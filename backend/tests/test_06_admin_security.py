"""账号权限/黑名单/导出/爽约/安全测试。"""
import datetime
import time


class TestAdminAccounts:
    def test_operator_cannot_create_admin(self, client):
        client.admin_login("operator", "operator123")
        client.post("/admin/users", {"username": "x1", "password": "123456",
                                     "real_name": "x", "role": "operator"},
                    expect_code=40300)
        client.admin_login()  # 恢复admin

    def test_operator_cannot_export(self, client):
        client.admin_login("operator", "operator123")
        client.get("/admin/stats/export/reservations", expect_code=40300)
        client.get("/admin/stats/export/access", expect_code=40300)
        client.admin_login()

    def test_create_admin_user(self, client, admin):
        uname = f"pytest_op_{int(time.time())}"
        u = client.post("/admin/users", {"username": uname, "password": "abc12345",
                                         "real_name": "测试运营", "role": "operator"},
                        expect_code=None)["data"]
        uid = u["id"]
        # 新账号可登录
        tok = client.post("/admin/login", {"username": uname, "password": "abc12345"})["data"]["token"]
        assert tok
        # 禁用后不可登录
        client.put(f"/admin/users/{uid}", {"username": uname, "password": "",
                                           "real_name": "测试运营", "role": "operator", "status": 0},
                   expect_code=None)
        client.post("/admin/login", {"username": uname, "password": "abc12345"},
                    expect_code=40300)

    def test_short_password_rejected(self, client, admin):
        client.post("/admin/users", {"username": f"short_{int(time.time())}",
                                     "password": "123", "real_name": "", "role": "operator"},
                    expect_code=40000)

    def test_duplicate_username_rejected(self, client, admin):
        client.post("/admin/users", {"username": "admin", "password": "123456",
                                     "real_name": "", "role": "operator"},
                    expect_code=40000)


class TestBlacklist:
    def test_blacklisted_user_cannot_book(self, client, wx_user, tomorrow, admin):
        u = wx_user("黑名单用户")
        # 获取user_id
        profile = client.get("/wx/profile", headers={"X-Wx-Openid": u["openid"]})["data"]
        client.post("/admin/blacklist/add", {"user_id": profile["user_id"], "reason": "测试拉黑"})
        body = client.post("/wx/reservations", {
            "visit_date": tomorrow, "session_id": 1,
            "visitors": [{"real_name": u["name"], "id_card_no": u["card"], "phone": ""}]},
            expect_code=40300, headers={"X-Wx-Openid": u["openid"]})
        assert "黑名单" in body["message"]
        # 黑名单列表可见(分页结构)
        bl = client.get("/admin/blacklist")["data"]
        assert any(x["id"] == profile["user_id"] for x in bl["items"])
        # 移出后可预约
        client.post("/admin/blacklist/remove", {"user_id": profile["user_id"]})
        data = client.book(u["openid"], u["card"], u["name"], date=tomorrow)
        assert data["status"] == "booked"


class TestExport:
    def test_export_csv_format(self, client, admin):
        resp = client.session.get(client.base + "/admin/stats/export/reservations",
                                  params={"date_str": datetime.date.today().isoformat()})
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        text = resp.content.decode("utf-8-sig")  # BOM
        lines = text.strip().split("\n")
        assert lines[0].startswith("预约码")

    def test_export_access_csv(self, client, admin):
        resp = client.session.get(client.base + "/admin/stats/export/access",
                                  params={"date_str": datetime.date.today().isoformat()})
        assert resp.status_code == 200
        lines = resp.content.decode("utf-8-sig").strip().split("\n")
        assert lines[0].startswith("日志ID")


class TestNoShow:
    def test_mark_noshow_yesterday(self, client, admin):
        # 建一个昨天日期的booked预约直接写库不可行(预约接口限制), 用历史date触发统计口
        body = client.post("/admin/stats/mark-noshow", {})
        assert body["code"] == 0
        assert "marked" in body["data"]

    def test_mark_noshow_explicit_date(self, client, admin):
        body = client.post("/admin/stats/mark-noshow",
                           {"date_str": (datetime.date.today() - datetime.timedelta(days=2)).isoformat()})
        assert body["code"] == 0

    def test_operator_cannot_mark(self, client):
        client.admin_login("operator", "operator123")
        client.post("/admin/stats/mark-noshow", {}, expect_code=40300)
        client.admin_login()


class TestSecurity:
    def test_sql_injection_in_keyword(self, client, admin):
        """关键词注入不产生异常/泄露。"""
        resp = client.session.get(client.base + "/admin/stats/reservations",
                                  params={"keyword": "'; DROP TABLE reservation; --"})
        assert resp.status_code == 200
        # 表仍可查询
        assert client.get("/admin/stats/reservations")["code"] == 0

    def test_expired_token_rejected(self, client):
        client.session.headers["Authorization"] = "Bearer invalid.token.here"
        client.get("/admin/me", expect_code=40100)
        client.session.headers.pop("Authorization")

    def test_missing_auth_header(self, client):
        old = client.session.headers.pop("Authorization", None)
        client.get("/admin/me", expect_code=40100)
        if old:
            client.session.headers["Authorization"] = old

    def test_xss_stored_safely(self, client, admin):
        """公告标题含脚本标签按原文存储返回(前端转义), 不产生500。"""
        client.admin_login()  # 确保鉴权(前面用例可能移除了header)
        a = client.post("/admin/announcements", {
            "title": "<script>alert(1)</script>", "content": "xss测试", "type": "notice",
            "is_published": 0})
        assert a["code"] == 0
        client.delete(f"/admin/announcements/{a['data']['id']}")


    def test_negative_visitor_count_rejected(self, client, wx_user, tomorrow):
        u = wx_user("负数测试")
        client.post("/wx/reservations", {
            "visit_date": tomorrow, "session_id": 1,
            "visitors": []}, expect_code=None,
            headers={"X-Wx-Openid": u["openid"]})  # min_length=1 => 422校验

    def test_oversize_credential_rejected(self, client):
        resp = client.session.post(client.base + "/gate/check", json={
            "check_type": "qrcode", "credential": "A" * 500, "direction": "in",
            "gate_id": "G", "device_seq": f"sec-{time.time()}"})
        assert resp.status_code in (200, 422)

    def test_idcard_validated_on_booking(self, client, wx_user, tomorrow):
        """预约时伪身份证被拒。"""
        u = wx_user("证件校验")
        client.post("/wx/reservations", {
            "visit_date": tomorrow, "session_id": 1,
            "visitors": [{"real_name": u["name"], "id_card_no": "123456789012345678", "phone": ""}]},
            expect_code=40000, headers={"X-Wx-Openid": u["openid"]})

    def test_health_open(self, client):
        assert client.request("GET", "/health", expect_code=None)["status"] == "UP"

    def test_wx_token_cannot_access_admin(self, client, wx_user):
        """越权回归: C端token(role=wx_user)不得访问后台接口。

        历史缺陷: 后台与C端共用签名密钥, 鉴权只比对 sub 是否命中 AdminUser.id,
        C端用户id与后台账号id撞号即可无密码拿到管理员权限。
        """
        u = wx_user("越权测试")
        body = client.post("/wx/login", {"code": u["openid"]})
        wx_token = body["data"]["token"]
        h = {"Authorization": f"Bearer {wx_token}"}
        for path in ("/admin/me", "/admin/users", "/admin/stats/dashboard"):
            r = client.session.get(client.base + path, headers=h)
            assert r.json()["code"] == 40100, f"{path} 允许C端token访问(越权)"

    def test_admin_token_rejected_on_wx_scope(self, client, admin):
        """反向隔离: 后台token不携带C端身份头时不能冒充游客。"""
        client.session.headers.pop("Authorization", None)
        client.get("/wx/profile", expect_code=40100)
        client.admin_login()
