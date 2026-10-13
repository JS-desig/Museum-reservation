"""定时任务: 爽约标记。当日结束后未核销的预约标记 no_show。

生产环境由 APScheduler/crontab 每晚触发; 本地可手动调接口。
"""
from datetime import date, datetime

from sqlalchemy import func

from app.core.database import SessionLocal
from app.models.models import Reservation, AuditLog


def mark_no_shows(target_date: date | None = None) -> dict:
    """将指定日期(默认昨天)仍未核销的 booked 预约标记为爽约。"""
    d = target_date or (datetime.now().date())
    db = SessionLocal()
    try:
        rows = (db.query(Reservation)
                .filter(Reservation.visit_date == d,
                        Reservation.status == "booked")
                .all())
        now = datetime.now()
        for r in rows:
            r.status = "no_show"
        db.add(AuditLog(action="no_show_mark",
                        detail=f"{d} 爽约标记 {len(rows)} 单"))
        db.commit()
        return {"date": str(d), "marked": len(rows)}
    finally:
        db.close()
