"""后台认证 + C端用户认证与实名模块。"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin, get_wx_user_id
from app.core.security import (
    verify_password, create_token, aes_encrypt, aes_decrypt,
    validate_id_card, hash_id_card, mask_id_card, mask_name, mask_phone,
    check_nonce,
)
from app.core.response import ok, BizError, E_PARAM, E_UNAUTHORIZED, E_FORBIDDEN
from app.core.ratelimit import rate_limit, client_ip
from app.models.models import AdminUser, WxUser, AuditLog

router = APIRouter()


# ============ B端后台登录 ============
class AdminLoginReq(BaseModel):
    username: str
    password: str


@router.post("/admin/login")
def admin_login(req: AdminLoginReq, request: Request, db: Session = Depends(get_db)):
    # 防爆破: 同IP每分钟最多20次登录尝试
    rate_limit(20, 60, f"login:{client_ip(request)}")
    admin = db.query(AdminUser).filter_by(username=req.username).first()
    if not admin or not verify_password(req.password, admin.password):
        raise BizError(E_UNAUTHORIZED, "用户名或密码错误")
    if admin.status != 1:
        raise BizError(E_FORBIDDEN, "账号已禁用")
    token = create_token(admin.id, admin.username, admin.role)
    db.add(AuditLog(admin_id=admin.id, admin_name=admin.username,
                    action="login", detail="后台登录"))
    return ok({"token": token, "id": admin.id, "username": admin.username,
               "real_name": admin.real_name, "role": admin.role})


@router.get("/admin/me")
def admin_me(admin: AdminUser = Depends(get_current_admin)):
    return ok({"id": admin.id, "username": admin.username,
               "real_name": admin.real_name, "role": admin.role})


# ============ C端微信登录(模拟 code2session) ============
class WxLoginReq(BaseModel):
    code: str = Field(..., description="wx.login获取的code, Demo中直接作为openid使用")
    nickname: str = ""


@router.post("/wx/login")
def wx_login(req: WxLoginReq, request: Request, db: Session = Depends(get_db)):
    """Demo: code 即 openid。生产环境在此调用微信 code2session 接口换openid。"""
    # 防刷: 同IP每分钟最多30次登录
    rate_limit(30, 60, f"wxlogin:{client_ip(request)}")
    openid = req.code
    user = db.query(WxUser).filter_by(openid=openid).first()
    if not user:
        user = WxUser(openid=openid, nickname=req.nickname or "游客")
        db.add(user)
        db.commit()
    token = create_token(user.id, openid, "wx_user")
    return ok({"token": token, "user_id": user.id, "is_verified": bool(user.is_verified)})


# ============ C端实名绑定 ============
class VerifyRealNameReq(BaseModel):
    real_name: str
    id_card_no: str
    phone: str


@router.post("/wx/realname")
def bind_realname(
    req: VerifyRealNameReq,
    openid: str = Depends(get_wx_user_id),
    db: Session = Depends(get_db),
):
    if not validate_id_card(req.id_card_no):
        raise BizError(E_PARAM, "身份证号校验位错误")
    if not (req.phone.isdigit() and len(req.phone) == 11):
        raise BizError(E_PARAM, "手机号格式错误")
    if not req.real_name.strip():
        raise BizError(E_PARAM, "姓名不能为空")

    user = db.query(WxUser).filter_by(openid=openid).first()
    if not user:
        raise BizError(E_UNAUTHORIZED, "用户不存在")

    # 实名信息加密存储, 仅保留脱敏展示字段
    user.real_name = aes_encrypt(req.real_name.strip())
    user.id_card_no = hash_id_card(req.id_card_no)
    user.id_card_enc = aes_encrypt(req.id_card_no.upper())
    user.id_card_masked = mask_id_card(req.id_card_no.upper())
    user.phone_enc = aes_encrypt(req.phone)
    user.phone_masked = mask_phone(req.phone)
    user.is_verified = 1
    return ok({"user_id": user.id, "is_verified": True})


@router.get("/wx/profile")
def wx_profile(openid: str = Depends(get_wx_user_id), db: Session = Depends(get_db)):
    user = db.query(WxUser).filter_by(openid=openid).first()
    if not user:
        raise BizError(E_UNAUTHORIZED, "用户不存在")
    return ok({
        "user_id": user.id,
        "nickname": user.nickname,
        "is_verified": bool(user.is_verified),
        "real_name": aes_decrypt(user.real_name) if user.real_name else None,
        "id_card_masked": user.id_card_masked,
        "phone_masked": user.phone_masked,
        "is_blacklisted": bool(user.is_blacklisted),
        "blacklist_reason": user.blacklist_reason,
    })
