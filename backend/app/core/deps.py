"""FastAPI 依赖: 后台JWT鉴权 / 角色控制 / C端模拟微信登录态。"""
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.core.response import BizError, E_UNAUTHORIZED, E_FORBIDDEN
from app.models.models import AdminUser


ADMIN_ROLES = ("admin", "operator")


def get_current_admin(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
) -> AdminUser:
    if not authorization.startswith("Bearer "):
        raise BizError(E_UNAUTHORIZED, "未登录或token缺失")
    payload = decode_token(authorization[7:])
    if not payload:
        raise BizError(E_UNAUTHORIZED, "token无效或已过期")
    # 必须校验token身份域: C端token(role=wx_user)与后台token共用同一签名密钥,
    # 若只比对 sub 是否命中 AdminUser.id, 则 C端用户id与后台账号id撞号即可越权。
    if payload.get("role") not in ADMIN_ROLES:
        raise BizError(E_UNAUTHORIZED, "token无效或已过期")
    try:
        admin_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise BizError(E_UNAUTHORIZED, "token无效或已过期")
    admin = db.query(AdminUser).filter(
        AdminUser.id == admin_id, AdminUser.status == 1
    ).first()
    if not admin:
        raise BizError(E_UNAUTHORIZED, "账号不存在或已禁用")
    return admin


def require_admin(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
    """仅系统管理员可访问。"""
    if admin.role != "admin":
        raise BizError(E_FORBIDDEN, "需要系统管理员权限")
    return admin


def get_wx_user_id(x_wx_openid: str = Header(default="")) -> str:
    """C端用户身份: 小程序通过网关换取token, Demo直接以header传递openid。

    生产环境应替换为微信 code2session + JWT。
    """
    if not x_wx_openid:
        raise BizError(E_UNAUTHORIZED, "缺少C端用户身份")
    return x_wx_openid
