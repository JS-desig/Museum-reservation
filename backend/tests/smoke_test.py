"""上线前冒烟检查: 11项核心链路一键验证(对应需求7.3 上线保障)。

链路: 健康检查 → 场馆信息 → 公告 → 展品 → 登录实名 → 选时段 → 预约
      → 闸机核销入馆 → 重复核销拦截 → 出馆核销 → 数据对账

用法:
    python tests/smoke_test.py                          # 默认 127.0.0.1:8000
    python tests/smoke_test.py --base-url http://host:8000/api

退出码: 0 = 全部通过(允许发布); 1 = 存在失败项(阻断发布)。

注意: 冒烟会写入真实数据(1笔预约 + 入/出馆通行日志)。上线前请在目标环境用
      专用测试账号执行, 结果随发布单归档。
"""
import argparse
import datetime
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    # Windows GBK 控制台兜底: 不可编码字符降级替换而非抛异常
    sys.stdout.reconfigure(errors="replace")

import requests  # noqa: E402

from api_client import APIClient  # noqa: E402
from idcard import make_card  # noqa: E402

SUN = int(time.time() * 1000) % 100000000
RUN_ID = f"smoke-{SUN}"

# 冒烟共享状态(各检查项之间串联)
st = {}


def check_1_health(c):
    """服务存活。"""
    body = c.request("GET", "/health", expect_code=None)
    assert body["status"] == "UP", f"服务状态 {body.get('status')}"


def check_2_venue(c):
    """场馆基础信息可读。"""
    data = c.get("/venue")["data"]
    assert data["name"], "场馆名称为空"
    st["venue"] = data["name"]


def check_3_announcements(c):
    """公告列表可读, 仅返回已发布且按发布时间倒序。"""
    items = c.get("/announcements")["data"]
    assert isinstance(items, list), "公告返回结构异常"
    times = [a["publish_time"] for a in items]
    assert times == sorted(times, reverse=True), "公告未按发布时间倒序"


def check_4_exhibits(c):
    """展品列表可读(服务端已过滤未上架)且字段完整。"""
    items = c.get("/exhibits")["data"]
    assert isinstance(items, list), "展品返回结构异常"
    for e in items:
        assert e["title"] and e["hall_name"], f"展品{e['id']}缺少标题/展厅"


def check_5_login_realname(c):
    """C端登录 + 实名绑定闭环。"""
    card = make_card(SUN)
    openid = f"wx_{RUN_ID}"
    c.post("/wx/login", {"code": openid, "nickname": "冒烟账号"})
    c.post("/wx/realname",
           {"real_name": "冒烟用户", "id_card_no": card, "phone": "13800000000"},
           headers={"X-Wx-Openid": openid})
    profile = c.get("/wx/profile", headers={"X-Wx-Openid": openid})["data"]
    assert profile["is_verified"] is True, "实名后 is_verified 应为 true"
    assert "*" in profile["id_card_masked"], "证件号未脱敏"
    st.update(openid=openid, card=card)


def check_6_slots(c):
    """按日期查询时段余量。"""
    today = datetime.date.today().isoformat()
    data = c.get("/wx/slots", params={"visit_date": today})["data"]
    assert data["slots"], "无可用时段"
    assert not data["closed"], "场馆处于闭馆状态, 无法冒烟"
    for s in data["slots"]:
        assert s["remaining"] <= s["capacity"], "时段余量大于容量"
    st["session_id"] = data["slots"][0]["id"]


def check_7_book(c):
    """创建预约(今日, 需当日核销验证)。"""
    assert st.get("session_id") and st.get("card"), "前置实名/时段查询未完成, 跳过"
    today = datetime.date.today().isoformat()
    data = c.post("/wx/reservations", {
        "visit_date": today, "session_id": st["session_id"],
        "visitors": [{"real_name": "冒烟用户", "id_card_no": st["card"], "phone": "13800000000"}],
    }, headers={"X-Wx-Openid": st["openid"]})["data"]
    assert data["resv_code"] and len(data["resv_code"]) == 12, "预约码格式异常"
    assert data["status"] == "booked", f"预约初始状态 {data['status']}"
    st["resv_code"] = data["resv_code"]


def check_8_gate_check_in(c):
    """闸机扫码核销入馆 => 开闸。"""
    r = c.post("/gate/check", {
        "check_type": "qrcode", "credential": st["resv_code"], "direction": "in",
        "gate_id": "GATE-SMOKE", "device_seq": f"{RUN_ID}-in-1"})["data"]
    assert r["result"] == "success", f"核销失败: {r.get('fail_reason')}"
    assert r["gate_action"] == "open" and r["light"] == "green", "闸机未开闸"
    st["check_in_ok"] = True


def check_9_gate_duplicate_block(c):
    """重复核销被拦截 => 红灯拒绝。"""
    assert st.get("check_in_ok"), "前置核销未成功, 跳过"
    r = c.post("/gate/check", {
        "check_type": "qrcode", "credential": st["resv_code"], "direction": "in",
        "gate_id": "GATE-SMOKE", "device_seq": f"{RUN_ID}-in-2"})["data"]
    assert r["result"] == "fail", "重复核销未被拦截"
    assert r["gate_action"] == "deny" and r["light"] == "red", "闸机未红灯拒绝"
    assert r["fail_reason"] == 60002, f"重复核销应返回60002, 实际 {r['fail_reason']}"


def check_10_gate_check_out(c):
    """出馆核销 => 在馆人数回落。"""
    r = c.post("/gate/check", {
        "check_type": "qrcode", "credential": st["resv_code"], "direction": "out",
        "gate_id": "GATE-SMOKE", "device_seq": f"{RUN_ID}-out-1"})["data"]
    assert r["result"] == "success", f"出馆核销失败: {r.get('fail_reason')}"


def check_11_reconcile(c):
    """数据对账: 实时在馆 = 入馆 - 出馆, 且核销记录后台可见。"""
    c.admin_login()
    rt = c.get("/admin/stats/dashboard")["data"]["realtime"]
    assert rt["in_venue"] == rt["inflow_today"] - rt["outflow_today"], \
        f"在馆人数口径不一致: {rt['in_venue']} != {rt['inflow_today']}-{rt['outflow_today']}"
    records = c.get("/admin/check-records", params={"date_str": datetime.date.today().isoformat()})["data"]["items"]
    mine = [r for r in records if r["device_seq"].startswith(RUN_ID)]
    assert len(mine) == 3, f"本次冒烟应产生3条核销记录, 实际{len(mine)}"


CHECKS = [
    ("1  服务健康检查", check_1_health),
    ("2  场馆信息", check_2_venue),
    ("3  公告列表", check_3_announcements),
    ("4  展品列表", check_4_exhibits),
    ("5  登录+实名绑定", check_5_login_realname),
    ("6  选日期时段", check_6_slots),
    ("7  创建预约", check_7_book),
    ("8  闸机核销入馆", check_8_gate_check_in),
    ("9  重复核销拦截", check_9_gate_duplicate_block),
    ("10 出馆核销", check_10_gate_check_out),
    ("11 数据对账", check_11_reconcile),
]


def main():
    ap = argparse.ArgumentParser(description="上线前冒烟检查")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000/api")
    args = ap.parse_args()

    client = APIClient(args.base_url)
    print("=" * 64)
    print("菏泽市科技博物馆 上线前冒烟检查")
    print(f"目标: {args.base_url}    批次: {RUN_ID}")
    print("=" * 64)

    # 预检: 服务不可达时立即退出, 避免逐项重试拖长耗时
    try:
        r = requests.get(f"{args.base_url}/health", timeout=5)
        assert r.status_code == 200 and r.json()["status"] == "UP", f"HTTP {r.status_code}"
    except Exception as e:
        print(f"[ABORT] 服务不可达: {args.base_url}")
        print(f"        {type(e).__name__}: {e}")
        print("结论: 冒烟中止, 阻断发布 [FAIL]")
        sys.exit(1)

    failed = []
    t_start = time.perf_counter()
    for name, fn in CHECKS:
        t0 = time.perf_counter()
        try:
            fn(client)
            print(f"[PASS] {name}  ({time.perf_counter() - t0:.2f}s)")
        except Exception as e:
            failed.append((name, e))
            print(f"[FAIL] {name}  ({time.perf_counter() - t0:.2f}s)")
            print(f"       └─ {type(e).__name__}: {e}")

    total = time.perf_counter() - t_start
    print("-" * 64)
    print(f"合计 {len(CHECKS)} 项 | 通过 {len(CHECKS) - len(failed)} | 失败 {len(failed)} | 耗时 {total:.2f}s")
    if failed:
        print("结论: 存在失败项, 阻断发布 [FAIL]")
        sys.exit(1)
    print("结论: 核心链路全部通过, 允许发布 [PASS]")
    sys.exit(0)


if __name__ == "__main__":
    main()
