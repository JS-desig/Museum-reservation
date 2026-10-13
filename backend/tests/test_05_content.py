"""内容模块测试: 场馆/展品/公告 CRUD + C端可见性。"""


class TestVenue:
    def test_get_venue(self, client):
        data = client.get("/venue")["data"]
        assert data["name"]
        assert data["max_daily"] > 0

    def test_update_venue_admin(self, client, admin):
        body = client.put("/admin/venue", {"open_time": "周二至周日 9:00-17:00 (更新)"})
        assert body["code"] == 0
        assert "更新" in client.get("/venue")["data"]["open_time"]

    def test_update_venue_requires_auth(self, client):
        """未登录修改场馆被拒。"""
        old = client.session.headers.pop("Authorization", None)
        client.put("/admin/venue", {"open_time": "x"}, expect_code=40100)
        if old:
            client.session.headers["Authorization"] = old

    def test_daily_max_reflected_in_slots(self, client, tomorrow):
        data = client.get("/wx/slots", params={"visit_date": tomorrow})["data"]
        assert data["daily_max"] > 0


class TestExhibits:
    def test_c_list_only_published(self, client):
        items = client.get("/exhibits")["data"]
        assert len(items) >= 5
        assert all(e["title"] for e in items)

    def test_filter_by_hall(self, client):
        items = client.get("/exhibits", params={"hall": "序厅"})["data"]
        assert all(e["hall_name"] == "序厅" for e in items)

    def test_admin_create_update_delete(self, client, admin):
        created = client.post("/admin/exhibits", {
            "hall_name": "测试展厅", "title": "临时展品", "description": "d",
            "media_type": "image", "media_url": "/x.jpg", "sort_order": 9, "status": 0,
        })["data"]
        eid = created["id"]
        client.put(f"/admin/exhibits/{eid}", {
            "hall_name": "测试展厅", "title": "临时展品v2", "description": "d",
            "media_type": "image", "media_url": "/x.jpg", "sort_order": 9, "status": 1})
        items = client.get("/admin/exhibits", params={"keyword": "临时展品"})["data"]
        assert any(e["id"] == eid and e["title"] == "临时展品v2" for e in items)
        client.delete(f"/admin/exhibits/{eid}")
        items = client.get("/admin/exhibits", params={"keyword": "临时展品"})["data"]
        assert not any(e["id"] == eid for e in items)

    def test_create_empty_title_rejected(self, client, admin):
        client.post("/admin/exhibits", {
            "hall_name": " ", "title": "  ", "description": "",
            "media_type": "image", "media_url": "", "sort_order": 0, "status": 1},
            expect_code=40000)

    def test_update_nonexistent(self, client, admin):
        client.put("/admin/exhibits/999999", {
            "hall_name": "x", "title": "x", "description": "",
            "media_type": "image", "media_url": "", "sort_order": 0, "status": 1},
            expect_code=40400)

    def test_delete_nonexistent(self, client, admin):
        client.delete("/admin/exhibits/999999", expect_code=40400)


class TestAnnouncements:
    def test_c_sees_only_published(self, client, admin):
        draft = client.post("/admin/announcements", {
            "title": "草稿公告-不应可见", "content": "x", "type": "notice", "is_published": 0,
        })["data"]
        pub_titles = [a["title"] for a in client.get("/announcements")["data"]]
        assert "草稿公告-不应可见" not in pub_titles
        client.delete(f"/admin/announcements/{draft['id']}")

    def test_publish_flow(self, client, admin):
        a = client.post("/admin/announcements", {
            "title": "发布流程测试", "content": "内容", "type": "activity", "is_published": 0,
        })["data"]
        assert "发布流程测试" not in [x["title"] for x in client.get("/announcements")["data"]]
        client.put(f"/admin/announcements/{a['id']}", {
            "title": "发布流程测试", "content": "内容", "type": "activity", "is_published": 1})
        assert "发布流程测试" in [x["title"] for x in client.get("/announcements")["data"]]
        client.delete(f"/admin/announcements/{a['id']}")
        assert "发布流程测试" not in [x["title"] for x in client.get("/announcements")["data"]]

    def test_empty_title_rejected(self, client, admin):
        client.post("/admin/announcements", {"title": "", "content": "x", "type": "notice"},
                    expect_code=40000)

    def test_update_nonexistent(self, client, admin):
        client.put("/admin/announcements/999999",
                   {"title": "x", "content": "x", "type": "notice"}, expect_code=40400)
