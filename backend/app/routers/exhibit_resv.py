"""特殊展项预约模块: 付费展项体验预约。

与入馆预约(reservation)的关键区别:
- 需付费(模拟支付闭环), 入馆预约免费;
- 前置条件: 用户须有同日的有效入馆预约(先约入馆, 才能约展项);
- 展项级容量限制(每时段可体验人数), 悲观锁防超卖;
- 同一用户同日同时段同展项限约 1 次, 每展项每日限约 2 次。
"""
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin, get_wx_user_id
from app.core.ratelimit import rate_limit
from app.core.response import ok, BizError, E_PARAM, E_NOT_FOUND, E_FORBIDDEN, E_RESV_FULL, E_RESV_DUPLICATE, E_RESV_LIMIT
from app.core.security import check_nonce, gen_resv_code
from app.models.models import (
    Exhibit, ExhibitReservation, Reservation, SessionSlot, WxUser, AuditLog,
)

router = APIRouter()

# 展项预约状态口径: booked=已预约(已支付) used=已体验 cancelled=已取消
ACTIVE_STATUSES = ("booked", "used")
MAX_EXHIBIT_RESV_PER_DAY = 1   # 同一用户同一展项每日限约次数(取消释放额度)
CANCEL_BEFORE_MINUTES = 30     # 体验时段开始前 N 分钟可取消


def _slot_used(db: Session, exhibit_id: int, visit_date: date, session_id: int) -> int:
    used = db.execute(
        text("SELECT COALESCE(SUM(person_count),0) FROM exhibit_reservation "
             "WHERE exhibit_id=:e AND visit_date=:d AND session_id=:s AND status IN ('booked','used') "
             "FOR UPDATE"),
        {"e": exhibit_id, "d": visit_date, "s": session_id}).scalar()
    return int(used or 0)


# ============ C端: 特殊展项可约列表(含余量) ============
@router.get("/wx/exhibit-reservations/special")
def list_special_exhibits(visit_date: str, db: Session = Depends(get_db)):
    try:
        d = date.fromisoformat(visit_date)
    except ValueError:
        raise BizError(E_PARAM, "日期格式错误")
    if d < date.today() or d > date.today() + timedelta(days=7):
        raise BizError(E_PARAM, "仅支持今日起7天内查询")

    specials = (db.query(Exhibit)
                .filter(Exhibit.status == 1, Exhibit.is_special == 1)
                .order_by(Exhibit.hall_name, Exhibit.sort_order).all())
    out = []
    for e in specials:
        used = (db.query(ExhibitReservation)
                .filter(ExhibitReservation.exhibit_id == e.id,
                        ExhibitReservation.visit_date == d,
                        ExhibitReservation.status.in_(ACTIVE_STATUSES))
                .with_entities(ExhibitReservation.session_id,
                               ExhibitReservation.person_count).all())
        used_map: dict[int, int] = {}
        for sid, cnt in used:
            used_map[sid] = used_map.get(sid, 0) + int(cnt)
        out.append({
            "id": e.id, "hall_name": e.hall_name, "title": e.title,
            "description": e.description, "media_type": e.media_type, "media_url": e.media_url,
            "price_cent": e.price_cent, "capacity": e.capacity,
            "sessions": [{"session_id": sid, "remaining": max(0, e.capacity - used_map.get(sid, 0))}
                         for sid in used_map] or
                        # 无预约时返回全部启用时段(余量=展项容量); 不再返回 session_id=0 占位,
                        # 否则前端提交 0 会触发"体验时段不存在或已停用"
                        [{"session_id": s.id, "remaining": e.capacity}
                         for s in db.query(SessionSlot)
                                    .filter(SessionSlot.is_active == 1)
                                    .order_by(SessionSlot.start_time).all()],
        })
    return ok(out)


# ============ C端: 创建特殊展项预约 ============
class ExhibitResvReq(BaseModel):
    exhibit_id: int
    visit_date: str
    session_id: int
    person_count: int = Field(1, ge=1, le=5, description="体验人数(1-5, 须≤入馆预约人数)")
    nonce: str | None = Field(None, description="防重放nonce")


@router.post("/wx/exhibit-reservations")
def create_exhibit_reservation(
    req: ExhibitResvReq,
    openid: str = Depends(get_wx_user_id),
    db: Session = Depends(get_db),
):
    rate_limit(10, 3600, f"exresv:{openid}")
    if not check_nonce(req.nonce):
        raise BizError(E_PARAM, "重复请求, 请勿重复提交")
    try:
        visit_date = date.fromisoformat(req.visit_date)
    except ValueError:
        raise BizError(E_PARAM, "日期格式错误")
    if visit_date < date.today() or visit_date > date.today() + timedelta(days=7):
        raise BizError(E_PARAM, "仅支持今日起7天内预约")

    user = db.query(WxUser).filter_by(openid=openid).first()
    if not user:
        raise BizError(E_NOT_FOUND, "用户不存在")
    if user.is_blacklisted:
        raise BizError(E_FORBIDDEN, f"您已被列入黑名单: {user.blacklist_reason or '违规'}")
    if not user.is_verified:
        raise BizError(E_PARAM, "请先完成实名认证")

    exhibit = db.query(Exhibit).filter(Exhibit.id == req.exhibit_id, Exhibit.status == 1).first()
    if not exhibit:
        raise BizError(E_NOT_FOUND, "展项不存在或已下架")
    if not exhibit.is_special:
        raise BizError(E_PARAM, "该展项为普通展项, 免费参观无需预约体验")

    slot = db.query(SessionSlot).filter(SessionSlot.id == req.session_id,
                                        SessionSlot.is_active == 1).first()
    if not slot:
        raise BizError(E_NOT_FOUND, "体验时段不存在或已停用")

    # 前置校验1: 须已有同日同时段的有效入馆预约 (先约入馆, 才能约展项)
    entry = (db.query(Reservation)
             .filter(Reservation.user_id == user.id,
                     Reservation.visit_date == visit_date,
                     Reservation.session_id == req.session_id,
                     Reservation.status.in_(("booked", "checked_in")))
             .first())
    if not entry:
        raise BizError(E_FORBIDDEN, "请先预约当日入馆, 再预约特殊展项体验")
    if req.person_count > entry.visitor_count:
        raise BizError(E_PARAM, f"体验人数不能超过入馆预约人数({entry.visitor_count}人)")

    # 前置校验2: 限次(仅计有效预约; 取消不占额度)
    my_today = (db.query(ExhibitReservation)
                .filter(ExhibitReservation.user_id == user.id,
                        ExhibitReservation.exhibit_id == exhibit.id,
                        ExhibitReservation.visit_date == visit_date,
                        ExhibitReservation.status.in_(ACTIVE_STATUSES)).count())
    if my_today >= MAX_EXHIBIT_RESV_PER_DAY:
        raise BizError(E_RESV_LIMIT, "该展项今日预约次数已达上限")

    dup = (db.query(ExhibitReservation)
           .filter(ExhibitReservation.user_id == user.id,
                   ExhibitReservation.exhibit_id == exhibit.id,
                   ExhibitReservation.visit_date == visit_date,
                   ExhibitReservation.session_id == req.session_id,
                   ExhibitReservation.status.in_(ACTIVE_STATUSES))
           .first())
    if dup:
        raise BizError(E_RESV_DUPLICATE, "该时段已预约此展项体验")

    # 容量校验+写入: 悲观锁串行化防超卖
    amount = exhibit.price_cent * req.person_count
    resv = ExhibitReservation(
        resv_code=gen_resv_code(), exhibit_id=exhibit.id, user_id=user.id,
        visit_date=visit_date, session_id=req.session_id,
        person_count=req.person_count, amount_cent=amount,
    )
    try:
        db.execute(text("SELECT id FROM session_slot WHERE id=:s FOR UPDATE"),
                   {"s": req.session_id})
        used = _slot_used(db, exhibit.id, visit_date, req.session_id)
        remaining = max(0, exhibit.capacity - used)
        if remaining < req.person_count:
            db.rollback()
            raise BizError(E_RESV_FULL, f"该展项体验名额不足(余{remaining})")
        db.add(resv)
        db.commit()
    except BizError:
        raise
    except Exception:
        db.rollback()
        raise

    return ok({
        "id": resv.id, "resv_code": resv.resv_code,
        "exhibit_id": exhibit.id, "exhibit_title": exhibit.title,
        "visit_date": str(visit_date), "session_id": req.session_id,
        "person_count": req.person_count,
        "amount_cent": amount, "pay_status": resv.pay_status,
    })


# ============ C端: 模拟支付 ============
@router.post("/wx/exhibit-reservations/{resv_id}/pay")
def pay_exhibit_reservation(resv_id: int, openid: str = Depends(get_wx_user_id),
                            db: Session = Depends(get_db)):
    user = db.query(WxUser).filter_by(openid=openid).first()
    if not user:
        raise BizError(E_NOT_FOUND, "用户不存在")
    resv = db.query(ExhibitReservation).filter(
        ExhibitReservation.id == resv_id, ExhibitReservation.user_id == user.id).first()
    if not resv:
        raise BizError(E_NOT_FOUND, "展项预约不存在")
    if resv.status != "booked":
        raise BizError(E_PARAM, "当前状态不可支付")
    if resv.pay_status == "paid":
        return ok({"resv_code": resv.resv_code, "pay_status": "paid"})
    # 模拟支付: 无商户号环境下直接置已支付; 生产环境替换为 wx.requestPayment 回调
    resv.pay_status = "paid"
    resv.paid_at = datetime.now()
    db.commit()
    return ok({"resv_code": resv.resv_code, "pay_status": "paid",
               "amount_cent": resv.amount_cent, "paid_at": str(resv.paid_at)})


# ============ C端: 我的展项预约 ============
@router.get("/wx/exhibit-reservations")
def my_exhibit_reservations(openid: str = Depends(get_wx_user_id), db: Session = Depends(get_db)):
    user = db.query(WxUser).filter_by(openid=openid).first()
    if not user:
        raise BizError(E_NOT_FOUND, "用户不存在")
    rows = (db.query(ExhibitReservation, Exhibit)
            .join(Exhibit, Exhibit.id == ExhibitReservation.exhibit_id)
            .filter(ExhibitReservation.user_id == user.id)
            .order_by(ExhibitReservation.id.desc()).limit(50).all())
    slots = {s.id: s for s in db.query(SessionSlot).all()}
    out = []
    for r, e in rows:
        s = slots.get(r.session_id)
        out.append({
            "id": r.id, "resv_code": r.resv_code,
            "exhibit_id": e.id, "exhibit_title": e.title, "hall_name": e.hall_name,
            "price_cent": e.price_cent,
            "visit_date": str(r.visit_date),
            "session_name": s.name if s else "",
            "session_time": f"{s.start_time}-{s.end_time}" if s else "",
            "person_count": r.person_count,
            "amount_cent": r.amount_cent,
            "pay_status": r.pay_status,
            "status": r.status,
        })
    return ok(out)


# ============ C端: 取消展项预约(未体验且时段开始前30分钟; 已支付走退款) ============
@router.delete("/wx/exhibit-reservations/{resv_id}")
def cancel_exhibit_reservation(resv_id: int, openid: str = Depends(get_wx_user_id),
                               db: Session = Depends(get_db)):
    user = db.query(WxUser).filter_by(openid=openid).first()
    if not user:
        raise BizError(E_NOT_FOUND, "用户不存在")
    resv = db.query(ExhibitReservation).filter(
        ExhibitReservation.id == resv_id, ExhibitReservation.user_id == user.id).first()
    if not resv:
        raise BizError(E_NOT_FOUND, "展项预约不存在")
    if resv.status != "booked":
        raise BizError(E_PARAM, "当前状态不可取消")

    slot = db.query(SessionSlot).filter(SessionSlot.id == resv.session_id).first()
    if slot:
        start_dt = datetime.combine(resv.visit_date, slot.start_time)
        if datetime.now() > start_dt - timedelta(minutes=CANCEL_BEFORE_MINUTES):
            raise BizError(E_PARAM, f"体验开始前{CANCEL_BEFORE_MINUTES}分钟内不可取消")

    refunded = resv.pay_status == "paid"
    if refunded:
        resv.pay_status = "refunded"   # 模拟原路退款
    resv.status = "cancelled"
    resv.cancel_time = datetime.now()
    db.commit()
    return ok({"id": resv.id, "status": resv.status, "refunded": refunded})


# ============ B端: 展项预约明细 ============
@router.get("/admin/exhibit-reservations")
def admin_exhibit_reservations(visit_date: str | None = None, keyword: str | None = None,
                               admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    q = (db.query(ExhibitReservation, Exhibit, WxUser)
         .join(Exhibit, Exhibit.id == ExhibitReservation.exhibit_id)
         .join(WxUser, WxUser.id == ExhibitReservation.user_id))
    if visit_date:
        try:
            q = q.filter(ExhibitReservation.visit_date == date.fromisoformat(visit_date))
        except ValueError:
            raise BizError(E_PARAM, "日期格式错误")
    if keyword:
        q = q.filter(ExhibitReservation.resv_code.contains(keyword)
                     | Exhibit.title.contains(keyword))
    rows = q.order_by(ExhibitReservation.id.desc()).limit(200).all()
    slots = {s.id: s for s in db.query(SessionSlot).all()}
    return ok([{
        "id": r.id, "resv_code": r.resv_code,
        "exhibit_title": e.title, "hall_name": e.hall_name,
        "nickname": u.nickname, "phone_masked": u.phone_masked or "",
        "visit_date": str(r.visit_date),
        "session_name": slots[r.session_id].name if r.session_id in slots else "",
        "person_count": r.person_count,
        "amount_cent": r.amount_cent,
        "pay_status": r.pay_status,
        "status": r.status,
        "created_at": str(r.created_at or ""),
    } for r, e, u in rows])
