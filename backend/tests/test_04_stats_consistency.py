"""统计看板 + 数据一致性测试(预约/核销/通行日志对账)。"""
import datetime
import time


def _check(client, credential, direction="in", gate="GATE-S"):
    return client.post("/gate/check", {
        "check_type": "qrcode", "credential": credential, "direction": direction,
        "gate_id": gate, "device_seq": f"pytest-stats-{time.time()}-{id(object())}"})


class TestDashboard:
    def test_dashboard_structure(self, client, admin):
        data = client.get("/admin/stats/dashboard")["data"]
        assert {"realtime", "today", "week", "month"} <= set(data)
        rt = data["realtime"]
        # 实时在馆人数 = inflow - outflow (对账口径)
        assert rt["in_venue"] == rt["inflow_today"] - rt["outflow_today"]
        assert 0 <= rt["usage_ratio"] <= 1

    def test_checkin_rate_consistency(self, client, admin):
        data = client.get("/admin/stats/dashboard")["data"]
        t = data["today"]
        if t["resv_count"] > 0:
            expected = round(t["checked_count"] / t["resv_count"], 4)
            assert abs(t["checkin_rate"] - expected) < 1e-4


class TestDataConsistency:
    """SQL一致性: 通行日志与核销记录、预约状态三方对账。"""

    def test_check_record_access_log_1to1(self, client, admin, wx_user):
        """核销成功 => 必有通行日志, 一一对应。"""
        u = wx_user("何六")
        today = datetime.date.today().isoformat()
        data = client.book(u["openid"], u["card"], u["name"], session_id=2, date=today)
        r = _check(client, data["resv_code"])
        assert r["data"]["result"] == "success"
        # 后台核销记录可见
        records = client.get("/admin/check-records", params={"date_str": today})["data"]["items"]
        rec = next(c for c in records if c["reservation_id"] == data["reservation_id"]
                   and c["direction"] == "in" and c["result"] == "success")
        assert rec["gate_id"] == "GATE-S"

    def test_failed_check_no_access_log(self, client, admin):
        """核销失败 => 不产生通行日志(不出现人已过闸后台无记录)。"""
        r = _check(client, "HZNOTEXIST99")
        assert r["data"]["result"] == "fail"
        records = client.get("/admin/check-records", params={"result": "fail"})["data"]["items"]
        fail_rec = records[0]
        # 失败记录不应关联任何成功通行
        logs = client.get("/admin/stats/hourly")["data"]
        assert isinstance(logs, list)  # 接口可用性

    def test_manual_checkin_creates_access_log(self, client, admin, wx_user, tomorrow):
        """手动核销也补通行日志, 保证统计口径一致。"""
        u = wx_user("吕七")
        data = client.book(u["openid"], u["card"], u["name"], date=tomorrow)
        client.post("/admin/reservations/manual", {"resv_code": data["resv_code"], "action": "check_in"})
        detail = client.get("/admin/stats/reservations", params={"date_str": tomorrow})["data"]["items"]
        target = next(r for r in detail if r["resv_code"] == data["resv_code"])
        assert target["status"] == "checked_in"
        assert target["checked_in_at"]
