"""统一响应结构与业务异常。"""
from typing import Any
from fastapi import Request
from fastapi.responses import JSONResponse


class BizError(Exception):
    """业务异常: http状态码固定200, 由 code 区分。"""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


# 业务错误码
E_UNAUTHORIZED = 40100          # 未登录/token无效
E_FORBIDDEN = 40300             # 无权限
E_PARAM = 40000                 # 参数错误
E_NOT_FOUND = 40400
E_RESV_FULL = 50001             # 时段已满
E_RESV_LIMIT = 50002            # 超过单证件当日预约次数
E_RESV_DUPLICATE = 50003        # 同日同时段已有预约
E_RESV_CANCELLED = 50004        # 预约已取消
E_RESV_NOT_BOOKED = 50005       # 预约状态不允许该操作
E_CHECK_INVALID = 60001         # 无效预约码
E_CHECK_ALREADY = 60002         # 已核销(重复核销)
E_CHECK_NO_RESV = 60003         # 未预约
E_CHECK_WRONG_SESSION = 60004   # 错峰(不在预约时段)
E_CHECK_BLACKLIST = 60005       # 黑名单
E_CHECK_CANCELLED = 60006       # 预约已取消
E_CHECK_EXPIRED = 60007         # 预约已过期
E_RATE_LIMIT = 42900            # 请求过于频繁


def ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


def fail(code: int, message: str) -> dict:
    return {"code": code, "message": message, "data": None}


async def biz_error_handler(request: Request, exc: BizError) -> JSONResponse:
    return JSONResponse(status_code=200, content=fail(exc.code, exc.message))
