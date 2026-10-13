"""SQLAlchemy ORM 模型(与 sql/schema.sql 一一对应)。"""
from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, DateTime, Date, Time,
    SmallInteger, VARBINARY, JSON, Index, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class AdminUser(Base):
    __tablename__ = "admin_user"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(128), nullable=False)
    real_name = Column(String(50), nullable=False, default="")
    role = Column(String(20), nullable=False, default="operator")  # admin/operator
    status = Column(SmallInteger, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class WxUser(Base):
    __tablename__ = "wx_user"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    openid = Column(String(64), unique=True, nullable=False)
    unionid = Column(String(64), nullable=True)
    nickname = Column(String(64), nullable=False, default="")
    real_name = Column(String(128), nullable=True)          # AES+Base64
    id_card_no = Column(String(128), nullable=True)         # 哈希(索引列)
    id_card_enc = Column(String(255), nullable=True)        # AES加密Base64
    id_card_masked = Column(String(20), nullable=True)
    phone_enc = Column(String(255), nullable=True)
    phone_masked = Column(String(20), nullable=True)
    is_verified = Column(SmallInteger, nullable=False, default=0)
    is_blacklisted = Column(SmallInteger, nullable=False, default=0)
    blacklist_reason = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class VenueInfo(Base):
    __tablename__ = "venue_info"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    address = Column(String(200), nullable=False, default="")
    open_time = Column(String(100), nullable=False, default="")
    traffic_guide = Column(Text)
    notice = Column(Text)
    max_daily = Column(Integer, nullable=False, default=5000)
    status = Column(SmallInteger, nullable=False, default=1)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class SessionSlot(Base):
    __tablename__ = "session_slot"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    capacity = Column(Integer, nullable=False)
    is_active = Column(SmallInteger, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.now)


class Exhibit(Base):
    __tablename__ = "exhibit"
    id = Column(Integer, primary_key=True, autoincrement=True)
    hall_name = Column(String(100), nullable=False, index=True)
    title = Column(String(100), nullable=False)
    description = Column(Text)
    media_type = Column(String(20), nullable=False, default="image")
    media_url = Column(String(500), nullable=True)
    is_special = Column(SmallInteger, nullable=False, default=0)   # 1=特殊展项(付费可预约体验)
    price_cent = Column(Integer, nullable=False, default=0)        # 体验单价(分)
    capacity = Column(Integer, nullable=False, default=0)          # 每时段可体验人数
    sort_order = Column(Integer, nullable=False, default=0)
    status = Column(SmallInteger, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Announcement(Base):
    __tablename__ = "announcement"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    type = Column(String(20), nullable=False, default="notice")
    is_published = Column(SmallInteger, nullable=False, default=0)
    publish_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Reservation(Base):
    __tablename__ = "reservation"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    resv_code = Column(String(12), unique=True, nullable=False)
    user_id = Column(BigInteger, nullable=False, index=True)
    visit_date = Column(Date, nullable=False)
    session_id = Column(Integer, nullable=False)
    visitor_count = Column(SmallInteger, nullable=False, default=1)
    status = Column(String(20), nullable=False, default="booked", index=True)
    checked_in_at = Column(DateTime, nullable=True)
    check_in_gate = Column(String(30), nullable=True)
    checked_out_at = Column(DateTime, nullable=True)
    cancel_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_date", "visit_date", "session_id", "status"),
    )


class ReservationVisitor(Base):
    __tablename__ = "reservation_visitor"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    reservation_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=True)
    real_name = Column(String(128), nullable=False)           # AES+Base64
    real_name_masked = Column(String(64), nullable=False, default="")
    id_card_no = Column(String(64), nullable=False)           # sha256哈希
    id_card_masked = Column(String(20), nullable=False)
    checked_in = Column(SmallInteger, nullable=False, default=0)
    checked_in_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("reservation_id", "id_card_no", name="uk_resv_idcard"),
    )


class CheckRecord(Base):
    __tablename__ = "check_record"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    check_type = Column(String(20), nullable=False)      # qrcode/idcard
    credential = Column(String(128), nullable=False)
    reservation_id = Column(BigInteger, nullable=True, index=True)
    visitor_id = Column(BigInteger, nullable=True)
    user_id = Column(BigInteger, nullable=True)
    direction = Column(String(10), nullable=False, default="in")
    result = Column(String(20), nullable=False)          # success/fail
    fail_reason = Column(String(100), nullable=True)
    gate_id = Column(String(30), nullable=False)
    device_seq = Column(String(64), nullable=True)
    synced_offline = Column(SmallInteger, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("gate_id", "device_seq", name="uk_device_seq"),
    )


class AccessLog(Base):
    __tablename__ = "access_log"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    reservation_id = Column(BigInteger, nullable=True, index=True)
    user_id = Column(BigInteger, nullable=True)
    visitor_id = Column(BigInteger, nullable=True)
    gate_id = Column(String(30), nullable=False)
    direction = Column(String(10), nullable=False)
    pass_time = Column(DateTime, nullable=False, index=True)
    check_record_id = Column(BigInteger, nullable=True)
    synced_offline = Column(SmallInteger, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.now)


class OfflineSyncQueue(Base):
    __tablename__ = "offline_sync_queue"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    gate_id = Column(String(30), nullable=False)
    device_seq = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    retry_count = Column(Integer, nullable=False, default=0)
    synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("gate_id", "device_seq", name="uk_gate_seq"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    admin_id = Column(Integer, nullable=True)
    admin_name = Column(String(50), nullable=False, default="")
    action = Column(String(50), nullable=False)
    detail = Column(String(500), nullable=False, default="")
    ip = Column(String(50), nullable=False, default="")
    created_at = Column(DateTime, default=datetime.now)


class SysConfig(Base):
    __tablename__ = "sys_config"
    cfg_key = Column(String(50), primary_key=True)
    cfg_value = Column(String(500), nullable=False)
    remark = Column(String(200), nullable=False, default="")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ResvDailyLimit(Base):
    __tablename__ = "resv_daily_limit"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    id_card_no = Column(String(64), nullable=False)
    visit_date = Column(Date, nullable=False)
    resv_count = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("id_card_no", "visit_date", name="uk_card_date"),
    )


class ExhibitReservation(Base):
    """特殊展项预约(付费体验): 须先有当日入馆预约, 模拟支付闭环。"""
    __tablename__ = "exhibit_reservation"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    resv_code = Column(String(12), unique=True, nullable=False)
    exhibit_id = Column(Integer, nullable=False)
    user_id = Column(BigInteger, nullable=False, index=True)
    visit_date = Column(Date, nullable=False)
    session_id = Column(Integer, nullable=False)
    person_count = Column(SmallInteger, nullable=False, default=1)
    amount_cent = Column(Integer, nullable=False, default=0)
    pay_status = Column(String(20), nullable=False, default="unpaid")
    paid_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="booked")
    checked_in_count = Column(SmallInteger, nullable=False, default=0)
    cancel_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
