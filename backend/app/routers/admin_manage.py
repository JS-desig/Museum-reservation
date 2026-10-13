"""账号权限管理 + 黑名单 + 时段容量配置 (系统管理员)。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin, get_current_admin
from app.core.security import hash_password
from app.core.response import ok, BizError, E_PARAM, E_NOT_FOUND, E_FORBIDDEN
from app.models.models import AdminUser, WxUser, SessionSlot, AuditLog, Reservation, SysConfig

router = APIRouter()


# ============ 后台账号 ============
@router.get("/admin/users")
def list_admins(admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    items = db.query(AdminUser).order_by(AdminUser.id).all()
    return ok([{
        "id": a.id, "username": a.username, "real_name": a.real_name,
        "role": a.role, "status": a.status,
    } for a in items])


class AdminUserReq(BaseModel):
    username: str
    password: str = ""
    real_name: str = ""
    role: str = "operator"
    status: int = 1


@router.post("/admin/users")
def create_admin(req: AdminUserReq, admin=Depends(require_admin), db: Session = Depends(get_db)):
    if db.query(AdminUser).filter_by(username=req.username).first():
        raise BizError(E_PARAM, "用户名已存在")
    if len(req.password) < 6:
        raise BizError(E_PARAM, "密码至少6位")
    u = AdminUser(username=req.username, password=hash_password(req.password),
                  real_name=req.real_name, role=req.role, status=req.status)
    db.add(u)
    db.flush()
    db.add(AuditLog(admin_id=admin.id, admin_name=admin.username,
                    action="admin_create", detail=f"新增账号 {req.username}({req.role})"))
    return ok({"id": u.id})


@router.put("/admin/users/{uid}")
def update_admin(uid: int, req: AdminUserReq, admin=Depends(require_admin), db: Session = Depends(get_db)):
    u = db.query(AdminUser).get(uid)
    if not u:
        raise BizError(E_NOT_FOUND, "账号不存在")
    u.real_name, u.role, u.status = req.real_name, req.role, req.status
    if req.password:
        if len(req.password) < 6:
            raise BizError(E_PARAM, "密码至少6位")
        u.password = hash_password(req.password)
    db.add(AuditLog(admin_id=admin.id, admin_name=admin.username,
                    action="admin_update", detail=f"更新账号 {u.username}"))
    return ok({"id": u.id})


# ============ 黑名单 ============
@router.get("/admin/blacklist")
def list_blacklist(page: int = 1, size: int = 20, keyword: str | None = None,
                   admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    page = max(1, page)
    size = min(max(1, size), 200)
    q = db.query(WxUser).filter(WxUser.is_blacklisted == 1)
    if keyword and keyword.strip():
        kw = keyword.strip()
        q = q.filter(WxUser.nickname.contains(kw)
                     | WxUser.id_card_masked.contains(kw)
                     | WxUser.phone_masked.contains(kw)
                     | WxUser.blacklist_reason.contains(kw))
    total = q.count()
    items = (q.order_by(WxUser.updated_at.desc(), WxUser.id.desc())
             .offset((page - 1) * size).limit(size).all())
    return ok({
        "total": total,
        "items": [{
            "id": u.id, "nickname": u.nickname, "real_name_masked": u.id_card_masked,
            "phone": u.phone_masked, "reason": u.blacklist_reason,
            "blacklisted_at": str(u.updated_at or ""),
        } for u in items],
    })


@router.get("/admin/wx-users")
def search_wx_users(keyword: str | None = None, page: int = 1, size: int = 20,
                    admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    """C端用户搜索(昵称/证件脱敏/手机号脱敏模糊), 供黑名单管理选人。

    返回字段全部脱敏, 不泄露明文实名信息。
    """
    page = max(1, page)
    size = min(max(1, size), 100)
    q = db.query(WxUser)
    if keyword and keyword.strip():
        kw = keyword.strip()
        q = q.filter(WxUser.nickname.contains(kw)
                     | WxUser.id_card_masked.contains(kw)
                     | WxUser.phone_masked.contains(kw))
    total = q.count()
    items = (q.order_by(WxUser.id.desc())
             .offset((page - 1) * size).limit(size).all())
    return ok({
        "total": total,
        "items": [{
            "id": u.id, "nickname": u.nickname,
            "id_card_masked": u.id_card_masked or "",
            "phone_masked": u.phone_masked or "",
            "is_verified": bool(u.is_verified),
            "is_blacklisted": bool(u.is_blacklisted),
            "blacklist_reason": u.blacklist_reason,
        } for u in items],
    })


class BlacklistReq(BaseModel):
    user_id: int
    reason: str = ""


@router.post("/admin/blacklist/add")
def add_blacklist(req: BlacklistReq, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    u = db.query(WxUser).get(req.user_id)
    if not u:
        raise BizError(E_NOT_FOUND, "用户不存在")
    already = u.is_blacklisted == 1
    u.is_blacklisted = 1
    u.blacklist_reason = req.reason
    db.add(AuditLog(admin_id=admin.id, admin_name=admin.username,
                    action="blacklist_add", detail=f"拉黑用户 {u.id}: {req.reason}"))
    return ok({"already": already, "id": u.id, "nickname": u.nickname})


@router.post("/admin/blacklist/remove")
def remove_blacklist(req: BlacklistReq, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    u = db.query(WxUser).get(req.user_id)
    if not u:
        raise BizError(E_NOT_FOUND, "用户不存在")
    u.is_blacklisted = 0
    u.blacklist_reason = None
    db.add(AuditLog(admin_id=admin.id, admin_name=admin.username,
                    action="blacklist_remove", detail=f"移出黑名单 {u.id}"))
    return ok()


# ============ 时段容量 ============
@router.get("/admin/slots")
def list_slots(admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    items = db.query(SessionSlot).order_by(SessionSlot.start_time).all()
    return ok([{
        "id": s.id, "name": s.name,
        "start_time": s.start_time.strftime("%H:%M"),
        "end_time": s.end_time.strftime("%H:%M"),
        "capacity": s.capacity, "is_active": s.is_active,
    } for s in items])


class SlotReq(BaseModel):
    name: str
    start_time: str
    end_time: str
    capacity: int
    is_active: int = 1


@router.post("/admin/slots")
def create_slot(req: SlotReq, admin=Depends(require_admin), db: Session = Depends(get_db)):
    from datetime import time as dtime
    s = SessionSlot(
        name=req.name,
        start_time=dtime(*map(int, req.start_time.split(":"))),
        end_time=dtime(*map(int, req.end_time.split(":"))),
        capacity=req.capacity, is_active=req.is_active)
    db.add(s)
    db.flush()
    db.add(AuditLog(admin_id=admin.id, admin_name=admin.username,
                    action="slot_create", detail=f"新增时段 {req.name} 容量{req.capacity}"))
    return ok({"id": s.id})


@router.put("/admin/slots/{sid}")
def update_slot(sid: int, req: SlotReq, admin=Depends(require_admin), db: Session = Depends(get_db)):
    from datetime import time as dtime
    s = db.query(SessionSlot).get(sid)
    if not s:
        raise BizError(E_NOT_FOUND, "时段不存在")
    s.name = req.name
    s.start_time = dtime(*map(int, req.start_time.split(":")))
    s.end_time = dtime(*map(int, req.end_time.split(":")))
    s.capacity = req.capacity
    s.is_active = req.is_active
    db.add(AuditLog(admin_id=admin.id, admin_name=admin.username,
                    action="slot_update", detail=f"更新时段 {req.name} 容量{req.capacity}"))
    return ok({"id": s.id})


# ============ 特殊时段开放日期(夜场等节假日限定时段) ============
@router.get("/admin/special-dates")
def get_special_dates(admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    row = db.query(SysConfig).filter_by(cfg_key="special_slot_dates").first()
    value = row.cfg_value if row else ""
    return ok({"dates": [d.strip() for d in value.split(",") if d.strip()], "raw": value})


@router.put("/admin/special-dates")
def update_special_dates(req: dict, admin=Depends(require_admin), db: Session = Depends(get_db)):
    """body: {"dates": ["2026-10-01", ...]} — 覆盖保存夜场开放日期。"""
    dates = req.get("dates") or []
    import re
    for d in dates:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(d)):
            raise BizError(E_PARAM, f"日期格式错误: {d}")
    value = ",".join(sorted(set(str(d) for d in dates)))
    row = db.query(SysConfig).filter_by(cfg_key="special_slot_dates").first()
    if row:
        row.cfg_value = value
    else:
        db.add(SysConfig(cfg_key="special_slot_dates", cfg_value=value,
                         remark="夜场等特殊时段开放日期(逗号分隔), 留空=日常不开放"))
    db.add(AuditLog(admin_id=admin.id, admin_name=admin.username,
                    action="special_dates_update", detail=f"特殊时段开放日期: {value or '(空)'}"))
    db.commit()
    return ok({"dates": [d for d in value.split(",") if d]})


# ============ 审计日志 ============
@router.get("/admin/audit-logs")
def audit_logs(page: int = 1, size: int = 50,
               admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    page = max(1, page)
    size = min(max(1, size), 200)  # 防超大size拖库
    q = db.query(AuditLog)
    total = q.count()
    items = (q.order_by(AuditLog.id.desc())
             .offset((page - 1) * size).limit(size).all())
    return ok({"total": total, "items": [{
        "id": a.id, "admin_name": a.admin_name, "action": a.action,
        "detail": a.detail, "ip": a.ip, "created_at": str(a.created_at),
    } for a in items]})
