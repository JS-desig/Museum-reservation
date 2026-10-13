import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "菏泽市科技博物馆预约与门禁系统"
    # MySQL 5.7 @ localhost
    DB_HOST: str = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "1234")
    DB_NAME: str = os.getenv("DB_NAME", "heze_museum")

    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "heze-museum-secret-change-in-prod")
    JWT_EXPIRE_MINUTES: int = 720

    # 实名字段 AES 加密密钥(16字节)
    AES_KEY: bytes = b"HeZeMuseum2026KB"

    # 防刷: 同证件同日最多预约次数 / 单笔最大同行人数 / 提前取消时限(分钟)
    MAX_RESV_PER_CARD_PER_DAY: int = 2
    MAX_VISITORS_PER_RESV: int = 5
    CANCEL_BEFORE_MINUTES: int = 30

    # 客流预警阈值比例
    CAPACITY_WARN_RATIO: float = 0.9


settings = Settings()

DATABASE_URL = (
    f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}?charset=utf8mb4"
)
