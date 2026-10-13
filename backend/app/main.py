"""FastAPI 入口: 路由注册、异常处理、CORS。"""
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.response import biz_error_handler, BizError, fail, E_PARAM
from app.routers import auth, content, reservation, gate, stats, admin_manage, exhibit_resv

logger = logging.getLogger("heze")

app = FastAPI(
    title=settings.APP_NAME,
    description="C端小程序预约 + B端后台管理 + 闸机核销 + 数据看板 一体化API",
    version="1.0.0",
)

# CORS: B端前端 dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(BizError)
async def biz_error_handler_wrapper(request: Request, exc: BizError):
    return await biz_error_handler(request, exc)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """兜底: 未捕获异常统一500业务码, 不向客户端泄露堆栈。"""
    logger.exception("未捕获异常 %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content=fail(50000, "服务内部错误, 请稍后重试"))


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=200, content=fail(E_PARAM, f"参数校验失败: {exc.errors()[0]['msg']}"))


app.include_router(auth.router, prefix="/api", tags=["认证"])
app.include_router(content.router, prefix="/api", tags=["内容"])
app.include_router(reservation.router, prefix="/api", tags=["预约"])
app.include_router(gate.router, prefix="/api", tags=["闸机核销"])
app.include_router(stats.router, prefix="/api", tags=["统计看板"])
app.include_router(admin_manage.router, prefix="/api", tags=["账号管理"])
app.include_router(exhibit_resv.router, prefix="/api", tags=["特殊展项预约"])


# 展品图片等静态资源 (seed 数据 media_url 均为 /static/... 相对路径)
app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parents[1] / "static"), name="static")


@app.get("/api/health", tags=["系统"])
def health():
    return {"status": "UP", "app": settings.APP_NAME}
