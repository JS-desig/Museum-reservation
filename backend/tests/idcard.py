"""测试身份证号工厂: 由序号生成校验位合法的18位身份证。

序号唯一 => 卡号唯一, 供 conftest 夹具与冒烟脚本共用。
"""

_W = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
_C = "10X98765432"


def make_card(seq: int) -> str:
    """由序号生成校验位合法的18位测试身份证。"""
    area = f"{110100 + seq % 100:06d}"[:6]
    birth = f"{1980 + (seq // 100) % 30:04d}{1 + seq % 12:02d}{1 + (seq // 7) % 28:02d}"
    tail4 = f"{seq % 10000:04d}"
    base = (area + birth + tail4)[:17]
    check = _C[sum(int(b) * w for b, w in zip(base, _W)) % 11]
    return base + check
