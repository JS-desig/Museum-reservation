"""B端预约查询过滤 + 管理接口回归测试。

回归缺陷:
- 预约明细 keyword 过滤曾在分页后应用: total 与实际结果不符, 且非首页命中项查不到;
- 前端预约管理页日期参数名为 date(后端期望 date_str), 日期筛选静默失效。
"""
import datetime
import time


def _resv_page(client, **params):
    return client.get("/admin/stats/reservations", params=params)["data"]


class TestReservationQueryFilter:
    def test_keyword_matches_total_and_item(self, client, admin):
        """按预约码精确搜索: total 收敛为命中数, 且结果含该单。"""
        code = _resv_page(client, size=5)["items"][0]["resv_code"]
        data = _resv_page(client, keyword=code)
        assert data["total"] == 1, f"关键词命中 total 应为1, 实际{data['total']}"
        assert [i["resv_code"] for i in data["items"]] == [code]

    def test_keyword_no_match_returns_empty(self, client, admin):
        """无匹配关键词: total=0 且列表为空(修复前 total 为全表总数)。"""
        data = _resv_page(client, keyword="ZZZZZZZZZZZZ")
        assert data["total"] == 0, f"无匹配时 total 应为0, 实际{data['total']}"
        assert data["items"] == []

    def test_keyword_cross_page(self, client, admin):
        """非首页的记录也能被关键词查到(分页前过滤的核心回归)。"""
        total = _resv_page(client, size=20)["total"]
        if total <= 20:
            return  # 数据量不足, 无法构造跨页场景
        last_page = (total - 1) // 20 + 1
        deep = _resv_page(client, page=last_page, size=20)["items"][-1]["resv_code"]
        data = _resv_page(client, keyword=deep)
        assert data["total"] == 1
        assert any(i["resv_code"] == deep for i in data["items"]), \
            f"深页记录 {deep} 未被关键词命中(分页后过滤缺陷)"

    def test_keyword_by_masked_visitor_name(self, client, admin):
        """支持按游客脱敏姓名模糊搜索。"""
        first = _resv_page(client, size=5)["items"][0]
        name = first["visitors"][0]["name"]
        data = _resv_page(client, keyword=name)
        assert data["total"] >= 1, f"按脱敏姓名 {name} 应至少命中1条"

    def test_date_filter_applies(self, client, admin, wx_user, tomorrow):
        """日期筛选只返回该日预约(回归前端 date/date_str 参数错配)。"""
        u = wx_user("筛选用例")
        client.book(u["openid"], u["card"], u["name"], date=tomorrow)
        data = _resv_page(client, date_str=tomorrow)
        assert data["total"] >= 1
        assert all(i["visit_date"] == tomorrow for i in data["items"]), \
            "日期筛选返回了其他日期的预约"


class TestManagementEndpoints:
    def test_gate_config_pull(self, client):
        """闸机启动拉取配置: 时段与服务器时间。"""
        data = client.get("/gate/config", params={"gate_id": "GATE-01"})["data"]
        assert data["gate_id"] == "GATE-01"
        assert data["slots"], "未下发时段配置"
        assert data["server_time"], "缺少服务器时间(闸机对时需要)"
        assert {"id", "name", "start", "end"} <= set(data["slots"][0])

    def test_wx_pass_records_after_checkin(self, client, wx_user):
        """个人中心历史通行记录: 核销后可见入馆记录。"""
        u = wx_user("通行记录")
        today = datetime.date.today().isoformat()
        data = client.book(u["openid"], u["card"], u["name"], session_id=2, date=today)
        client.post("/gate/check", {
            "check_type": "qrcode", "credential": data["resv_code"], "direction": "in",
            "gate_id": "GATE-HIST", "device_seq": f"hist-{time.time()}",
        })
        logs = client.get("/wx/pass-records", headers={"X-Wx-Openid": u["openid"]})["data"]
        assert any(l["reservation_id"] == data["reservation_id"] and l["direction"] == "in"
                   for l in logs), "核销后通行记录不可见"

    def test_audit_logs_record_admin_actions(self, client, admin):
        """审计日志: 后台操作留痕可查。"""
        client.put("/admin/venue", {"name": "菏泽市科技博物馆"})
        data = client.get("/admin/audit-logs")["data"]
        assert data["total"] > 0
        assert any(a["action"] == "venue_update" for a in data["items"]), \
            "场馆更新操作未写入审计日志"
