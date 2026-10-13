"""防刷高频边界 + 并发名额一致性测试(需求: 节假日高并发名额不超卖)。"""
import datetime
import threading
import time


class TestAntiSpam:
    def test_daily_limit_three_per_card(self, client, admin):
        """同证件当日预约次数计数不超过上限(2次); 取消后额度释放可重约。"""
        from conftest import make_card, _card_seq
        _card_seq[0] += 1
        card = make_card(_card_seq[0])
        name = "限次用户"
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        openid = f"wx_limit_{int(time.time()*1000)}"
        client.post("/wx/login", {"code": openid, "nickname": name})
        client.post("/wx/realname", {"real_name": name, "id_card_no": card, "phone": "13800000000"},
                    headers={"X-Wx-Openid": openid})
        h = {"X-Wx-Openid": openid}
        # 两个时段各订一单 => 同证件同日同时段唯一, 各占1次
        for sid in (1, 2):
            client.post("/wx/reservations", {"visit_date": tomorrow, "session_id": sid,
                                             "visitors": [{"real_name": name, "id_card_no": card, "phone": ""}]},
                        expect_code=0, headers=h)
        resvs = [r for r in client.get("/wx/reservations", headers=h)["data"]
                 if r["visit_date"] == tomorrow and r["status"] == "booked"]
        assert len(resvs) == 2
        # 已达上限2次, 第3次被限次拦截
        r3 = client.post("/wx/reservations", {"visit_date": tomorrow, "session_id": 1,
                                              "visitors": [{"real_name": name, "id_card_no": card, "phone": ""}]},
                         expect_code=50002, headers=h)
        assert r3["code"] == 50002
        # 取消上午场那单 => 额度释放, 重订同时段成功(时段唯一约束也已随取消解除)
        am = next(r for r in resvs if r["session_name"] == "上午场")
        client.delete(f"/wx/reservations/{am['id']}", headers=h)
        r4 = client.post("/wx/reservations", {"visit_date": tomorrow, "session_id": 1,
                                              "visitors": [{"real_name": name, "id_card_no": card, "phone": ""}]},
                         headers=h)
        assert r4["code"] == 0, r4

    def test_rapid_duplicate_submit_nonce(self, client, wx_user, tomorrow):
        """携带相同nonce的重复提交被拦截。"""
        u = wx_user("防重用户")
        nonce = f"nonce-{time.time()}-{id(object())}"
        payload = {"visit_date": tomorrow, "session_id": 1,
                   "visitors": [{"real_name": u["name"], "id_card_no": u["card"], "phone": ""}],
                   "nonce": nonce}
        r1 = client.post("/wx/reservations", payload, headers={"X-Wx-Openid": u["openid"]})
        assert r1["code"] == 0
        r2 = client.post("/wx/reservations", payload, expect_code=40000,
                         headers={"X-Wx-Openid": u["openid"]})
        assert "重复" in r2["message"]

    def test_two_users_same_card_blocked(self, client, wx_user, new_card, tomorrow):
        """两个账号绑同一证件, 第二个账号预约被同日同时段唯一约束拦截。"""
        u1 = wx_user("证件主人")
        openid2 = f"wx_borrow_{int(time.time()*1000)}"
        client.post("/wx/login", {"code": openid2, "nickname": "借证用户"})
        # 借证用户绑定与u1相同的证件
        client.post("/wx/realname", {"real_name": "借证用户", "id_card_no": u1["card"], "phone": "13800000000"},
                    headers={"X-Wx-Openid": openid2})
        # u1先预约成功
        client.book(u1["openid"], u1["card"], u1["name"], date=tomorrow)
        # openid2用同一证件预约 => 50003
        client.post("/wx/reservations", {
            "visit_date": tomorrow, "session_id": 1,
            "visitors": [{"real_name": "借证用户", "id_card_no": u1["card"], "phone": ""}]},
            expect_code=50003, headers={"X-Wx-Openid": openid2})


class TestConcurrency:
    def test_no_oversell_under_parallel_booking(self, client, admin):
        """并发预约不超卖: 临时时段容量3, 10并发只应成功3单。"""
        # 建临时小容量时段
        s = client.post("/admin/slots", {"name": f"并发时段{int(time.time())}",
                                         "start_time": "08:00", "end_time": "08:30",
                                         "capacity": 3, "is_active": 1})["data"]
        sid = s["id"]
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        # 预创建10个实名用户
        users = []
        from conftest import make_card, _card_seq
        for i in range(10):
            _card_seq[0] += 1
            card = make_card(_card_seq[0])
            openid = f"wx_cc_{int(time.time()*1000)}_{i}"
            client.post("/wx/login", {"code": openid, "nickname": f"并发{i}"})
            client.post("/wx/realname", {"real_name": f"并发{i}", "id_card_no": card, "phone": "13800000000"},
                        headers={"X-Wx-Openid": openid})
            users.append((openid, card, f"并发{i}"))
        # 并发提交
        results = []
        lock = threading.Lock()

        def book(u):
            openid, card, name = u
            c = client.session
            try:
                resp = c.post(client.base + "/wx/reservations", json={
                    "visit_date": tomorrow, "session_id": sid,
                    "visitors": [{"real_name": name, "id_card_no": card, "phone": ""}]},
                    headers={"X-Wx-Openid": openid}, timeout=15)
                body = resp.json()
                with lock:
                    results.append(body["code"])
            except Exception as e:
                with lock:
                    results.append(-1)

        threads = [threading.Thread(target=book, args=(u,)) for u in users]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        ok_count = sum(1 for c in results if c == 0)
        # 校验时段实际占用
        slots = client.get("/admin/slots")["data"]
        cap = next(s2 for s2 in slots if s2["id"] == sid)["capacity"]
        # 清理时段
        client.request("PUT", f"/admin/slots/{sid}", expect_code=None,
                       json={"name": "并发时段-停用", "start_time": "08:00", "end_time": "08:30",
                             "capacity": 3, "is_active": 0})
        assert ok_count <= cap, f"超卖! 成功{ok_count} > 容量{cap}"
        assert ok_count == 3, f"名额利用率不足: 成功{ok_count}/3 (并发竞争失败属正常少量)"
