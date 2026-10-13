"""统计与看板模块: 客流统计 / 预约核销率 / 爽约率 / 实时在馆人数 / 峰值预警。

数据一致性: 所有统计以 access_log 为对账基准, 辅以 reservation 聚合;
SQL 校验脚本(tests/sql) 验证两套口径完全一致。
"""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.core.config import settings
from app.core.response import ok
from app.models.models import (
    Reservation, ReservationVisitor, CheckRecord, AccessLog,
    SessionSlot, VenueInfo, WxUser, SysConfig,
)

router = APIRouter()


def _warn_ratio(db: Session) -> float:
    """客流预警阈值: 优先读sys_config, 缺省用settings。"""
    row = db.query(SysConfig).filter_by(cfg_key="capacity_warn_ratio").first()
    try:
        return float(row.cfg_value) if row else settings.CAPACITY_WARN_RATIO
    except (ValueError, TypeError):
        return settings.CAPACITY_WARN_RATIO


def _day_bounds(d: date):
    start = datetime.combine(d, datetime.min.time())
    return start, start + timedelta(days=1)


@router.get("/admin/stats/dashboard")
def dashboard(admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    """B端首页统计 + 数据看板。"""
    today = date.today()
    start, end = _day_bounds(today)

    venue = db.query(VenueInfo).first()
    daily_max = venue.max_daily if venue else 5000

    # 当日预约
    booked_today = (db.query(Reservation).filter(
        Reservation.visit_date == today,
        Reservation.status.in_(("booked", "checked_in"))).count())
    visitors_today = (db.query(func.coalesce(func.sum(Reservation.visitor_count), 0))
                      .filter(Reservation.visit_date == today,
                              Reservation.status.in_(("booked", "checked_in")))
                      .scalar())
    checked_today = (db.query(Reservation).filter(
        Reservation.visit_date == today, Reservation.status == "checked_in").count())
    cancelled_today = (db.query(Reservation).filter(
        Reservation.visit_date == today, Reservation.status == "cancelled").count())
    no_show_today = (db.query(Reservation).filter(
        Reservation.visit_date == today, Reservation.status == "no_show").count())

    # 实时在馆人数 = 通行日志 in - out (对账基准)
    inflow = (db.query(func.count(AccessLog.id)).filter(
        AccessLog.direction == "in",
        AccessLog.pass_time >= start, AccessLog.pass_time < end).scalar())
    outflow = (db.query(func.count(AccessLog.id)).filter(
        AccessLog.direction == "out",
        AccessLog.pass_time >= start, AccessLog.pass_time < end).scalar())
    in_venue = int(inflow) - int(outflow)

    # 周期统计
    def period_stat(days: int):
        s = datetime.combine(today - timedelta(days=days - 1), datetime.min.time())
        total = (db.query(func.coalesce(func.sum(Reservation.visitor_count), 0))
                 .filter(Reservation.visit_date >= s.date(),
                         Reservation.visit_date <= today,
                         Reservation.status.in_(("booked", "checked_in"))).scalar())
        checked = (db.query(func.coalesce(func.sum(Reservation.visitor_count), 0))
                   .filter(Reservation.visit_date >= s.date(),
                           Reservation.visit_date <= today,
                           Reservation.status == "checked_in").scalar())
        return int(total or 0), int(checked or 0)

    week_total, week_checked = period_stat(7)
    month_total, month_checked = period_stat(30)

    # 时段分布(当日, 按通行日志)
    slot_dist = []
    for s in db.query(SessionSlot).filter(SessionSlot.is_active == 1).order_by(SessionSlot.start_time):
        cnt = (db.query(func.count(AccessLog.id)).filter(
            AccessLog.direction == "in",
            AccessLog.pass_time >= datetime.combine(today, s.start_time),
            AccessLog.pass_time <= datetime.combine(today, s.end_time)).scalar())
        slot_dist.append({"session": s.name, "count": int(cnt)})

    # 最近7日预约/核销趋势
    trend = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        t, c = (db.query(func.coalesce(func.sum(Reservation.visitor_count), 0),
                         func.sum(func.if_(Reservation.status == "checked_in",
                                           Reservation.visitor_count, 0)))
                .filter(Reservation.visit_date == d).first())
        trend.append({"date": str(d), "booked": int(t or 0), "checked": int(c or 0)})

    warn_ratio = _warn_ratio(db)
    return ok({
        "realtime": {
            "in_venue": in_venue,
            "inflow_today": int(inflow),
            "outflow_today": int(outflow),
            "daily_max": daily_max,
            "usage_ratio": round(in_venue / daily_max, 4) if daily_max else 0,
            "warning": in_venue >= daily_max * warn_ratio,
            "warn_ratio": warn_ratio,
        },
        "today": {
            "resv_count": booked_today,
            "visitor_count": int(visitors_today or 0),
            "checked_count": checked_today,
            "cancelled": cancelled_today,
            "no_show": no_show_today,
            "checkin_rate": round(checked_today / booked_today, 4) if booked_today else 0,
            "noshow_rate": round(no_show_today / booked_today, 4) if booked_today else 0,
        },
        "week": {"total": week_total, "checked": week_checked,
                 "rate": round(week_checked / week_total, 4) if week_total else 0},
        "month": {"total": month_total, "checked": month_checked,
                  "rate": round(month_checked / month_total, 4) if month_total else 0},
        "slot_distribution": slot_dist,
        "trend_7d": trend,
    })


@router.get("/admin/stats/reservations")
def resv_stats(
    page: int = 1, size: int = 20, date_str: str | None = None,
    status: str | None = None, keyword: str | None = None,
    admin=Depends(get_current_admin), db: Session = Depends(get_db),
):
    """预约明细(含游客脱敏信息)。"""
    page = max(1, page)
    size = min(max(1, size), 200)  # 防超大size拖库
    q = db.query(Reservation)
    if date_str:
        q = q.filter(Reservation.visit_date == date.fromisoformat(date_str))
    if status:
        q = q.filter(Reservation.status == status)
    # 关键词匹配预约码 / 手机号(脱敏) / 游客姓名与证件(脱敏)
    # 必须在分页前于DB过滤, 否则 total 与实际结果不符, 且跨页命中项永远查不到
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(or_(
            Reservation.resv_code.like(like),
            Reservation.user_id.in_(
                db.query(WxUser.id).filter(WxUser.phone_masked.like(like))),
            Reservation.id.in_(
                db.query(ReservationVisitor.reservation_id).filter(or_(
                    ReservationVisitor.real_name_masked.like(like),
                    ReservationVisitor.id_card_masked.like(like)))),
        ))
    total = q.count()
    items = (q.order_by(Reservation.id.desc())
             .offset((page - 1) * size).limit(size).all())
    slots = {s.id: s for s in db.query(SessionSlot).all()}
    out = []
    for r in items:
        s = slots.get(r.session_id)
        visitors = db.query(ReservationVisitor).filter_by(reservation_id=r.id).all()
        user = db.query(WxUser).get(r.user_id)
        out.append({
            "id": r.id, "resv_code": r.resv_code,
            "user_phone": user.phone_masked if user else "",
            "visit_date": str(r.visit_date),
            "session_name": s.name if s else "",
            "visitor_count": r.visitor_count, "status": r.status,
            "checked_in_at": str(r.checked_in_at or ""),
            "checked_out_at": str(r.checked_out_at or ""),
            "created_at": str(r.created_at),
            "visitors": [{"name": v.real_name_masked, "id_card": v.id_card_masked,
                          "checked_in": bool(v.checked_in)} for v in visitors],
        })
    return ok({"total": total, "items": out})


@router.get("/admin/stats/hourly")
def hourly_stats(date_str: str | None = None, admin=Depends(get_current_admin),
                 db: Session = Depends(get_db)):
    """按小时通行分布(客流峰值预警用)。"""
    d = date.fromisoformat(date_str) if date_str else date.today()
    start, end = _day_bounds(d)
    rows = (db.query(func.hour(AccessLog.pass_time).label("h"),
                     AccessLog.direction, func.count(AccessLog.id))
            .filter(AccessLog.pass_time >= start, AccessLog.pass_time < end)
            .group_by("h", AccessLog.direction).all())
    hour_map: dict[int, dict] = {}
    for h, direction, cnt in rows:
        hour_map.setdefault(int(h), {"hour": int(h), "in": 0, "out": 0})
        hour_map[int(h)]["in" if direction == "in" else "out"] = int(cnt)
    return ok(sorted(hour_map.values(), key=lambda x: x["hour"]))


# ============ 数据导出(CSV, 需求 2.2 系统管理员) ============
import csv
import io

from fastapi.responses import StreamingResponse

from app.core.deps import require_admin


@router.get("/admin/stats/export/reservations")
def export_reservations(date_str: str | None = None,
                        admin=Depends(require_admin), db: Session = Depends(get_db)):
    """导出预约明细CSV(脱敏, BOM兼容Excel)。"""
    q = db.query(Reservation)
    if date_str:
        q = q.filter(Reservation.visit_date == date.fromisoformat(date_str))
    rows = q.order_by(Reservation.id.desc()).limit(50000).all()
    slots = {s.id: s for s in db.query(SessionSlot).all()}

    buf = io.StringIO()
    buf.write("\ufeff")  # Excel BOM
    w = csv.writer(buf)
    w.writerow(["预约码", "参观日期", "时段", "人数", "状态",
                "核销时间", "出馆时间", "创建时间", "游客(脱敏)"])
    for r in rows:
        s = slots.get(r.session_id)
        visitors = db.query(ReservationVisitor).filter_by(reservation_id=r.id).all()
        v_str = "; ".join(f"{v.real_name_masked}({v.id_card_masked})" for v in visitors)
        w.writerow([r.resv_code, r.visit_date, s.name if s else "",
                    r.visitor_count, r.status,
                    r.checked_in_at or "", r.checked_out_at or "",
                    r.created_at, v_str])
    buf.seek(0)
    filename = f"reservations_{date_str or 'all'}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/admin/stats/export/access")
def export_access(date_str: str | None = None,
                  admin=Depends(require_admin), db: Session = Depends(get_db)):
    """导出通行日志CSV(对账基准)。"""
    q = db.query(AccessLog)
    if date_str:
        d = date.fromisoformat(date_str)
        start, end = _day_bounds(d)
        q = q.filter(AccessLog.pass_time >= start, AccessLog.pass_time < end)
    rows = q.order_by(AccessLog.pass_time.desc()).limit(100000).all()

    buf = io.StringIO()
    buf.write("\ufeff")
    w = csv.writer(buf)
    w.writerow(["日志ID", "预约ID", "闸机", "方向", "过闸时间", "离线补传"])
    for r in rows:
        w.writerow([r.id, r.reservation_id or "", r.gate_id, r.direction,
                    r.pass_time, "是" if r.synced_offline else "否"])
    buf.seek(0)
    filename = f"access_{date_str or 'all'}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"})


# ============ 爽约标记(需求: 爽约率统计来源) ============
from pydantic import BaseModel as _BaseModel


class NoShowReq(_BaseModel):
    date_str: str | None = None  # 默认昨天


@router.post("/admin/stats/mark-noshow")
def mark_noshow(req: NoShowReq, admin=Depends(require_admin)):
    """当日结束后将未核销预约标记为爽约(定时任务手动触发口)。"""
    from app.services.no_show import mark_no_shows
    d = date.fromisoformat(req.date_str) if req.date_str else \
        date.today() - timedelta(days=1)
    result = mark_no_shows(d)
    return ok(result)
