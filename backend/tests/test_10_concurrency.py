"""并发/竞态压测: 名额不超卖、多游客混入、闸机指令幂等。

对应需求 2.2(节假日高并发) / 3.3(闸机异常处理) / 五(可靠性与性能)。

与 test_07 单游客并发用例的区别:
- 断言"精确用满容量"(ok==capacity), 既不允许超卖, 也不允许锁过度导致名额丢失;
- 覆盖多游客(n>1)并发, 验证 remaining < n 判断本身是原子的;
- 覆盖闸机同序号/不同序号并发下的幂等与防重复计数。
"""
import datetime
import threading
import time

import requests

from api_client import BASE_URL
from idcard import make_card

_seq = [int(time.time() * 1000) % 100000000]

# 并发线程各自独立XFF IP: 避免同IP触发应用层限流(限流按client_ip计数)
ThreadLocal = threading.local()


def _xff() -> dict:
    """线程级独立XFF头, 保证并发请求各自独立IP。"""
    ident = f"{id(threading.current_thread()) % 65025 + 1}"
    return {"X-Forwarded-For": f"10.{_seq[0] % 250}.{ident}.1"}


def _new_user(prefix, name):
    """创建并实名一个C端用户, 返回 (openid, card, name)。"""
    _seq[0] += 1
    card = make_card(_seq[0])
    openid = f"wx_cc_{prefix}_{int(time.time() * 1000)}_{_seq[0]}"
    requests.post(f"{BASE_URL}/wx/login", json={"code": openid, "nickname": name},
                  headers=_xff(), timeout=10)
    requests.post(f"{BASE_URL}/wx/realname",
                  json={"real_name": name, "id_card_no": card, "phone": "13800000000"},
                  headers={"X-Wx-Openid": openid, **_xff()}, timeout=10)
    return openid, card, name


def _new_card():
    _seq[0] += 1
    return make_card(_seq[0])


def _book_once(openid, visitors, visit_date, sid):
    """单次预约请求(独立连接, 避免多线程共用 Session)。"""
    r = requests.post(f"{BASE_URL}/wx/reservations", json={
        "visit_date": visit_date, "session_id": sid, "visitors": visitors},
        headers={"X-Wx-Openid": openid, **_xff()}, timeout=30)
    return r.json()


def _parallel(fn, args):
    """并发执行 fn(arg), 返回与入参同序的结果列表。"""
    out = [None] * len(args)

    def worker(i, a):
        try:
            out[i] = fn(a)
        except Exception as e:  # 网络/超时也记录, 便于断言无异常
            out[i] = {"code": -1, "message": f"{type(e).__name__}: {e}"}

    ts = [threading.Thread(target=worker, args=(i, a)) for i, a in enumerate(args)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=60)
    return out


def _mk_slot(client, capacity, tag):
    return client.post("/admin/slots", {
        "name": f"压测{tag}-{int(time.time() * 1000) % 100000}",
        "start_time": "07:00", "end_time": "07:30",
        "capacity": capacity, "is_active": 1})["data"]["id"]


def _kill_slot(client, sid, capacity):
    client.request("PUT", f"/admin/slots/{sid}", expect_code=None, json={
        "name": "压测时段-停用", "start_time": "07:00", "end_time": "07:30",
        "capacity": capacity, "is_active": 0})


def _used(client, date_str, sid):
    """指定时段的实际占用量(走C端余量接口, 按 session_id 精确定位)。"""
    data = client.get("/wx/slots", params={"visit_date": date_str})["data"]["slots"]
    return next(s for s in data if s["id"] == sid)["used"]


class TestCapacityConcurrency:
    def test_exact_capacity_no_oversell_no_waste(self, client, admin):
        """容量5 + 20并发单人: 恰好成功5单, 名额用满且不超卖。"""
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        cap = 5
        sid = _mk_slot(client, cap, "A")
        try:
            users = [_new_user("cap", f"容量{i}") for i in range(20)]
            results = _parallel(
                lambda u: _book_once(u[0], [{"real_name": u[2], "id_card_no": u[1], "phone": ""}],
                                     tomorrow, sid),
                users)
            codes = [r.get("code") for r in results]
            ok = codes.count(0)
            fails = [c for c in codes if c != 0]
            assert ok == cap, f"应恰好成功{cap}单, 实际{ok}(codes={codes})"
            assert all(c == 50001 for c in fails), f"失败码应均为时段已满50001, 实际{sorted(set(fails))}"
            assert _used(client, tomorrow, sid) == cap, "名额占用与容量不符"
        finally:
            _kill_slot(client, sid, cap)

    def test_multi_visitor_concurrent_not_oversold(self, client, admin):
        """容量6 + 10并发(每单2人): 恰好成功3单(6人), 验证 remaining<n 判断原子性。"""
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        cap = 6
        sid = _mk_slot(client, cap, "B")
        try:
            pair = [(_new_user("mv", f"双人{i}"), _new_card()) for i in range(10)]
            results = _parallel(
                lambda p: _book_once(p[0][0], [
                    {"real_name": p[0][2], "id_card_no": p[0][1], "phone": ""},
                    {"real_name": f"同行{p[0][2]}", "id_card_no": p[1], "phone": ""}],
                    tomorrow, sid),
                pair)
            codes = [r.get("code") for r in results]
            ok = codes.count(0)
            assert ok == cap // 2, f"容量{cap}每单2人应成功{cap // 2}单, 实际{ok}(codes={codes})"
            assert _used(client, tomorrow, sid) == cap, "总人数应恰好用满容量"
        finally:
            _kill_slot(client, sid, cap)

    def test_remaining_visible_after_concurrency(self, client, admin):
        """并发压满后 C端余量查询应归零(前端不会放出多余名额)。"""
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        cap = 3
        sid = _mk_slot(client, cap, "C")
        try:
            users = [_new_user("rem", f"余量{i}") for i in range(8)]
            _parallel(lambda u: _book_once(
                u[0], [{"real_name": u[2], "id_card_no": u[1], "phone": ""}], tomorrow, sid), users)
            slots = client.get("/wx/slots", params={"visit_date": tomorrow})["data"]["slots"]
            row = next(s for s in slots if s["id"] == sid)
            assert row["remaining"] == 0, f"压满后剩余应为0, 实际{row['remaining']}"
        finally:
            _kill_slot(client, sid, cap)


class TestGateCommandConcurrency:
    def test_same_device_seq_concurrent_idempotent(self, client, admin, wx_user):
        """同一 device_seq 并发 8 次: 只应产生 1 次实际核销。"""
        u = wx_user("幂等并发")
        today = datetime.date.today().isoformat()
        data = client.book(u["openid"], u["card"], u["name"], session_id=2, date=today)
        seq = f"cc-same-{time.time()}"
        payload = {"check_type": "qrcode", "credential": data["resv_code"],
                   "direction": "in", "gate_id": "GATE-CC", "device_seq": seq}

        results = _parallel(
            lambda _: requests.post(f"{BASE_URL}/gate/check", json=payload,
                                    headers=_xff(), timeout=30).json(), [0] * 8)
        successes = [r for r in results if r.get("data", {}).get("result") == "success"
                     and not r["data"].get("duplicate")]
        assert len(successes) == 1, f"同序号并发应只有1次实际核销, 实际{len(successes)}"
        # 不应有5xx/异常
        assert all(r.get("code") == 0 for r in results), \
            f"存在非业务响应(如唯一约束冲突): {[r.get('message') for r in results if r.get('code') != 0]}"
        recs = client.get("/admin/check-records", params={"date_str": today})["data"]["items"]
        mine = [c for c in recs if c["device_seq"] == seq]
        assert len(mine) == 1, f"同序号应只落1条核销记录, 实际{len(mine)}"

    def test_multi_visitor_concurrent_distinct_seq(self, client, admin, wx_user):
        """3人预约 + 3并发不同序号: 3人各核销一次, 不重复计数。"""
        u = wx_user("多人并发")
        today = datetime.date.today().isoformat()
        companions = [_new_card(), _new_card()]
        visitors = [{"real_name": u["name"], "id_card_no": u["card"], "phone": ""}]
        for i, c in enumerate(companions):
            visitors.append({"real_name": f"同行{i}", "id_card_no": c, "phone": ""})
        data = client.post("/wx/reservations", {
            "visit_date": today, "session_id": 2, "visitors": visitors},
            headers={"X-Wx-Openid": u["openid"]})["data"]

        codes = [data["resv_code"]] * 3
        seqs = [f"cc-multi-{time.time()}-{i}" for i in range(3)]
        results = _parallel(lambda i: requests.post(f"{BASE_URL}/gate/check", json={
            "check_type": "qrcode", "credential": codes[i], "direction": "in",
            "gate_id": "GATE-CC2", "device_seq": seqs[i]}, headers=_xff(), timeout=30).json(), list(range(3)))
        ok = [r for r in results if r.get("data", {}).get("result") == "success"]
        assert len(ok) == 3, f"3名游客应各核销1次, 实际成功{len(ok)}"

        recs = client.get("/admin/check-records", params={"date_str": today})["data"]["items"]
        mine = [c for c in recs if c["device_seq"] in seqs]
        assert len(mine) == 3, f"应恰好3条核销记录, 实际{len(mine)}"
        # 预约详情中3名游客均标记已核销, 且无人被重复核销
        rows = client.get("/admin/stats/reservations", params={"date_str": today})["data"]["items"]
        target = next(r for r in rows if r["resv_code"] == data["resv_code"])
        assert all(v["checked_in"] for v in target["visitors"]), "存在未核销游客"
        assert len(target["visitors"]) == 3

    def test_same_visitor_concurrent_distinct_seq(self, client, admin, wx_user):
        """同一游客并发不同序号: 只应核销1次(不得重复放行)。"""
        u = wx_user("重复并发")
        today = datetime.date.today().isoformat()
        data = client.book(u["openid"], u["card"], u["name"], session_id=2, date=today)
        seqs = [f"cc-dup-{time.time()}-{i}" for i in range(5)]
        results = _parallel(lambda i: requests.post(f"{BASE_URL}/gate/check", json={
            "check_type": "qrcode", "credential": data["resv_code"], "direction": "in",
            "gate_id": "GATE-CC3", "device_seq": seqs[i]}, headers=_xff(), timeout=30).json(), list(range(5)))
        ok = [r for r in results if r.get("data", {}).get("result") == "success"]
        assert len(ok) == 1, f"单人并发应只放行1次, 实际{len(ok)}"
        recs = client.get("/admin/check-records", params={"date_str": today})["data"]["items"]
        mine = [c for c in recs if c["device_seq"] in seqs]
        success = [c for c in mine if c["result"] == "success"]
        assert len(success) == 1, f"应恰好1条成功核销记录, 实际{len(success)}"
