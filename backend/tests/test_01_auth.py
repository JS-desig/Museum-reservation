"""认证与实名模块测试。"""
import pytest


class TestAdminAuth:
    def test_login_ok(self, client):
        body = client.post("/admin/login", {"username": "admin", "password": "admin123"})
        assert body["data"]["token"]
        assert body["data"]["role"] == "admin"

    def test_login_wrong_password(self, client):
        body = client.post("/admin/login", {"username": "admin", "password": "bad"},
                           expect_code=40100)
        assert "错误" in body["message"]

    def test_me_requires_token(self, client):
        client.request("GET", "/admin/me", expect_code=40100,
                       headers={"Authorization": ""})

    def test_me_with_token(self, client, admin):
        body = client.get("/admin/me")
        assert body["data"]["username"] == "admin"


class TestWxAuth:
    def test_wx_login_creates_user(self, client):
        openid = f"wx_t_{id(object())}"
        body = client.post("/wx/login", {"code": openid, "nickname": "A"})
        assert body["data"]["is_verified"] is False

    def test_realname_bad_checksum(self, client):
        openid = f"wx_t_{id(object())}"
        client.post("/wx/login", {"code": openid})
        body = client.post("/wx/realname",
                           {"real_name": "张三", "id_card_no": "110101199003078679", "phone": "13800000000"},
                           expect_code=40000, headers={"X-Wx-Openid": openid})
        assert "校验位" in body["message"]

    def test_realname_bad_phone(self, client, new_card):
        openid = f"wx_t_{id(object())}"
        client.post("/wx/login", {"code": openid})
        client.post("/wx/realname",
                    {"real_name": "张三", "id_card_no": new_card, "phone": "123"},
                    expect_code=40000, headers={"X-Wx-Openid": openid})

    def test_realname_then_profile_masked(self, client, new_card):
        openid = f"wx_t_{id(object())}"
        client.post("/wx/login", {"code": openid})
        client.post("/wx/realname",
                    {"real_name": "张三", "id_card_no": new_card, "phone": "13812345678"},
                    headers={"X-Wx-Openid": openid})
        profile = client.get("/wx/profile", headers={"X-Wx-Openid": openid})["data"]
        assert profile["is_verified"] is True
        assert profile["real_name"] == "张三"
        assert profile["id_card_masked"].startswith(new_card[:4])
        assert "*" in profile["id_card_masked"]
        assert "138****5678" == profile["phone_masked"]
        assert new_card not in str(profile)  # 完整证件号不外泄
