"""内容模块: 场馆信息 / 展厅展品 / 公告 (C端只读 + B端管理)。"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.core.response import ok, BizError, E_PARAM, E_NOT_FOUND
from app.models.models import VenueInfo, Exhibit, Announcement, AuditLog

router = APIRouter()


# ============ 场馆信息 ============
@router.get("/venue")
def get_venue(db: Session = Depends(get_db)):
    v = db.query(VenueInfo).first()
    if not v:
        raise BizError(E_NOT_FOUND, "场馆信息未配置")
    return ok({
        "id": v.id, "name": v.name, "address": v.address,
        "open_time": v.open_time, "traffic_guide": v.traffic_guide,
        "notice": v.notice, "max_daily": v.max_daily, "status": v.status,
    })


class VenueUpdateReq(BaseModel):
    name: str | None = None
    address: str | None = None
    open_time: str | None = None
    traffic_guide: str | None = None
    notice: str | None = None
    max_daily: int | None = None
    status: int | None = None


@router.put("/admin/venue")
def update_venue(req: VenueUpdateReq, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    v = db.query(VenueInfo).first()
    if not v:
        raise BizError(E_NOT_FOUND, "场馆信息未配置")
    for f, val in req.model_dump(exclude_none=True).items():
        setattr(v, f, val)
    db.add(AuditLog(admin_id=admin.id, admin_name=admin.username,
                    action="venue_update", detail=f"更新场馆信息 {req.model_dump(exclude_none=True)}"))
    return ok({"id": v.id})


# ============ 展厅展品 ============
@router.get("/exhibits")
def list_exhibits(hall: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Exhibit).filter(Exhibit.status == 1)
    if hall:
        q = q.filter(Exhibit.hall_name == hall)
    items = q.order_by(Exhibit.hall_name, Exhibit.sort_order).all()
    return ok([{
        "id": e.id, "hall_name": e.hall_name, "title": e.title,
        "description": e.description, "media_type": e.media_type, "media_url": e.media_url,
        "is_special": bool(e.is_special), "price_cent": e.price_cent, "capacity": e.capacity,
    } for e in items])


@router.get("/admin/exhibits")
def admin_list_exhibits(keyword: str | None = None, admin=Depends(get_current_admin),
                        db: Session = Depends(get_db)):
    q = db.query(Exhibit)
    if keyword:
        q = q.filter(Exhibit.title.contains(keyword) | Exhibit.hall_name.contains(keyword))
    items = q.order_by(Exhibit.id.desc()).all()
    return ok([{
        "id": e.id, "hall_name": e.hall_name, "title": e.title,
        "description": e.description, "media_type": e.media_type, "media_url": e.media_url,
        "sort_order": e.sort_order, "status": e.status,
    } for e in items])


class ExhibitReq(BaseModel):
    hall_name: str
    title: str
    description: str = ""
    media_type: str = "image"
    media_url: str | None = None
    sort_order: int = 0
    status: int = 1


@router.post("/admin/exhibits")
def create_exhibit(req: ExhibitReq, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    if not req.title.strip() or not req.hall_name.strip():
        raise BizError(E_PARAM, "展厅与标题不能为空")
    e = Exhibit(**req.model_dump())
    db.add(e)
    db.flush()
    db.add(AuditLog(admin_id=admin.id, admin_name=admin.username,
                    action="exhibit_create", detail=f"新增展品 {req.title}"))
    return ok({"id": e.id})


@router.put("/admin/exhibits/{exhibit_id}")
def update_exhibit(exhibit_id: int, req: ExhibitReq,
                   admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    e = db.query(Exhibit).get(exhibit_id)
    if not e:
        raise BizError(E_NOT_FOUND, "展品不存在")
    for f, val in req.model_dump().items():
        setattr(e, f, val)
    db.add(AuditLog(admin_id=admin.id, admin_name=admin.username,
                    action="exhibit_update", detail=f"更新展品 {req.title}"))
    return ok({"id": e.id})


@router.delete("/admin/exhibits/{exhibit_id}")
def delete_exhibit(exhibit_id: int, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    e = db.query(Exhibit).get(exhibit_id)
    if not e:
        raise BizError(E_NOT_FOUND, "展品不存在")
    db.delete(e)
    db.add(AuditLog(admin_id=admin.id, admin_name=admin.username,
                    action="exhibit_delete", detail=f"删除展品 {e.title}"))
    return ok()


# ============ 公告 ============
@router.get("/announcements")
def list_announcements(db: Session = Depends(get_db)):
    items = (db.query(Announcement)
             .filter(Announcement.is_published == 1)
             .order_by(Announcement.publish_time.desc())
             .all())
    return ok([{
        "id": a.id, "title": a.title, "content": a.content,
        "type": a.type, "publish_time": str(a.publish_time or ""),
    } for a in items])


@router.get("/admin/announcements")
def admin_list_announcements(admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    items = db.query(Announcement).order_by(Announcement.id.desc()).all()
    return ok([{
        "id": a.id, "title": a.title, "content": a.content, "type": a.type,
        "is_published": a.is_published, "publish_time": str(a.publish_time or ""),
    } for a in items])


class AnnouncementReq(BaseModel):
    title: str
    content: str
    type: str = "notice"
    is_published: int = 0


@router.post("/admin/announcements")
def create_announcement(req: AnnouncementReq, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    if not req.title.strip():
        raise BizError(E_PARAM, "标题不能为空")
    a = Announcement(title=req.title, content=req.content, type=req.type,
                     is_published=req.is_published,
                     publish_time=datetime.now() if req.is_published else None)
    db.add(a)
    db.flush()
    db.add(AuditLog(admin_id=admin.id, admin_name=admin.username,
                    action="announcement_create", detail=f"发布公告 {req.title}"))
    return ok({"id": a.id})


@router.put("/admin/announcements/{ann_id}")
def update_announcement(ann_id: int, req: AnnouncementReq,
                        admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    a = db.query(Announcement).get(ann_id)
    if not a:
        raise BizError(E_NOT_FOUND, "公告不存在")
    was_unpub = a.is_published == 0
    a.title, a.content, a.type = req.title, req.content, req.type
    a.is_published = req.is_published
    if req.is_published and was_unpub and not a.publish_time:
        a.publish_time = datetime.now()
    db.add(AuditLog(admin_id=admin.id, admin_name=admin.username,
                    action="announcement_update", detail=f"更新公告 {req.title}"))
    return ok({"id": a.id})


@router.delete("/admin/announcements/{ann_id}")
def delete_announcement(ann_id: int, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    a = db.query(Announcement).get(ann_id)
    if not a:
        raise BizError(E_NOT_FOUND, "公告不存在")
    db.delete(a)
    db.add(AuditLog(admin_id=admin.id, admin_name=admin.username,
                    action="announcement_delete", detail=f"删除公告 {a.title}"))
    return ok()
