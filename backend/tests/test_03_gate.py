"""闸机核销测试: 在线核销 / 幂等 / 异常凭证 / 离线补传。

重点覆盖需求3.3异常处理机制:
- 断网重连: 离线批量补传, device_seq幂等去重
- 指令延迟: 补传按pass_time落库
- 重复核销: 同seq幂等返回 / 不同seq业务拦截
"""
import datetime
import time


class TestGateCheck:
    def _check(self, client, credential, direction="in", ctype="qrcode", gate="GATE-A", seq=None):
        seq = seq or f"pytest-{time.time()}-{id(object())}"
        return client.post("/gate/check", {
            "check_type": ctype, "credential": credential, "direction": direction,
            "gate_id": gate, "device_seq": seq})

    def test_qr_checkin_success(self, client, wx_user):
        """当日预约 -> 扫码入馆成功。"""
        u = wx_user("钱八")
        today = datetime.date.today().isoformat()
        data = client.book(u["openid"], u["card"], u["name"], session_id=2, date=today)
        r = self._check(client, data["resv_code"])
        assert r["data"]["result"] == "success"
        assert r["data"]["gate_action"] == "open"

    def test_idcard_checkin_success(self, client, wx_user):
        """身份证核销通道。"""
        u = wx_user("陈九")
        today = datetime.date.today().isoformat()
        client.book(u["openid"], u["card"], u["name"], session_id=2, date=today)
        r = self._check(client, u["card"], ctype="idcard")
        assert r["data"]["result"] == "success"

    def test_duplicate_same_seq_idempotent(self, client, wx_user):
        """重复核销: 同device_seq幂等, 返回首次结果。"""
        u = wx_user("褚十")
        today = datetime.date.today().isoformat()
        data = client.book(u["openid"], u["card"], u["name"], session_id=2, date=today)
        seq = "pytest-dup-seq-001"
        r1 = self._check(client, data["resv_code"], seq=seq)
        r2 = self._check(client, data["resv_code"], seq=seq)
        assert r1["data"]["result"] == "success"
        assert r2["data"]["duplicate"] is True
        assert r2["data"]["record_id"] == r1["data"]["record_id"]

    def test_duplicate_diff_seq_rejected(self, client, wx_user):
        """重复核销: 不同device_seq也被业务拦截(60002)。"""
        u = wx_user("卫一")
        today = datetime.date.today().isoformat()
        data = client.book(u["openid"], u["card"], u["name"], session_id=2, date=today)
        self._check(client, data["resv_code"])
        r2 = self._check(client, data["resv_code"])
        assert r2["data"]["result"] == "fail"
        assert r2["data"]["fail_reason"] == 60002

    def test_wrong_session(self, client, wx_user):
        """错峰: 明天的票今天不能用(60004)。"""
        u = wx_user("蒋二")
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        data = client.book(u["openid"], u["card"], u["name"], date=tomorrow)
        r = self._check(client, data["resv_code"])
        assert r["data"]["fail_reason"] == 60004

    def test_invalid_code(self, client):
        r = self._check(client, "HZNOTEXIST00")
        assert r["data"]["fail_reason"] == 60001

    def test_unbooked_idcard(self, client, wx_user):
        """从未预约的证件 => 未找到有效预约(60003)。"""
        from conftest import make_card, _card_seq
        _card_seq[0] += 1
        r = self._check(client, make_card(_card_seq[0]), ctype="idcard")
        assert r["data"]["result"] == "fail"
        assert r["data"]["fail_reason"] in (60002, 60003)

    def test_checkout_before_checkin_rejected(self, client, wx_user):
        """未入馆不能出馆。"""
        u = wx_user("沈三")
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        data = client.book(u["openid"], u["card"], u["name"], date=tomorrow)
        r = self._check(client, data["resv_code"], direction="out")
        assert r["data"]["result"] == "fail"

    def test_checkin_then_checkout_flow(self, client, wx_user):
        u = wx_user("韩四")
        today = datetime.date.today().isoformat()
        data = client.book(u["openid"], u["card"], u["name"], session_id=2, date=today)
        code = data["resv_code"]
        r_in = self._check(client, code)
        assert r_in["data"]["result"] == "success"
        r_out = self._check(client, code, direction="out")
        assert r_out["data"]["result"] == "success"


class TestOfflineSync:
    def test_batch_sync_idempotent(self, client, wx_user):
        """离线补传: 同一批指令重复补传, 不产生重复记录。"""
        u = wx_user("杨五")
        today = datetime.date.today().isoformat()
        data = client.book(u["openid"], u["card"], u["name"], session_id=2, date=today)
        code = data["resv_code"]
        items = [{
            "check_type": "qrcode", "credential": code, "direction": "in",
            "gate_id": "GATE-OFF", "device_seq": "off-seq-001",
            "pass_time": f"{today}T10:30:00",
        }]
        r1 = client.post("/gate/sync/batch", {"gate_id": "GATE-OFF", "items": items})
        assert r1["data"]["results"][0]["result"] == "success"
        # 重复补传同批次 => duplicate
        r2 = client.post("/gate/sync/batch", {"gate_id": "GATE-OFF", "items": items})
        assert r2["data"]["results"][0]["duplicate"] is True

    def test_batch_sync_pass_time_preserved(self, client, admin, wx_user):
        """补传落库使用实际过闸时间(指令延迟场景)。"""
        u = wx_user("朱六")
        today = datetime.date.today().isoformat()
        data = client.book(u["openid"], u["card"], u["name"], session_id=2, date=today)
        client.post("/gate/sync/batch", {"gate_id": "GATE-OD", "items": [{
            "check_type": "qrcode", "credential": data["resv_code"], "direction": "in",
            "gate_id": "GATE-OD", "device_seq": f"off-seq-time-{time.time()}",
            "pass_time": f"{today}T09:15:00",
        }]})
        # 校验通行日志的pass_time为09:15(非补传时刻)
        rows = client.get("/admin/stats/reservations", params={"date_str": today})["data"]["items"]
        target = next(r for r in rows if r["resv_code"] == data["resv_code"])
        assert target["checked_in_at"].startswith(f"{today} 09:15")

    def test_batch_mixed_results(self, client, wx_user):
        """批量补传中部分无效码: 单条失败不影响其余。"""
        u = wx_user("秦一")
        today = datetime.date.today().isoformat()
        data = client.book(u["openid"], u["card"], u["name"], session_id=2, date=today)
        items = [
            {"check_type": "qrcode", "credential": "HZINVALID0000", "direction": "in",
             "gate_id": "GATE-MIX", "device_seq": "mix-001", "pass_time": f"{today}T10:00:00"},
            {"check_type": "qrcode", "credential": data["resv_code"], "direction": "in",
             "gate_id": "GATE-MIX", "device_seq": "mix-002", "pass_time": f"{today}T10:01:00"},
        ]
        r = client.post("/gate/sync/batch", {"gate_id": "GATE-MIX", "items": items})["data"]["results"]
        assert r[0]["result"] == "fail"
        assert r[1]["result"] == "success"


class TestPerformance:
    def test_gate_check_latency(self, client, wx_user):
        """核销响应 < 0.5s (需求六)。"""
        u = wx_user("尤二")
        today = datetime.date.today().isoformat()
        data = client.book(u["openid"], u["card"], u["name"], session_id=2, date=today)
        t0 = time.perf_counter()
        client.post("/gate/check", {
            "check_type": "qrcode", "credential": data["resv_code"], "direction": "in",
            "gate_id": "GATE-P", "device_seq": f"perf-{time.time()}"})
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.5, f"核销耗时{elapsed:.2f}s 超过0.5s"
