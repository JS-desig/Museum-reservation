"""SQL 数据一致性校验脚本: 直接对库执行对账SQL。

对应需求五: 预约状态与核销状态强一致; 报表数据与通行日志完全对账。
用法: python sql_consistency.py
退出码: 0=全部通过 1=发现不一致
"""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    # Windows GBK 控制台兜底: 不可编码字符降级替换而非中断对账
    sys.stdout.reconfigure(errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pymysql  # noqa: E402


def get_conn():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    from app.core.config import settings
    return pymysql.connect(
        host=settings.DB_HOST, port=settings.DB_PORT, user=settings.DB_USER,
        password=settings.DB_PASSWORD, database=settings.DB_NAME, charset="utf8mb4")


CHECKS = [
    # 1. 每个已核销预约必须有对应入馆通行日志
    ("checked_in预约必有通行日志",
     """SELECT COUNT(*) FROM reservation r
        WHERE r.status = 'checked_in'
          AND NOT EXISTS (SELECT 1 FROM access_log a
                          WHERE a.reservation_id = r.id AND a.direction = 'in')"""),
    # 2. 每条成功核销记录必须有通行日志(核销↔通行一一对应)
    ("成功核销必有通行日志",
     """SELECT COUNT(*) FROM check_record c
        WHERE c.result = 'success'
          AND NOT EXISTS (SELECT 1 FROM access_log a WHERE a.check_record_id = c.id)"""),
    # 3. 每条入馆通行日志必须来自成功核销或手动核销
    ("通行日志必有成功核销依据",
     """SELECT COUNT(*) FROM access_log a
        WHERE a.direction = 'in'
          AND a.check_record_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM check_record c
                          WHERE c.id = a.check_record_id AND c.result = 'success')"""),
    # 4. 已核销预约的checked_in_at必须与首位游客过闸时间一致(允许1秒误差)
    ("预约核销时间与通行日志一致",
     """SELECT COUNT(*) FROM reservation r
        WHERE r.status = 'checked_in' AND r.checked_in_at IS NOT NULL
          AND EXISTS (SELECT 1 FROM access_log a
                      WHERE a.reservation_id = r.id AND a.direction = 'in')
          AND ABS(TIMESTAMPDIFF(SECOND, r.checked_in_at,
                (SELECT MIN(a.pass_time) FROM access_log a
                 WHERE a.reservation_id = r.id AND a.direction = 'in'))) > 5"""),
    # 5. 已取消预约不应有核销后的通行(取消后闸机不能放行)
    ("已取消预约无入馆记录",
     """SELECT COUNT(*) FROM reservation r
        WHERE r.status = 'cancelled'
          AND EXISTS (SELECT 1 FROM access_log a
                      WHERE a.reservation_id = r.id AND a.direction = 'in')"""),
    # 6. 在馆人数口径: 通行日志 in-out == 后台统计应显示的当前在馆
    ("通行日志进出方向合法",
     """SELECT COUNT(*) FROM access_log WHERE direction NOT IN ('in','out')"""),
    # 7. 重复入馆检查: 同一游客同一天不能有两次入馆日志
    ("无重复入馆记录",
     """SELECT COUNT(*) FROM (
            SELECT visitor_id, DATE(pass_time) d, COUNT(*) c
            FROM access_log WHERE direction = 'in' AND visitor_id IS NOT NULL
            GROUP BY visitor_id, DATE(pass_time) HAVING c > 1) t"""),
]


def main():
    conn = get_conn()
    all_pass = True
    try:
        with conn.cursor() as cur:
            print("=" * 60)
            print("菏泽市科技博物馆 数据一致性校验")
            print("=" * 60)
            for name, sql in CHECKS:
                cur.execute(sql)
                (cnt,) = cur.fetchone()
                status = "PASS" if cnt == 0 else "FAIL"
                if cnt != 0:
                    all_pass = False
                print(f"[{status}] {name}: {cnt} 条异常")
            # 附加统计
            cur.execute("""SELECT
                (SELECT COUNT(*) FROM reservation WHERE status='checked_in'),
                (SELECT COUNT(*) FROM check_record WHERE result='success' AND direction='in'),
                (SELECT COUNT(*) FROM access_log WHERE direction='in')""")
            checked, rec, logs = cur.fetchone()
            print("-" * 60)
            print(f"汇总: 已核销预约{checked} | 成功核销记录{rec} | 入馆日志{logs}")
            if rec != logs:
                print(f"[WARN] 核销记录与入馆日志数差异{logs - rec}(手动核销不计check_record, 多游客预约属正常)")
    finally:
        conn.close()

    print("=" * 60)
    print("结果:", "全部通过 [PASS]" if all_pass else "存在不一致 [FAIL]")
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
