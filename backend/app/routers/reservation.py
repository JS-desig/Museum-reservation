"""预约模块: C端预约/取消/查询 + B端预约管理/黑名单/承载量。

强一致性设计:
- 名额扣减、同行人明细写入、证件限次计数在同一事务;
- 时段名额校验基于 SUM(visitor_count) 实时统计, 不依赖冗余计数字段;
- 同证件同日同时段唯一性 + 每日预约次数上限防刷。
"""
import math
import random
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin, get_wx_user_id
from app.core.security import (
    aes_encrypt, aes_decrypt, validate_id_card, hash_id_card,
    mask_id_card, mask_name, check_nonce, gen_resv_code,
)
from app.core.config import settings
from app.core.response import (
    ok, BizError, E_PARAM, E_NOT_FOUND, E_FORBIDDEN,
    E_RESV_FULL, E_RESV_LIMIT, E_RESV_DUPLICATE, E_RESV_CANCELLED, E_RESV_NOT_BOOKED,
)
from app.core.ratelimit import rate_limit
from app.models.models import (
    WxUser, SessionSlot, Reservation, ReservationVisitor,
    ResvDailyLimit, VenueInfo, AuditLog, SysConfig,
)

router = APIRouter()

ACTIVE_STATUSES = ("booked", "checked_in")

NIGHT_SLOT_KEYWORD = "夜"   # 时段名含此关键字视为夜场(特殊日期限定)


def _special_slot_dates(db: Session) -> set[str]:
    """夜场等特殊时段的开放日期(逗号分隔), 来自 sys_config.special_slot_dates。"""
    row = db.query(SysConfig).filter_by(cfg_key="special_slot_dates").first()
    if not row or not row.cfg_value.strip():
        return set()
    return {d.strip() for d in row.cfg_value.split(",") if d.strip()}


def _is_special_date(db: Session, visit_date: date) -> bool:
    return str(visit_date) in _special_slot_dates(db)


# ---------- 通用: 时段剩余名额 ----------
def slot_remaining(db: Session, visit_date: date, session_id: int) -> dict:
    slot = db.query(SessionSlot).filter(
        SessionSlot.id == session_id, SessionSlot.is_active == 1).first()
    if not slot:
        raise BizError(E_PARAM, "时段不存在或已停用")
    used = db.query(func.coalesce(func.sum(Reservation.visitor_count), 0)).filter(
        Reservation.visit_date == visit_date,
        Reservation.session_id == session_id,
        Reservation.status.in_(ACTIVE_STATUSES),
    ).scalar()
    return {"slot": slot, "used": int(used), "remaining": max(0, slot.capacity - int(used))}


def list_slots_with_remaining(db: Session, visit_date: date):
    slots = db.query(SessionSlot).filter(SessionSlot.is_active == 1).order_by(SessionSlot.start_time).all()
    special_day = _is_special_date(db, visit_date)
    # 夜场仅特殊日期(节假日)开放, 日常隐藏且不可约
    if not special_day:
        slots = [s for s in slots if NIGHT_SLOT_KEYWORD not in (s.name or "")]
    used_rows = (db.query(Reservation.session_id,
                          func.coalesce(func.sum(Reservation.visitor_count), 0))
                 .filter(Reservation.visit_date == visit_date,
                         Reservation.status.in_(ACTIVE_STATUSES))
                 .group_by(Reservation.session_id).all())
    used_map = {sid: int(u) for sid, u in used_rows}
    venue = db.query(VenueInfo).first()
    daily_total = sum(used_map.values())
    out = []
    for s in slots:
        out.append({
            "id": s.id, "name": s.name,
            "start_time": s.start_time.strftime("%H:%M"),
            "end_time": s.end_time.strftime("%H:%M"),
            "capacity": s.capacity,
            "used": used_map.get(s.id, 0),
            "remaining": max(0, s.capacity - used_map.get(s.id, 0)),
        })
    daily_max = venue.max_daily if venue else 5000
    return {
        "visit_date": str(visit_date),
        "closed": bool(venue and venue.status == 0),
        "daily_used": daily_total,
        "daily_max": daily_max,
        "daily_remaining": max(0, daily_max - daily_total),
        "slots": out,
    }


# ============ C端: 查询某日时段余量 ============
@router.get("/wx/slots")
def wx_query_slots(visit_date: str, db: Session = Depends(get_db)):
    try:
        d = date.fromisoformat(visit_date)
    except ValueError:
        raise BizError(E_PARAM, "日期格式错误, 应为YYYY-MM-DD")
    if d < date.today():
        raise BizError(E_PARAM, "不能查询过去的日期")
    if d > date.today() + timedelta(days=7):
        raise BizError(E_PARAM, "仅支持未来7天内预约")
    return ok(list_slots_with_remaining(db, d))


# ============ C端: 创建预约 ============
class VisitorItem(BaseModel):
    real_name: str
    id_card_no: str
    phone: str = ""


class CreateResvReq(BaseModel):
    visit_date: str
    session_id: int
    visitors: list[VisitorItem] = Field(..., min_length=1)
    nonce: str | None = Field(None, description="防重放nonce")


@router.post("/wx/reservations")
def create_reservation(
    req: CreateResvReq,
    openid: str = Depends(get_wx_user_id),
    db: Session = Depends(get_db),
):
    # 防刷: 同一用户每小时最多10笔预约(防脚本刷票占用名额)
    rate_limit(10, 3600, f"resv:{openid}")
    # 防重放nonce在事务开启前检查
    if not check_nonce(req.nonce):
        raise BizError(E_PARAM, "重复请求, 请勿重复提交")
    try:
        visit_date = date.fromisoformat(req.visit_date)
    except ValueError:
        raise BizError(E_PARAM, "日期格式错误")

    if visit_date < date.today():
        raise BizError(E_PARAM, "不能预约过去的日期")
    if visit_date > date.today() + timedelta(days=7):
        raise BizError(E_PARAM, "仅支持未来7天内预约")

    user = db.query(WxUser).filter_by(openid=openid).first()
    if not user:
        raise BizError(E_NOT_FOUND, "用户不存在")
    if user.is_blacklisted:
        raise BizError(E_FORBIDDEN, f"您已被列入黑名单: {user.blacklist_reason or '违规'}")

    # 同行人数校验
    n = len(req.visitors)
    if n > settings.MAX_VISITORS_PER_RESV:
        raise BizError(E_PARAM, f"单笔预约最多{settings.MAX_VISITORS_PER_RESV}人")

    # 身份证合法性 + 去重; 主预约人证件号可为脱敏值(由服务端用本人绑定信息补全)
    cards = []
    for i, v in enumerate(req.visitors):
        no = v.id_card_no.strip().upper()
        if "*" in no:
            if i != 0:
                raise BizError(E_PARAM, f"同行人证件号不能使用脱敏值: {v.real_name}")
            full = aes_decrypt(user.id_card_enc) if user.id_card_enc else None
            if (not full
                    or len(full) != len(no)
                    or any(m != "*" and m != c for m, c in zip(no, full))):
                raise BizError(E_PARAM, "证件号与实名信息不匹配, 请重新实名")
            no = full
        if not validate_id_card(no):
            raise BizError(E_PARAM, f"身份证号校验失败: {v.real_name}")
        cards.append(no)
    if len(set(cards)) != len(cards):
        raise BizError(E_PARAM, "同行人身份证号重复")

    venue = db.query(VenueInfo).first()
    if venue and venue.status == 0:
        raise BizError(E_PARAM, "场馆今日闭馆, 暂停预约")

    # 主预约人必须已实名, 且其证件须在同行人中
    if not user.is_verified or not user.id_card_no:
        raise BizError(E_PARAM, "请先完成实名认证")
    if user.id_card_no not in [hash_id_card(c) for c in cards]:
        raise BizError(E_PARAM, "主预约人证件必须包含在预约人中")

    # 防刷1: 每证件每日预约次数
    for no in cards:
        h = hash_id_card(no)
        row = db.query(ResvDailyLimit).filter_by(id_card_no=h, visit_date=visit_date).first()
        if row and row.resv_count >= settings.MAX_RESV_PER_CARD_PER_DAY:
            raise BizError(E_RESV_LIMIT, "该证件今日预约次数已达上限")

    # 防刷2: 同证件同日同时段唯一
    dup = (db.query(ReservationVisitor.reservation_id)
           .join(Reservation, Reservation.id == ReservationVisitor.reservation_id)
           .filter(Reservation.visit_date == visit_date,
                   Reservation.session_id == req.session_id,
                   Reservation.status.in_(ACTIVE_STATUSES),
                   ReservationVisitor.id_card_no.in_([hash_id_card(c) for c in cards]))
           .first())
    if dup:
        raise BizError(E_RESV_DUPLICATE, "该证件当日该时段已有有效预约")

    # 名额校验+写入(悲观锁串行化, 防高并发超卖):
    # 1) 锁定时段行 => 同一时段的并发请求在此排队
    # 2) used统计必须在锁后用"当前读"(原生SQL), 否则REPEATABLE-READ快照读到旧值
    slot_row = db.query(SessionSlot).filter(
        SessionSlot.id == req.session_id).with_for_update().first()
    if not slot_row or slot_row.is_active != 1:
        db.rollback()
        raise BizError(E_PARAM, "时段不存在或已停用")
    # 夜场仅特殊日期(节假日)开放; 日常创建预约直接拦截
    if NIGHT_SLOT_KEYWORD in (slot_row.name or "") and not _is_special_date(db, visit_date):
        db.rollback()
        raise BizError(E_PARAM, "该时段仅节假日开放, 当前日期不可预约")
    used = db.execute(
        text("SELECT COALESCE(SUM(visitor_count),0) FROM reservation "
             "WHERE visit_date=:d AND session_id=:s AND status IN ('booked','checked_in') "
             "FOR UPDATE"),
        {"d": visit_date, "s": req.session_id}).scalar()
    info = {"used": int(used or 0), "remaining": max(0, slot_row.capacity - int(used or 0))}
    if info["remaining"] < n:
        db.rollback()
        raise BizError(E_RESV_FULL, f"该时段剩余名额不足(余{info['remaining']})")
    if venue and info["used"] + n > venue.max_daily:
        db.rollback()
        raise BizError(E_RESV_FULL, "当日总承载量已满")

    # 写入预约
    resv = Reservation(
        resv_code=gen_resv_code(), user_id=user.id,
        visit_date=visit_date, session_id=req.session_id,
        visitor_count=n, status="booked",
    )
    db.add(resv)
    db.flush()

    for v, no in zip(req.visitors, cards):
        db.add(ReservationVisitor(
            reservation_id=resv.id,
            user_id=user.id if hash_id_card(no) == user.id_card_no else None,
            real_name=aes_encrypt(v.real_name.strip()),
            real_name_masked=mask_name(v.real_name.strip()),
            id_card_no=hash_id_card(no),
            id_card_masked=mask_id_card(no),
        ))

    # 限次计数
    for no in cards:
        h = hash_id_card(no)
        row = db.query(ResvDailyLimit).filter_by(id_card_no=h, visit_date=visit_date).first()
        if row:
            row.resv_count += 1
        else:
            db.add(ResvDailyLimit(id_card_no=h, visit_date=visit_date, resv_count=1))

    return ok({
        "reservation_id": resv.id, "resv_code": resv.resv_code,
        "visit_date": str(visit_date), "session_id": req.session_id,
        "visitor_count": n, "status": resv.status,
    })


# ============ C端: 我的预约 ============
@router.get("/wx/reservations")
def my_reservations(openid: str = Depends(get_wx_user_id), db: Session = Depends(get_db)):
    user = db.query(WxUser).filter_by(openid=openid).first()
    if not user:
        raise BizError(E_NOT_FOUND, "用户不存在")
    resvs = (db.query(Reservation).filter(Reservation.user_id == user.id)
             .order_by(Reservation.id.desc()).limit(50).all())
    slots = {s.id: s for s in db.query(SessionSlot).all()}
    out = []
    for r in resvs:
        s = slots.get(r.session_id)
        visitors = db.query(ReservationVisitor).filter_by(reservation_id=r.id).all()
        out.append({
            "id": r.id, "resv_code": r.resv_code,
            "visit_date": str(r.visit_date),
            "session_name": s.name if s else "",
            "session_time": f"{s.start_time.strftime('%H:%M')}-{s.end_time.strftime('%H:%M')}" if s else "",
            "visitor_count": r.visitor_count,
            "status": r.status,
            "checked_in_at": str(r.checked_in_at or ""),
            "checked_out_at": str(r.checked_out_at or ""),
            "visitors": [{"real_name": v.real_name_masked, "id_card_masked": v.id_card_masked,
                          "checked_in": bool(v.checked_in)} for v in visitors],
        })
    return ok(out)


# ============ C端: 取消预约 ============
@router.delete("/wx/reservations/{resv_id}")
def cancel_reservation(
    resv_id: int,
    openid: str = Depends(get_wx_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(WxUser).filter_by(openid=openid).first()
    if not user:
        raise BizError(E_NOT_FOUND, "用户不存在")
    r = db.query(Reservation).filter_by(id=resv_id, user_id=user.id).first()
    if not r:
        raise BizError(E_NOT_FOUND, "预约不存在")
    if r.status != "booked":
        raise BizError(E_RESV_NOT_BOOKED, "当前状态不可取消")

    slot = db.query(SessionSlot).get(r.session_id)
    deadline = datetime.combine(r.visit_date, slot.start_time) - timedelta(
        minutes=settings.CANCEL_BEFORE_MINUTES)
    if datetime.now() > deadline:
        raise BizError(E_PARAM, f"需在预约时段开始前{settings.CANCEL_BEFORE_MINUTES}分钟取消")

    r.status = "cancelled"
    r.cancel_time = datetime.now()
    # 释放当日限次额度: 该单每个证件的计数回减1
    visitor_cards = (db.query(ReservationVisitor.id_card_no)
                     .filter(ReservationVisitor.reservation_id == r.id).all())
    for (h,) in visitor_cards:
        row = db.query(ResvDailyLimit).filter_by(id_card_no=h, visit_date=r.visit_date).first()
        if row and row.resv_count > 0:
            row.resv_count -= 1
    db.commit()
    return ok({"id": r.id, "status": r.status})


# ============ C端: 通行记录 ============
@router.get("/wx/pass-records")
def my_pass_records(openid: str = Depends(get_wx_user_id), db: Session = Depends(get_db)):
    from app.models.models import AccessLog
    user = db.query(WxUser).filter_by(openid=openid).first()
    if not user:
        raise BizError(E_NOT_FOUND, "用户不存在")
    logs = (db.query(AccessLog).filter_by(user_id=user.id)
            .order_by(AccessLog.pass_time.desc()).limit(100).all())
    return ok([{
        "id": l.id, "direction": l.direction, "pass_time": str(l.pass_time),
        "gate_id": l.gate_id, "reservation_id": l.reservation_id,
    } for l in logs])
