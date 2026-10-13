"""安全工具: 密码哈希、JWT、AES字段加密、身份证脱敏、防重放。"""
import hashlib
import hmac
import base64
import os
import time
import re
from datetime import datetime, timedelta

import bcrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jose import jwt, JWTError

from app.core.config import settings

# ---------- 密码 ----------
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


# ---------- JWT ----------
def create_token(user_id: int, username: str, role: str, expires_minutes: int | None = None) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=expires_minutes or settings.JWT_EXPIRE_MINUTES),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except JWTError:
        return None


# ---------- AES-GCM 字段级加密(Base64字符串存储, 兼容utf8 VARCHAR列) ----------
def _aes() -> AESGCM:
    return AESGCM(settings.AES_KEY)


def aes_encrypt(plain: str) -> str:
    nonce = os.urandom(12)
    data = nonce + _aes().encrypt(nonce, plain.encode("utf-8"), None)
    return base64.b64encode(data).decode("ascii")


def aes_decrypt(data: str | bytes) -> str:
    if isinstance(data, str):
        data = base64.b64decode(data)
    return _aes().decrypt(data[:12], data[12:], None).decode("utf-8")


# ---------- 身份证 ----------
_IDCARD_RE = re.compile(r"^\d{17}[\dXx]$")


def validate_id_card(no: str) -> bool:
    """18位身份证格式 + 校验位验证。"""
    if not _IDCARD_RE.match(no or ""):
        return False
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    codes = "10X98765432"
    s = sum(int(no[i]) * weights[i] for i in range(17))
    return codes[s % 11] == no[17].upper()


def hash_id_card(no: str) -> str:
    """身份证号哈希(用于等值查询与唯一约束), 加固定盐防彩虹表。"""
    return hmac.new(settings.AES_KEY, no.upper().encode(), hashlib.sha256).hexdigest()


def mask_id_card(no: str) -> str:
    return no[:4] + "**********" + no[-4:] if len(no) == 18 else "****"


def mask_name(name: str) -> str:
    if len(name) <= 1:
        return name
    return name[0] + "*" * (len(name) - 1)


def mask_phone(p: str) -> str:
    return p[:3] + "****" + p[-4:] if len(p) == 11 else "****"


# ---------- 防重放(nonce + 时间窗口) ----------
_nonce_store: dict[str, float] = {}
NONCE_TTL = 300


def check_nonce(nonce: str | None) -> bool:
    """首次出现返回True并记录; 5分钟窗口内重复返回False。"""
    if not nonce:
        return True  # 未带nonce的接口不校验
    now = time.time()
    # 清理过期
    expired = [k for k, t in _nonce_store.items() if now - t > NONCE_TTL]
    for k in expired:
        _nonce_store.pop(k, None)
    if nonce in _nonce_store:
        return False
    _nonce_store[nonce] = now
    return True


def gen_resv_code() -> str:
    """12位预约码: HZ + 毫秒时间戳hex(6位) + 4位随机。

    随机段先取模再定宽, 避免 urandom 超过4位时被末尾截断(截断会偏斜分布)。
    """
    ts = format(int(time.time() * 1000), "x")[-6:]
    rnd = format(int.from_bytes(os.urandom(2), "big") % 10000, "04d")
    return ("HZ" + ts + rnd).upper()
