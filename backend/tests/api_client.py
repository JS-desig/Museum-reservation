"""接口自动化测试公共封装: 带重试的请求客户端 + 统一断言。"""
import time
import functools
import requests

BASE_URL = "http://127.0.0.1:8000/api"
MAX_RETRIES = 3
RETRY_BACKOFF = 0.5  # 秒


def retry_on_error(max_retries: int = MAX_RETRIES):
    """请求失败自动重试(指数退避)。"""

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(max_retries):
                try:
                    return fn(*args, **kwargs)
                except (requests.ConnectionError, requests.Timeout) as e:
                    last_err = e
                    time.sleep(RETRY_BACKOFF * (2 ** attempt))
            raise last_err

        return wrapper

    return decorator


class APIClient:
    """统一API客户端: 业务断言(code==0)与HTTP状态分离。"""

    def __init__(self, base_url: str = BASE_URL):
        self.base = base_url
        self.session = requests.Session()
        # 每个客户端独立XFF IP, 避免测试共享127.0.0.1触发应用层限流
        self.session.headers["X-Forwarded-For"] = f"10.{id(self) % 255}.{id(self) // 255 % 255}.{id(self) // 65025 % 255}"

    @retry_on_error()
    def request(self, method: str, path: str, expect_code: int = 0, **kw) -> dict:
        resp = self.session.request(method, self.base + path, timeout=10, **kw)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"
        body = resp.json()
        if expect_code is not None:
            assert body["code"] == expect_code, \
                f"业务码 {body['code']} != {expect_code}: {body['message']}"
        return body

    def get(self, path, expect_code=0, **kw): return self.request("GET", path, expect_code, **kw)
    def post(self, path, json=None, expect_code=0, **kw): return self.request("POST", path, expect_code, json=json, **kw)
    def put(self, path, json=None, expect_code=0, **kw): return self.request("PUT", path, expect_code, json=json, **kw)
    def delete(self, path, expect_code=0, **kw): return self.request("DELETE", path, expect_code, **kw)

    # ---- 断言辅助 ----
    @staticmethod
    def assert_ok(body: dict):
        assert body["code"] == 0, body["message"]

    @staticmethod
    def assert_fail(body: dict, code: int):
        assert body["code"] == code, f"期望{code} 实际{body['code']}: {body['message']}"

    # ---- 便捷登录 ----
    def admin_login(self, username="admin", password="admin123") -> dict:
        body = self.post("/admin/login", {"username": username, "password": password})
        self.session.headers["Authorization"] = f"Bearer {body['data']['token']}"
        return body["data"]

    def wx_user(self, openid: str, real_name=None, id_card=None, phone="13800000000") -> dict:
        """创建/获取一个C端用户, 可选完成实名。返回 {openid, card}。"""
        self.post("/wx/login", {"code": openid, "nickname": "测试用户"})
        if real_name and id_card:
            self.post("/wx/realname", {"real_name": real_name, "id_card_no": id_card, "phone": phone},
                      headers={"X-Wx-Openid": openid})
        return {"openid": openid, "card": id_card}

    def book(self, openid: str, card: str, name: str, session_id=1, date=None, visitors=None) -> dict:
        """创建预约, 返回 data。"""
        import datetime
        d = date or (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        vs = visitors or [{"real_name": name, "id_card_no": card, "phone": "13800000000"}]
        return self.post("/wx/reservations", {"visit_date": d, "session_id": session_id, "visitors": vs},
                         headers={"X-Wx-Openid": openid})["data"]


# 有效的18位测试身份证(校验位正确)
VALID_CARD_M = "110101199003078670"
VALID_CARD_F = "110101199003078670"  # 同号不可复用, Faker生成器会构造新号
