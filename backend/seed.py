"""种子数据: 默认账号、场馆、时段、展品、公告、配置。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.models import (
    AdminUser, VenueInfo, SessionSlot, Exhibit, Announcement, SysConfig,
)


def run():
    db = SessionLocal()
    try:
        # 后台账号
        if not db.query(AdminUser).filter_by(username="admin").first():
            db.add(AdminUser(
                username="admin", password=hash_password("admin123"),
                real_name="系统管理员", role="admin"))
        if not db.query(AdminUser).filter_by(username="operator").first():
            db.add(AdminUser(
                username="operator", password=hash_password("operator123"),
                real_name="场馆运营员", role="operator"))

        # 场馆
        if not db.query(VenueInfo).first():
            db.add(VenueInfo(
                name="菏泽市科技博物馆",
                address="山东省菏泽市牡丹区人民路1000号",
                open_time="周二至周日 9:00-17:00 (16:00停止入馆), 周一闭馆(法定节假日除外)",
                traffic_guide="公交: 3路/9路/28路至科技馆站; 自驾: 场馆地下停车场B1-B2层免费停车",
                notice="1.免费不免票, 需实名预约入馆; 2.禁止携带易燃易爆物品; 3.请勿触摸展品; 4.文明参观。",
                max_daily=5000))

        # 时段
        if not db.query(SessionSlot).first():
            db.add_all([
                SessionSlot(name="上午场", start_time="09:00", end_time="12:00", capacity=2000),
                SessionSlot(name="下午场", start_time="13:00", end_time="16:00", capacity=2000),
            ])

        # 展品
        if not db.query(Exhibit).first():
            db.add_all([
                Exhibit(hall_name="序厅", title="科技之光主题装置",
                        description="直径8米的动态光影装置, 展现菏泽牡丹与科技融合之美。",
                        media_type="image", media_url="/static/exhibits/hall_light.svg", sort_order=1),
                Exhibit(hall_name="儿童科学乐园", title="趣味物理实验台",
                        description="面向3-12岁儿童的互动物理实验设施: 光学迷宫、声波共振、磁悬浮。",
                        media_type="video", media_url="/static/exhibits/kids_physics.svg", sort_order=1),
                Exhibit(hall_name="生命科学厅", title="基因密码展区",
                        description="DNA双螺旋模型与基因测序互动体验, 了解生命科学的奥秘。",
                        media_type="image", media_url="/static/exhibits/gene.svg", sort_order=1,
                        is_special=1, price_cent=2000, capacity=20),
                Exhibit(hall_name="智慧菏泽厅", title="牡丹产业数字化展项",
                        description="展示菏泽牡丹全产业链的数字化、智能化成果。",
                        media_type="audio", media_url="/static/exhibits/peony.svg", sort_order=1),
                Exhibit(hall_name="航空航天厅", title="载人航天模拟舱",
                        description="1:1神舟飞船返回舱模型, 可体验航天员训练模拟器。",
                        media_type="video", media_url="/static/exhibits/space.svg", sort_order=1,
                        is_special=1, price_cent=3000, capacity=12),
                Exhibit(hall_name="儿童科学乐园", title="VR深海探险",
                        description="VR沉浸式深海探险体验, 探索海底火山与深海生物发光之谜。",
                        media_type="video", media_url="/static/exhibits/kids_physics.svg", sort_order=2,
                        is_special=1, price_cent=2500, capacity=15),
                Exhibit(hall_name="智慧菏泽厅", title="机器人编程工坊",
                        description="在讲解员指导下完成第一台编程机器人, 体验人工智能的魅力(45分钟)。",
                        media_type="image", media_url="/static/exhibits/hall_light.svg", sort_order=2,
                        is_special=1, price_cent=3500, capacity=10),
            ])

        # 公告
        if not db.query(Announcement).first():
            db.add_all([
                Announcement(
                    title="中秋国庆双节开放公告",
                    content="中秋、国庆假期(10月1日-10月8日)正常开放, 每日增设夜场(17:30-20:30), 请提前预约。",
                    type="activity", is_published=1),
                Announcement(
                    title="10月15日临时闭馆维护公告",
                    content="因设备检修, 10月15日(周三)全天临时闭馆, 已预约游客可免费改约其他日期。",
                    type="closure", is_published=1),
            ])

        # 系统配置
        cfg_defaults = [
            ("capacity_warn_ratio", "0.9", "客流预警阈值比例"),
            ("offline_sync_enabled", "1", "是否启用离线核销补传"),
            ("special_slot_dates", "2026-10-01,2026-10-02,2026-10-03,2026-10-04,2026-10-05,2026-10-06,2026-10-07,2026-10-08",
             "夜场等特殊时段开放日期(逗号分隔), 留空=日常不开放"),
        ]
        for k, v, remark in cfg_defaults:
            if not db.query(SysConfig).filter_by(cfg_key=k).first():
                db.add(SysConfig(cfg_key=k, cfg_value=v, remark=remark))

        db.commit()
        print("Seed data OK: 2 admins, 1 venue, 2 slots, 5 exhibits, 2 announcements")
    finally:
        db.close()


if __name__ == "__main__":
    run()
