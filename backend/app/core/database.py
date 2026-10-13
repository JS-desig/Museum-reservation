"""数据库连接管理: SQLAlchemy Engine + aiomysql 兼容的同步会话工厂。

FastAPI 依赖注入通过 get_db 提供会话; 事务边界由调用方(服务层)控制,
保证「预约扣减名额 + 明细写入 + 限次计数」在同一事务内强一致。
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=1800,
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
