"""轻量内存限流: 滑动窗口按 key 计数, 兜底防刷(单实例部署适用)。

对应需求错误码 42900(请求过于频繁)。网关层限流(需求 SEC-010)之外的应用层防线。
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.response import BizError, E_RATE_LIMIT

_windows: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()

# 定期清理防内存增长: 每10万次请求清理一次过期key
_counter = 0
_CLEANUP_EVERY = 100_000


def rate_limit(times: int, per_seconds: float, key: str):
    """超出 `times` 次/`per_seconds`秒 窗口则抛 42900。"""
    global _counter
    now = time.monotonic()
    with _lock:
        q = _windows[key]
        cutoff = now - per_seconds
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= times:
            raise BizError(E_RATE_LIMIT, f"请求过于频繁, 请{int(per_seconds)}秒后重试")
        q.append(now)
        _counter += 1
        if _counter >= _CLEANUP_EVERY:
            stale = [k for k, v in _windows.items() if not v or v[-1] < cutoff]
            for k in stale:
                _windows.pop(k, None)
            _counter = 0


def client_ip(request: Request) -> str:
    """取客户端IP(支持反向代理 X-Forwarded-For 首跳)。"""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
