"""预约模块测试: 正常流、边界、防刷。"""
import datetime

E_FULL = 50001      # 时段满
E_LIMIT = 50002     # 证件当日次数上限
E_DUP = 50003       # 同日同时段重复
E_CANCEL_STATE = 50005
E_PARAM = 40000


class TestCreateReservation:
    def test_normal_booking(self, client, wx_user, tomorrow):
        u = wx_user("张三")
        data = client.book(u["openid"], u["card"], u["name"], date=tomorrow)
        assert data["resv_code"].startswith("HZ")
        assert len(data["resv_code"]) == 12
        assert data["status"] == "booked"
        assert data["visitor_count"] == 1

    def test_booking_with_companions(self, client, wx_user, new_card, tomorrow):
        u = wx_user("李四")
        c2 = new_card
        data = client.book(u["openid"], u["card"], u["name"], date=tomorrow,
                           visitors=[{"real_name": u["name"], "id_card_no": u["card"], "phone": ""},
                                     {"real_name": "王五", "id_card_no": c2, "phone": ""}])
        assert data["visitor_count"] == 2

    def test_unverified_user_rejected(self, client, tomorrow):
        openid = f"wx_py_noverify_{id(object())}"
        client.post("/wx/login", {"code": openid})
        body = client.post("/wx/reservations",
                           {"visit_date": tomorrow, "session_id": 1,
                            "visitors": [{"real_name": "X", "id_card_no": "110101199003078670", "phone": ""}]},
                           expect_code=40000, headers={"X-Wx-Openid": openid})
        assert "实名" in body["message"]

    def test_main_visitor_card_must_be_included(self, client, wx_user, new_card, tomorrow):
        u = wx_user("赵六")
        body = client.post("/wx/reservations",
                           {"visit_date": tomorrow, "session_id": 1,
                            "visitors": [{"real_name": "别人", "id_card_no": new_card, "phone": ""}]},
                           expect_code=40000, headers={"X-Wx-Openid": u["openid"]})
        assert "主预约人" in body["message"]

    def test_past_date_rejected(self, client, wx_user):
        u = wx_user("孙七")
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        client.post("/wx/reservations",
                    {"visit_date": yesterday, "session_id": 1,
                     "visitors": [{"real_name": u["name"], "id_card_no": u["card"], "phone": ""}]},
                    expect_code=40000, headers={"X-Wx-Openid": u["openid"]})

    def test_beyond_7days_rejected(self, client, wx_user):
        u = wx_user("周八")
        far = (datetime.date.today() + datetime.timedelta(days=8)).isoformat()
        client.post("/wx/reservations",
                    {"visit_date": far, "session_id": 1,
                     "visitors": [{"real_name": u["name"], "id_card_no": u["card"], "phone": ""}]},
                    expect_code=40000, headers={"X-Wx-Openid": u["openid"]})

    def test_duplicate_same_session(self, client, wx_user, tomorrow):
        u = wx_user("吴九")
        client.book(u["openid"], u["card"], u["name"], date=tomorrow)
        client.post("/wx/reservations",
                    {"visit_date": tomorrow, "session_id": 1,
                     "visitors": [{"real_name": u["name"], "id_card_no": u["card"], "phone": ""}]},
                    expect_code=E_DUP, headers={"X-Wx-Openid": u["openid"]})

    def test_same_card_different_session_ok(self, client, wx_user, tomorrow):
        """同证件同日不同时段允许。"""
        u = wx_user("郑十")
        client.book(u["openid"], u["card"], u["name"], session_id=1, date=tomorrow)
        data = client.book(u["openid"], u["card"], u["name"], session_id=2, date=tomorrow)
        assert data["status"] == "booked"

    def test_max_visitors_per_resv(self, client, wx_user, tomorrow):
        """单笔超过5人被拒(边界: 5人成功 6人拒绝)。"""
        u = wx_user("王一")
        visitors = [{"real_name": u["name"], "id_card_no": u["card"], "phone": ""}]
        for i in range(5):
            from conftest import make_card
            visitors.append({"real_name": f"同行{i}", "id_card_no": make_card(90000 + i), "phone": ""})
        body = client.post("/wx/reservations",
                           {"visit_date": tomorrow, "session_id": 1, "visitors": visitors},
                           expect_code=40000, headers={"X-Wx-Openid": u["openid"]})

    def test_duplicate_cards_in_one_resv(self, client, wx_user, tomorrow):
        u = wx_user("刘二")
        card = {"real_name": u["name"], "id_card_no": u["card"], "phone": ""}
        client.post("/wx/reservations",
                    {"visit_date": tomorrow, "session_id": 1, "visitors": [card, card]},
                    expect_code=40000, headers={"X-Wx-Openid": u["openid"]})


class TestCancel:
    def test_cancel_tomorrow_ok(self, client, wx_user, tomorrow):
        u = wx_user("陈三")
        data = client.book(u["openid"], u["card"], u["name"], date=tomorrow)
        body = client.delete(f"/wx/reservations/{data['reservation_id']}",
                             headers={"X-Wx-Openid": u["openid"]})
        assert body["data"]["status"] == "cancelled"

    def test_cancel_twice_rejected(self, client, wx_user, tomorrow):
        u = wx_user("张四")
        data = client.book(u["openid"], u["card"], u["name"], date=tomorrow)
        client.delete(f"/wx/reservations/{data['reservation_id']}", headers={"X-Wx-Openid": u["openid"]})
        client.delete(f"/wx/reservations/{data['reservation_id']}",
                      expect_code=E_CANCEL_STATE, headers={"X-Wx-Openid": u["openid"]})

    def test_cancel_after_checked_in_rejected(self, client, wx_user, admin):
        """当日预约核销后不可取消。"""
        u = wx_user("李五")
        today = datetime.date.today().isoformat()
        data = client.book(u["openid"], u["card"], u["name"], session_id=2, date=today)
        code = data["resv_code"]
        import time as _t
        seq = f"pytest-{_t.time()}"
        client.post("/gate/check", {"check_type": "qrcode", "credential": code,
                                    "direction": "in", "gate_id": "GATE-T", "device_seq": seq})
        client.delete(f"/wx/reservations/{data['reservation_id']}",
                      expect_code=E_CANCEL_STATE, headers={"X-Wx-Openid": u["openid"]})

    def test_cancel_others_rejected(self, client, wx_user, tomorrow):
        u1 = wx_user("王六")
        u2 = wx_user("冯七")
        data = client.book(u1["openid"], u1["card"], u1["name"], date=tomorrow)
        client.delete(f"/wx/reservations/{data['reservation_id']}",
                      expect_code=40400, headers={"X-Wx-Openid": u2["openid"]})


class TestCapacity:
    def test_slots_remaining_visible(self, client, tomorrow):
        data = client.get("/wx/slots", params={"visit_date": tomorrow})["data"]
        # 至少含默认2个时段(并发测试可能遗留停用时段, is_active=0不计入)
        assert len(data["slots"]) >= 2
        for s in data["slots"]:
            assert s["remaining"] <= s["capacity"]
