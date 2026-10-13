"""闸机核销模块: 在线核销 / 离线批量补传 / 状态同步。

一致性设计(对应需求 3.3 / 四 / 五):
- 幂等: (gate_id, device_seq) 唯一约束, 重复指令返回首次结果;
- 核销成功 => check_record + access_log + reservation/reservation_visitor 状态更新同事务;
- 离线模式: 闸机本地缓存指令, 网络恢复后 POST /gate/sync/batch 补传, 服务端按
  device_seq 幂等去重, 按过闸时间(pass_time)落库, 保证对账无遗漏。
"""
from datetime import date, datetime, time as dtime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.core.security import hash_id_card, aes_decrypt, mask_name
from app.core.response import (
    ok, BizError, E_PARAM, E_NOT_FOUND,
    E_CHECK_INVALID, E_CHECK_ALREADY, E_CHECK_NO_RESV, E_CHECK_WRONG_SESSION,
    E_CHECK_BLACKLIST, E_CHECK_CANCELLED, E_CHECK_EXPIRED,
)
from app.models.models import (
    Reservation, ReservationVisitor, CheckRecord, AccessLog,
    OfflineSyncQueue, SessionSlot, WxUser, VenueInfo, AuditLog,
)

router = APIRouter()


class GateCheckReq(BaseModel):
    check_type: str = Field(..., pattern="^(qrcode|idcard)$")
    credential: str = Field(..., description="预约码 或 身份证号")
    direction: str = Field("in", pattern="^(in|out)$")
    gate_id: str = Field(..., description="闸机编号")
    device_seq: str = Field(..., description="闸机端指令唯一序号(幂等键)")


class GateSyncItem(GateCheckReq):
    pass_time: str = Field(..., description="过闸时间 ISO格式(离线补传时为实际时间)")


def _resolve_reservation(db: Session, req: GateCheckReq):
    """按凭证定位预约与同行人。返回 (reservation, visitor, fail_code)。

    游客行以 FOR UPDATE 加锁: 并发核销同一预约时后续事务在此排队, 拿到锁后重新
    求值 WHERE checked_in=? 跳过已被前序事务核销的游客, 避免"两人同时选中同一游客"
    导致重复计数与漏核销。锁后仍是当前读, 因此可见前序事务已提交的状态。
    """
    resv = None
    visitor = None
    if req.check_type == "qrcode":
        code = req.credential.strip().upper()
        resv = db.query(Reservation).filter_by(resv_code=code).first()
        if not resv:
            return None, None, E_CHECK_INVALID
        if req.direction == "out":
            # 出馆: 找最近入馆的游客
            visitor = (db.query(ReservationVisitor)
                       .filter_by(reservation_id=resv.id, checked_in=1)
                       .order_by(ReservationVisitor.checked_in_at.desc())
                       .with_for_update().first())
        else:
            visitor = (db.query(ReservationVisitor)
                       .filter_by(reservation_id=resv.id, checked_in=0)
                       .order_by(ReservationVisitor.id)
                       .with_for_update().first())
            if visitor is None:
                # 全部已核销 => 重复核销(不同device_seq也拦截)
                return None, None, E_CHECK_ALREADY
    else:
        card = req.credential.strip().upper()
        h = hash_id_card(card)
        visitor = (db.query(ReservationVisitor)
                   .filter_by(id_card_no=h, checked_in=0 if req.direction == "in" else 1)
                   .order_by(ReservationVisitor.id.desc())
                   .with_for_update().first())
        if not visitor:
            if req.direction == "out":
                return None, None, E_CHECK_INVALID  # 该证件当前不在馆内
            # 已核销过的证件 => 区分重复核销与无预约
            any_v = db.query(ReservationVisitor).filter_by(id_card_no=h).first()
            if any_v:
                return None, None, E_CHECK_ALREADY
            return None, None, E_CHECK_NO_RESV
        resv = db.query(Reservation).get(visitor.reservation_id)
        if not resv:
            return None, None, E_CHECK_NO_RESV
    return resv, visitor, None


def _validate(resv: Reservation, direction: str, at: datetime):
    """业务校验, 返回 fail_code 或 None。"""
    if resv.status == "cancelled":
        return E_CHECK_CANCELLED
    if resv.status == "expired" or resv.status == "no_show":
        return E_CHECK_EXPIRED
    if direction == "out":
        if resv.status != "checked_in":
            return E_CHECK_INVALID  # 未入馆不能出馆核销
        return None
    # 入馆校验
    if resv.status == "checked_in" and resv.checked_in_at and \
            resv.checked_in_at.date() != resv.visit_date:
        return E_CHECK_EXPIRED
    if resv.visit_date != at.date():
        return E_CHECK_WRONG_SESSION if resv.visit_date > at.date() else E_CHECK_EXPIRED
    return None


def _dup_response(prev: CheckRecord) -> dict:
    """幂等命中: 返回首次处理结果。"""
    return {
        "duplicate": True,
        "result": prev.result,
        "fail_reason": prev.fail_reason,
        "reservation_id": prev.reservation_id,
        "record_id": prev.id,
    }


def _find_prev(db: Session, req: GateCheckReq, locking: bool = False):
    """按幂等键(gate_id, device_seq)查首次结果。

    locking=True 用 FOR UPDATE 走"当前读": REPEATABLE-READ 下普通 SELECT 读的是
    事务开始时的快照, 看不到并发事务刚提交的同序号指令。
    """
    q = db.query(CheckRecord).filter_by(gate_id=req.gate_id, device_seq=req.device_seq)
    return (q.with_for_update().first() if locking else q.first())


def _insert_record(db: Session, req: GateCheckReq, **kw):
    """插入核销记录, 兜住并发同序号指令的唯一键冲突。

    返回 (record, is_duplicate)。冲突时回滚本事务并取回先到事务写入的记录。
    注: 调用点必须保证这是事务内首次写入(回滚不会丢失已完成的业务写入)。
    """
    rec = CheckRecord(**kw)
    db.add(rec)
    try:
        db.flush()
        return rec, False
    except IntegrityError:
        db.rollback()
        return _find_prev(db, req), True


def _do_check(db: Session, req: GateCheckReq, at: datetime | None,
              offline: bool = False) -> dict:
    """核心核销逻辑(幂等)。at=None 表示在线核销取当前时间。"""
    now = at or datetime.now()

    # 幂等: 同闸机同序号直接返回首次结果
    prev = _find_prev(db, req)
    if prev:
        return _dup_response(prev)

    # 黑名单检查(仅入馆)
    if req.direction == "in" and req.check_type == "idcard":
        h = hash_id_card(req.credential.strip().upper())
        wu = db.query(WxUser).filter_by(id_card_no=h).first()
        if wu and wu.is_blacklisted:
            rec, dup = _insert_record(
                db, req,
                check_type=req.check_type, credential=req.credential[:128],
                direction=req.direction, result="fail",
                fail_reason="blacklist", gate_id=req.gate_id,
                device_seq=req.device_seq, synced_offline=1 if offline else 0,
            )
            if dup:
                return _dup_response(rec)
            return {"duplicate": False, "result": "fail", "fail_reason": "blacklist",
                    "record_id": rec.id}

    resv, visitor, fail_code = _resolve_reservation(db, req)

    # 取到游客行锁后复查幂等键(当前读): 并发到达的同序号指令可能刚由先到事务落库,
    # 此时应返回其首次结果而不是重复处理。
    prev = _find_prev(db, req, locking=True)
    if prev:
        return _dup_response(prev)

    if resv and fail_code is None:
        # 黑名单用户(以预约内证件关联)
        if req.direction == "in" and visitor and visitor.user_id:
            wu = db.query(WxUser).get(visitor.user_id)
            if wu and wu.is_blacklisted:
                fail_code = E_CHECK_BLACKLIST

    if fail_code is None:
        fail_code = _validate(resv, req.direction, now)

    if fail_code is not None:
        rec, dup = _insert_record(
            db, req,
            check_type=req.check_type, credential=req.credential[:128],
            reservation_id=resv.id if resv else None,
            visitor_id=visitor.id if visitor else None,
            direction=req.direction, result="fail", fail_reason=fail_code,
            gate_id=req.gate_id, device_seq=req.device_seq,
            synced_offline=1 if offline else 0,
        )
        if dup:
            return _dup_response(rec)
        return {"duplicate": False, "result": "fail", "fail_reason": fail_code,
                "record_id": rec.id}

    # ---- 核销成功: 同事务更新预约状态 + 写核销记录 + 写通行日志 ----
    # 核销记录是本事务的首次写入, 因此若并发同序号指令抢先落库, 回滚不会丢失业务写入
    rec, dup = _insert_record(
        db, req,
        check_type=req.check_type, credential=req.credential[:128],
        reservation_id=resv.id, visitor_id=visitor.id, user_id=visitor.user_id,
        direction=req.direction, result="success",
        gate_id=req.gate_id, device_seq=req.device_seq,
        synced_offline=1 if offline else 0,
    )
    if dup:
        return _dup_response(rec)

    log = AccessLog(
        reservation_id=resv.id, user_id=visitor.user_id, visitor_id=visitor.id,
        gate_id=req.gate_id, direction=req.direction, pass_time=now,
        check_record_id=rec.id, synced_offline=1 if offline else 0,
    )
    db.add(log)

    if req.direction == "in":
        visitor.checked_in = 1
        visitor.checked_in_at = now
        # 首位游客过闸 => 预约整体标记已核销
        if resv.status == "booked":
            resv.status = "checked_in"
            resv.checked_in_at = now
            resv.check_in_gate = req.gate_id
    else:
        # 出馆: 标记该游客已出馆(重置入闸标记, 允许再次入园按新核销计)
        visitor.checked_in = 0
        # 该预约所有人已出 => 预约记出馆时间
        remaining = (db.query(ReservationVisitor)
                     .filter(ReservationVisitor.reservation_id == resv.id,
                             ReservationVisitor.checked_in == 1).count())
        if remaining <= 1:
            resv.checked_out_at = now

    db.flush()
    return {
        "duplicate": False, "result": "success", "fail_reason": None,
        "reservation_id": resv.id, "record_id": rec.id,
        "visitor": mask_name(aes_decrypt(visitor.real_name)) if visitor.real_name else "",
        "visit_date": str(resv.visit_date), "direction": req.direction,
    }


FAIL_MSG = {
    "invalid_code": "无效预约码", "already_checked": "该游客已核销",
    "no_resv": "未找到有效预约", "wrong_session": "错峰: 不在预约日期/时段",
    "blacklist": "黑名单用户禁止入馆", "cancelled": "预约已取消",
    "expired": "预约已过期", E_CHECK_ALREADY: "重复核销",
}


@router.post("/gate/check")
def gate_check(req: GateCheckReq, db: Session = Depends(get_db)):
    """闸机在线核销。响应 < 0.5s 要求: 纯索引查询+单事务写入。"""
    result = _do_check(db, req, None, offline=False)
    if result["result"] == "success":
        return ok({**result, "gate_action": "open", "voice": "welcome",
                   "light": "green"})
    return ok({**result, "gate_action": "deny", "voice": "deny",
               "light": "red"})


# ============ 离线补传 ============
class GateSyncBatchReq(BaseModel):
    gate_id: str
    items: list[GateSyncItem]


@router.post("/gate/sync/batch")
def gate_sync_batch(req: GateSyncBatchReq, db: Session = Depends(get_db)):
    """断网恢复后闸机批量补传。逐条幂等处理, 单条失败不影响其余。"""
    results = []
    for item in req.items:
        try:
            at = datetime.fromisoformat(item.pass_time)
        except ValueError:
            results.append({"device_seq": item.device_seq, "result": "fail",
                            "fail_reason": "bad_pass_time"})
            continue
        try:
            r = _do_check(db, item, at, offline=True)
            results.append({"device_seq": item.device_seq, **r})
        except Exception as e:
            db.rollback()
            results.append({"device_seq": item.device_seq, "result": "fail",
                            "fail_reason": f"error:{type(e).__name__}"})
    # 入队记录(审计/重试追踪)
    for item in req.items:
        exists = db.query(OfflineSyncQueue).filter_by(
            gate_id=item.gate_id, device_seq=item.device_seq).first()
        if not exists:
            db.add(OfflineSyncQueue(
                gate_id=item.gate_id, device_seq=item.device_seq,
                payload=item.model_dump(), status="done",
                synced_at=datetime.now()))
    db.commit()
    return ok({"total": len(req.items), "results": results})


# ============ 闸机心跳/配置下发 ============
@router.get("/gate/config")
def gate_config(gate_id: str, db: Session = Depends(get_db)):
    """闸机启动时拉取: 今日时段、闭馆状态、最大承载。"""
    venue = db.query(VenueInfo).first()
    slots = db.query(SessionSlot).filter(SessionSlot.is_active == 1).all()
    return ok({
        "gate_id": gate_id,
        "venue_open": bool(venue and venue.status == 1),
        "venue_name": venue.name if venue else "",
        "slots": [{"id": s.id, "name": s.name,
                   "start": s.start_time.strftime("%H:%M"),
                   "end": s.end_time.strftime("%H:%M")} for s in slots],
        "server_time": datetime.now().isoformat(),
    })


# ============ B端: 核销记录 / 手动核销 / 异常处理 ============
@router.get("/admin/check-records")
def admin_check_records(
    page: int = 1, size: int = 20, result: str | None = None,
    gate_id: str | None = None, date_str: str | None = None,
    admin=Depends(get_current_admin), db: Session = Depends(get_db),
):
    page = max(1, page)
    size = min(max(1, size), 200)  # 防超大size拖库
    q = db.query(CheckRecord)
    if result:
        q = q.filter(CheckRecord.result == result)
    if gate_id:
        q = q.filter(CheckRecord.gate_id == gate_id)
    if date_str:
        d = date.fromisoformat(date_str)
        q = q.filter(func.date(CheckRecord.created_at) == d)
    total = q.count()
    items = (q.order_by(CheckRecord.id.desc())
             .offset((page - 1) * size).limit(size).all())
    return ok({
        "total": total,
        "items": [{
            "id": c.id, "check_type": c.check_type, "credential": c.credential,
            "reservation_id": c.reservation_id, "direction": c.direction,
            "result": c.result, "fail_reason": c.fail_reason,
            "gate_id": c.gate_id, "device_seq": c.device_seq,
            "synced_offline": c.synced_offline, "created_at": str(c.created_at),
        } for c in items],
    })


class ManualCheckReq(BaseModel):
    resv_code: str
    action: str = Field(..., pattern="^(check_in|cancel)$")


@router.post("/admin/reservations/manual")
def manual_operate(req: ManualCheckReq, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    """手动核销/取消异常预约。"""
    r = db.query(Reservation).filter_by(resv_code=req.resv_code.upper()).first()
    if not r:
        raise BizError(E_NOT_FOUND, "预约不存在")
    if req.action == "check_in":
        if r.status != "booked":
            raise BizError(E_PARAM, "仅已预约状态可手动核销")
        r.status = "checked_in"
        r.checked_in_at = datetime.now()
        r.check_in_gate = "MANUAL"
        for v in db.query(ReservationVisitor).filter_by(reservation_id=r.id).all():
            v.checked_in = 1
            v.checked_in_at = r.checked_in_at
        # 手动核销同样补通行日志, 保证对账一致
        db.add(AccessLog(
            reservation_id=r.id, user_id=r.user_id, gate_id="MANUAL",
            direction="in", pass_time=r.checked_in_at, synced_offline=0))
        msg = "手动核销入馆"
    else:
        if r.status not in ("booked",):
            raise BizError(E_PARAM, "仅已预约状态可取消")
        r.status = "cancelled"
        r.cancel_time = datetime.now()
        msg = "手动取消预约"
    db.add(AuditLog(admin_id=admin.id, admin_name=admin.username,
                    action=f"resv_{req.action}", detail=f"{msg} {r.resv_code}"))
    return ok({"id": r.id, "status": r.status})
