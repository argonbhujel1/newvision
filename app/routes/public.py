import os
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, flash, redirect, url_for, abort, jsonify, current_app
from app import db
from app.models import (
    Settings, HeroSlide, Notice, News, Blog, Gallery, Staff,
    PageContent, AdmissionEnquiry, ContactMessage, PushSubscription, SiteNotification
)
from app.push_utils import get_vapid_public_key

public_bp = Blueprint("public", __name__)

# Throttle auto-reply processing so it doesn't run on every single request
_last_auto_reply_check = None
_AUTO_REPLY_INTERVAL = timedelta(minutes=15)


def get_settings():
    return Settings.query.first()


def generate_auto_reply(enquiry, settings=None):
    """Build a personalized acknowledgement using the enquiry details."""
    settings = settings or get_settings()
    school = (settings.school_name if settings else None) or "New Vision Academy"
    phone = (settings.phone if settings else None) or ""
    parent = (enquiry.parent_name or "").strip() or "Parent/Guardian"
    student = (enquiry.student_name or "").strip() or "your child"
    grade = (enquiry.grade or "").strip() or "the requested class"
    phone_line = f" For any urgent queries, please call us at {phone}." if phone else ""

    return (
        f"Dear {parent},\n\n"
        f"Your admission enquiry has been received. "
        f"Thank you for your interest in {school}. "
        f"Our school management team is reviewing the details for {student} "
        f"(Grade: {grade}) and will contact you soon.{phone_line}\n\n"
        f"Warm regards,\n"
        f"{school} Management Team"
    )


def process_auto_replies(force=False):
    """
    If an admission enquiry is older than 24 hours and admin has not replied,
    automatically store a personalized acknowledgement (AI-style auto-reply).
    """
    global _last_auto_reply_check
    now = datetime.utcnow()
    if not force and _last_auto_reply_check and (now - _last_auto_reply_check) < _AUTO_REPLY_INTERVAL:
        return 0
    _last_auto_reply_check = now

    cutoff = now - timedelta(hours=24)
    pending = (
        AdmissionEnquiry.query
        .filter(
            AdmissionEnquiry.created_at <= cutoff,
            AdmissionEnquiry.auto_replied.is_(False),
            AdmissionEnquiry.replied_at.is_(None),
        )
        .all()
    )
    if not pending:
        return 0

    settings = get_settings()
    count = 0
    for e in pending:
        e.reply_message = generate_auto_reply(e, settings)
        e.auto_replied = True
        e.replied_at = now
        e.is_read = True
        count += 1
    if count:
        db.session.commit()
        try:
            current_app.logger.info("Auto-replied to %s admission enquir%s", count, "y" if count == 1 else "ies")
        except Exception:
            pass
    return count

@public_bp.route("/sw.js")
def service_worker():
    """Serve SW from site root so scope can cover the whole origin (required for push)."""
    from flask import current_app, send_from_directory, make_response
    resp = make_response(send_from_directory(
        os.path.join(current_app.root_path, "static"), "sw.js"
    ))
    resp.headers["Content-Type"] = "application/javascript; charset=utf-8"
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp




@public_bp.context_processor
def inject_globals():
    settings = get_settings()
    latest_notices = (
        Notice.query.filter_by(is_active=True)
        .order_by(Notice.published_at.desc())
        .limit(5)
        .all()
    )
    return dict(
        settings=settings,
        ticker_notices=latest_notices,
        vapid_public_key=get_vapid_public_key(),
    )


@public_bp.route("/api/push-subscribe", methods=["POST"])
def push_subscribe():
    data = request.get_json(silent=True) or {}
    endpoint = (data.get("endpoint") or "").strip()
    if not endpoint:
        return jsonify({"ok": False, "error": "missing endpoint"}), 400
    keys = data.get("keys") or {}
    existing = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if existing:
        existing.p256dh = keys.get("p256dh") or existing.p256dh
        existing.auth = keys.get("auth") or existing.auth
    else:
        sub = PushSubscription(
            endpoint=endpoint,
            p256dh=keys.get("p256dh") or "",
            auth=keys.get("auth") or "",
            user_agent=(request.headers.get("User-Agent") or "")[:300],
        )
        db.session.add(sub)
    db.session.commit()
    return jsonify({"ok": True})


@public_bp.route("/")
def home():
    # Process pending auto-replies (throttled) when site is visited
    try:
        process_auto_replies()
    except Exception:
        pass

    slides = HeroSlide.query.filter_by(is_active=True).order_by(HeroSlide.sort_order).all()
    notices = Notice.query.filter_by(is_active=True).order_by(Notice.published_at.desc()).limit(3).all()
    news = News.query.filter_by(is_active=True).order_by(News.published_at.desc()).limit(3).all()
    blogs = Blog.query.filter_by(is_active=True).order_by(Blog.published_at.desc()).limit(2).all()
    gallery = Gallery.query.filter_by(is_active=True).order_by(Gallery.sort_order, Gallery.id.desc()).limit(8).all()
    commitments = PageContent.query.filter_by(key="commitments", is_active=True).order_by(PageContent.sort_order).all()
    offers = PageContent.query.filter_by(key="offers", is_active=True).order_by(PageContent.sort_order).all()
    facilities = PageContent.query.filter_by(key="facilities", is_active=True).order_by(PageContent.sort_order).all()
    return render_template(
        "public/home.html",
        slides=slides,
        notices=notices,
        news=news,
        blogs=blogs,
        gallery=gallery,
        commitments=commitments,
        offers=offers,
        facilities=facilities,
    )


@public_bp.route("/about")
@public_bp.route("/about/history")
def about():
    facilities = PageContent.query.filter_by(key="facilities", is_active=True).order_by(PageContent.sort_order).all()
    return render_template("public/about.html", facilities=facilities)


@public_bp.route("/about/principal")
def principal():
    return render_template("public/principal.html")


@public_bp.route("/academics/staff")
def staff():
    members = Staff.query.filter_by(is_active=True).order_by(Staff.sort_order, Staff.name).all()
    return render_template("public/staff.html", members=members)


@public_bp.route("/gallery")
def gallery():
    images = Gallery.query.filter_by(is_active=True).order_by(Gallery.sort_order, Gallery.id.desc()).all()
    albums = sorted({g.album or "General" for g in images})
    album_filter = request.args.get("album")
    if album_filter:
        images = [g for g in images if (g.album or "General") == album_filter]
    return render_template("public/gallery.html", images=images, albums=albums, album_filter=album_filter)


@public_bp.route("/notices")
def notices():
    items = Notice.query.filter_by(is_active=True).order_by(Notice.published_at.desc()).all()
    return render_template("public/notices.html", notices=items)


@public_bp.route("/notices/<int:notice_id>")
def notice_detail(notice_id):
    notice = Notice.query.filter_by(id=notice_id, is_active=True).first_or_404()
    return render_template("public/notice_detail.html", notice=notice)


@public_bp.route("/news")
def news_list():
    items = News.query.filter_by(is_active=True).order_by(News.published_at.desc()).all()
    return render_template("public/news.html", news=items)


@public_bp.route("/news/<slug>")
def news_detail(slug):
    item = News.query.filter_by(slug=slug, is_active=True).first_or_404()
    return render_template("public/news_detail.html", item=item)


@public_bp.route("/blog")
def blog_list():
    items = Blog.query.filter_by(is_active=True).order_by(Blog.published_at.desc()).all()
    return render_template("public/blog.html", blogs=items)


@public_bp.route("/blog/<slug>")
def blog_detail(slug):
    item = Blog.query.filter_by(slug=slug, is_active=True).first_or_404()
    return render_template("public/blog_detail.html", item=item)


@public_bp.route("/admission", methods=["GET", "POST"])
def admission():
    try:
        process_auto_replies()
    except Exception:
        pass
    if request.method == "POST":
        enquiry = AdmissionEnquiry(
            student_name=request.form.get("student_name", "").strip(),
            parent_name=request.form.get("parent_name", "").strip(),
            phone=request.form.get("phone", "").strip(),
            email=request.form.get("email", "").strip(),
            grade=request.form.get("grade", "").strip(),
            message=request.form.get("message", "").strip(),
        )
        if not enquiry.student_name or not enquiry.phone:
            flash("Student name and phone are required.", "error")
        else:
            db.session.add(enquiry)
            db.session.commit()
            flash(
                "Thank you! Your admission enquiry has been received. "
                "Our school management team is reviewing it and will contact you soon.",
                "success",
            )
            return redirect(url_for("public.admission") + "#enquiry")
    return render_template("public/admission.html")


@public_bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        msg = ContactMessage(
            name=request.form.get("name", "").strip(),
            email=request.form.get("email", "").strip(),
            phone=request.form.get("phone", "").strip(),
            subject=request.form.get("subject", "").strip(),
            message=request.form.get("message", "").strip(),
        )
        if not msg.name or not msg.message:
            flash("Name and message are required.", "error")
        else:
            db.session.add(msg)
            db.session.commit()
            flash("Thank you! Your message has been sent.", "success")
            return redirect(url_for("public.contact"))
    return render_template("public/contact.html")


@public_bp.route("/api/notifications/latest")
def notifications_latest():
    """Clients poll this to show alerts (works on LAN without HTTPS)."""
    after_id = request.args.get("after", 0, type=int)
    q = SiteNotification.query
    if after_id:
        q = q.filter(SiteNotification.id > after_id)
    items = q.order_by(SiteNotification.id.asc()).limit(10).all()
    return jsonify({
        "ok": True,
        "items": [
            {
                "id": n.id,
                "title": n.title,
                "body": n.body,
                "url": n.url or "/",
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in items
        ],
    })


@public_bp.route("/api/notifications/poll")
def notifications_poll():
    """Return newest notification id for lightweight poll."""
    last = SiteNotification.query.order_by(SiteNotification.id.desc()).first()
    return jsonify({
        "ok": True,
        "last_id": last.id if last else 0,
        "title": last.title if last else "",
        "body": last.body if last else "",
        "url": (last.url if last else "/") or "/",
    })
