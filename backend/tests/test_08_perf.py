"""性能基线测试(需求六): 预约接口 < 1s, 闸机核销 < 0.5s。

断言取多次采样的"最坏值", 避免单次抖动造成的偶发误报;
样本区间同时打印, 便于对比优化前后基线。
"""
import datetime
import time


def _worst(fn, times: int):
    """执行 times 次, 返回 (最坏耗时, 全部采样)。"""
    samples = []
    for _ in range(times):
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    return max(samples), samples


class TestPerformanceBaseline:
    def test_slots_query_latency(self, client):
        """C端时段余量查询(SUM聚合) < 1s。"""
        today = datetime.date.today().isoformat()
        worst, samples = _worst(
            lambda: client.get("/wx/slots", params={"visit_date": today}), 5)
        assert worst < 1.0, f"时段查询最坏 {worst:.3f}s 超过1s, 采样={samples}"

    def test_reservation_create_latency(self, client, wx_user):
        """预约创建(名额校验+同行人明细+限次计数同事务) < 1s。"""
        today = datetime.date.today().isoformat()
        samples = []
        for i in range(3):
            u = wx_user(f"性能预约{i}")
            t0 = time.perf_counter()
            client.book(u["openid"], u["card"], u["name"], session_id=2, date=today)
            samples.append(time.perf_counter() - t0)
        worst = max(samples)
        assert worst < 1.0, f"预约创建最坏 {worst:.3f}s 超过1s, 采样={samples}"

    def test_gate_check_latency(self, client, wx_user):
        """闸机核销(索引查询+单事务写入) < 0.5s。"""
        today = datetime.date.today().isoformat()
        samples = []
        for i in range(3):
            u = wx_user(f"性能核销{i}")
            data = client.book(u["openid"], u["card"], u["name"], session_id=2, date=today)
            t0 = time.perf_counter()
            r = client.post("/gate/check", {
                "check_type": "qrcode", "credential": data["resv_code"], "direction": "in",
                "gate_id": "GATE-PERF", "device_seq": f"perf-{time.time()}-{i}"})
            samples.append(time.perf_counter() - t0)
            assert r["data"]["result"] == "success", r["data"].get("fail_reason")
        worst = max(samples)
        assert worst < 0.5, f"闸机核销最坏 {worst:.3f}s 超过0.5s, 采样={samples}"

    def test_dashboard_aggregation_latency(self, client):
        """看板聚合统计(多表聚合) < 1s。"""
        client.admin_login()
        worst, samples = _worst(lambda: client.get("/admin/stats/dashboard"), 5)
        assert worst < 1.0, f"看板聚合最坏 {worst:.3f}s 超过1s, 采样={samples}"
