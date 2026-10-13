"""Faker 测试数据生成工具: 批量生成预约用户/预约单/通行记录。

用法:
    python tests/fake_data.py --users 50 --date 2026-10-10
    python tests/fake_data.py --users 20 --with-passes   # 同时生成核销+通行记录
"""
import argparse
import datetime
import random
import sys
from pathlib import Path

from faker import Faker

sys.path.insert(0, str(Path(__file__).resolve().parent))
from api_client import APIClient  # noqa: E402

fake = Faker("zh_CN")

_W = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
_C = "10X98765432"


def make_card(seq: int) -> str:
    base = f"{fake.numerify('######')}{1990 + seq % 25:04d}{random.randint(1, 12):02d}{random.randint(1, 28):02d}{seq % 10000:04d}"[:17]
    return base + _C[sum(int(b) * w for b, w in zip(base, _W)) % 11]


def gen_users(n: int):
    """生成n个实名用户, 返回 [(openid, card, name)]。"""
    users = []
    for i in range(n):
        openid = f"faker_{datetime.datetime.now().timestamp()}_{i}"
        name = fake.name()
        card = make_card(i)
        yield openid, name, card


def _phone() -> str:
    return fake.numerify("13#########")


def create_reservation(client, openid, name, card, visit_date, session_id):
    return client.post("/wx/reservations", {
        "visit_date": visit_date, "session_id": session_id,
        "visitors": [{"real_name": name, "id_card_no": card, "phone": _phone()},
                     ]},
        headers={"X-Wx-Openid": openid})


def main():
    parser = argparse.ArgumentParser(description="博物馆测试数据生成器")
    parser.add_argument("--users", type=int, default=10, help="生成用户/预约数")
    parser.add_argument("--date", default=None, help="参观日期 YYYY-MM-DD, 默认明天")
    parser.add_argument("--session", type=int, default=1, help="时段id")
    parser.add_argument("--with-passes", action="store_true", help="同时对部分预约执行闸机核销")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api")
    args = parser.parse_args()

    visit_date = args.date or (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    client = APIClient(args.base_url)

    ok, fail = 0, 0
    created = []
    for i, (openid, name, card) in enumerate(gen_users(args.users)):
        client.post("/wx/login", {"code": openid, "nickname": name})
        client.post("/wx/realname", {"real_name": name, "id_card_no": card, "phone": fake.phone_number()},
                    headers={"X-Wx-Openid": openid})
        r = create_reservation(client, openid, name, card, visit_date, args.session)
        if r["code"] == 0:
            ok += 1
            created.append(r["data"]["resv_code"])
        else:
            fail += 1

    print(f"预约生成: 成功{ok} 失败{fail} (日期{visit_date} 时段{args.session})")

    if args.with_passes:
        passed = 0
        for code in created:
            if random.random() < 0.7:  # 70%核销率
                r = client.post("/gate/check", {
                    "check_type": "qrcode", "credential": code, "direction": "in",
                    "gate_id": f"GATE-{random.randint(1, 4):02d}",
                    "device_seq": f"faker-{datetime.datetime.now().timestamp()}-{passed}"})
                if r["data"]["result"] == "success":
                    passed += 1
        print(f"闸机核销: 成功{passed}/{len(created)}")


if __name__ == "__main__":
    main()
