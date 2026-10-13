"""测试夹具: API客户端 + 身份证工厂 + 唯一数据。"""
import sys
import time
import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api_client import APIClient  # noqa: E402
from idcard import make_card  # noqa: E402,F401  (测试用例通过 conftest 引用)


@pytest.fixture()  # function级: 每用例独立XFF IP, 避免登录限流误伤测试
def client() -> APIClient:
    c = APIClient()
    # 健康检查: 服务未启动时快速失败并提示
    try:
        c.request("GET", "/health", expect_code=None)
    except Exception:
        pytest.fail("后端服务未启动: 请先运行 uvicorn app.main:app --port 8000")
    return c


@pytest.fixture()
def admin(client) -> dict:
    return client.admin_login()


_card_seq = [int(time.time() * 1000) % 100000000]


@pytest.fixture
def new_card() -> str:
    """每个用例获得唯一校验位合法身份证。"""
    _card_seq[0] += 1
    return make_card(_card_seq[0])


@pytest.fixture
def wx_user(client):
    """新建一个已实名的C端用户, 每次调用使用唯一身份证。"""
    made = []

    def _make(name="测试用户"):
        _card_seq[0] += 1
        card = make_card(_card_seq[0])
        openid = f"wx_py_{int(time.time()*1000)}_{len(made)}"
        client.post("/wx/login", {"code": openid, "nickname": name})
        client.post("/wx/realname", {"real_name": name, "id_card_no": card, "phone": "13800000000"},
                    headers={"X-Wx-Openid": openid})
        made.append(openid)
        return {"openid": openid, "card": card, "name": name}

    return _make


@pytest.fixture
def tomorrow() -> str:
    return (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
