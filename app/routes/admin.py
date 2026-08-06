import os
import uuid
from datetime import datetime
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    current_app, abort
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from app import db
from app.models import (
    User, Settings, HeroSlide, Notice, News, Blog, Gallery, Staff,
    PageContent, AdmissionEnquiry, ContactMessage, PushSubscription, SiteNotification
)
from app.push_utils import send_push_to_all

admin_bp = Blueprint("admin", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "heic", "heif"}
HEIC_EXTENSIONS = {"heic", "heif"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file_storage, subfolder=""):
    """Save uploaded image to Cloudinary (preferred) or local static/uploads.

    Returns a full https:// Cloudinary URL, or a relative path like uploads/logo/x.jpg.
    Templates must use media_url() so both forms work.
    """
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename):
        return None
    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    folder_key = (subfolder or "misc").strip("/") or "misc"

    # Prefer Cloudinary when configured
    try:
        from app.cloudinary_utils import cloudinary_enabled, upload_to_cloudinary
        if cloudinary_enabled():
            # Reset stream in case it was read
            try:
                file_storage.stream.seek(0)
            except Exception:
                pass
            url = upload_to_cloudinary(file_storage, folder=folder_key)
            if url:
                return url
            current_app.logger.warning("Cloudinary upload returned empty; falling back to local")
            try:
                file_storage.stream.seek(0)
            except Exception:
                pass
    except Exception as e:
        current_app.logger.warning("Cloudinary unavailable: %s", e)

    # Local fallback (dev / if Cloudinary fails)
    upload_root = current_app.config["UPLOAD_FOLDER"]
    dest_dir = os.path.join(upload_root, subfolder) if subfolder else upload_root
    os.makedirs(dest_dir, exist_ok=True)

    if ext in HEIC_EXTENSIONS:
        try:
            from pillow_heif import register_heif_opener
            from PIL import Image
            import io

            register_heif_opener()
            raw = file_storage.read()
            img = Image.open(io.BytesIO(raw))
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            name = f"{uuid.uuid4().hex}.jpg"
            path = os.path.join(dest_dir, name)
            img.save(path, "JPEG", quality=88, optimize=True)
            rel = f"uploads/{subfolder}/{name}" if subfolder else f"uploads/{name}"
            return rel.replace("//", "/")
        except ImportError:
            current_app.logger.warning("HEIC needs pillow-heif or use JPG")
            return None
        except Exception as e:
            current_app.logger.warning("HEIC convert failed: %s", e)
            return None

    name = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(dest_dir, name)
    file_storage.save(path)
    rel = f"uploads/{subfolder}/{name}" if subfolder else f"uploads/{name}"
    return rel.replace("//", "/")


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash("Welcome back!", "success")
            next_url = request.args.get("next") or url_for("admin.dashboard")
            return redirect(next_url)
        flash("Invalid username or password.", "error")
    return render_template("admin/login.html")


@admin_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("admin.login"))


@admin_bp.route("/")
@admin_required
def dashboard():
    stats = {
        "notices": Notice.query.count(),
        "news": News.query.count(),
        "blogs": Blog.query.count(),
        "gallery": Gallery.query.count(),
        "staff": Staff.query.count(),
        "enquiries": AdmissionEnquiry.query.filter_by(is_read=False).count(),
        "messages": ContactMessage.query.filter_by(is_read=False).count(),
    }
    recent_enquiries = AdmissionEnquiry.query.order_by(AdmissionEnquiry.created_at.desc()).limit(5).all()
    recent_messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).limit(5).all()
    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_enquiries=recent_enquiries,
        recent_messages=recent_messages,
    )


# ---------- Settings ----------
@admin_bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    s = Settings.query.first()
    if not s:
        s = Settings()
        db.session.add(s)
        db.session.commit()
    if request.method == "POST":
        fields = [
            "school_name", "tagline", "phone", "phone2", "phone3", "email",
            "address", "google_maps_address", "latitude", "longitude",
            "registration_no", "pan", "facebook_url", "whatsapp", "established",
            "grades_offered", "admission_session", "school_type",
            "student_count", "school_hours", "district", "municipality",
            "ward", "province", "principal_name", "principal_title",
            "principal_message", "about_text", "meta_description",
        ]
        for f in fields:
            setattr(s, f, request.form.get(f, "").strip())
        if request.form.get("remove_logo") == "1":
            s.logo_path = ""
        logo = request.files.get("logo")
        if logo and logo.filename:
            path = save_upload(logo, "logo")
            if path:
                s.logo_path = path
            else:
                flash("Logo could not be saved. Use JPG, PNG, GIF or WebP.", "error")
        if request.form.get("remove_principal_photo") == "1":
            s.principal_photo = ""
        photo = request.files.get("principal_photo")
        if photo and photo.filename:
            path = save_upload(photo, "principal")
            if path:
                s.principal_photo = path
            else:
                flash("Principal photo could not be saved. Use JPG, PNG, GIF or WebP.", "error")
        db.session.commit()
        flash("Settings updated successfully.", "success")
        return redirect(url_for("admin.settings"))
    return render_template("admin/settings.html", s=s)


# ---------- Hero Slides ----------
@admin_bp.route("/slides")
@admin_required
def slides():
    items = HeroSlide.query.order_by(HeroSlide.sort_order).all()
    return render_template("admin/slides.html", items=items)


@admin_bp.route("/slides/new", methods=["GET", "POST"])
@admin_bp.route("/slides/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def slide_form(item_id=None):
    item = HeroSlide.query.get(item_id) if item_id else None
    if request.method == "POST":
        if not item:
            item = HeroSlide()
            db.session.add(item)
        item.title = request.form.get("title", "").strip()
        item.subtitle = request.form.get("subtitle", "").strip()
        item.button1_text = request.form.get("button1_text", "").strip()
        item.button1_url = request.form.get("button1_url", "").strip()
        item.button2_text = request.form.get("button2_text", "").strip()
        item.button2_url = request.form.get("button2_url", "").strip()
        item.badge_text = request.form.get("badge_text", "").strip()
        item.sort_order = int(request.form.get("sort_order") or 0)
        item.is_active = request.form.get("is_active") == "on"
        img = request.files.get("image")
        if img and img.filename:
            path = save_upload(img, "slides")
            if path:
                item.image_path = path
        db.session.commit()
        flash("Slide saved.", "success")
        return redirect(url_for("admin.slides"))
    return render_template("admin/slide_form.html", item=item)


@admin_bp.route("/slides/<int:item_id>/delete", methods=["POST"])
@admin_required
def slide_delete(item_id):
    item = HeroSlide.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Slide deleted.", "success")
    return redirect(url_for("admin.slides"))


# ---------- Notices ----------
@admin_bp.route("/notices")
@admin_required
def notices():
    items = Notice.query.order_by(Notice.published_at.desc()).all()
    return render_template("admin/notices.html", items=items)


@admin_bp.route("/notices/new", methods=["GET", "POST"])
@admin_bp.route("/notices/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def notice_form(item_id=None):
    item = Notice.query.get(item_id) if item_id else None
    if request.method == "POST":
        if not item:
            item = Notice()
            db.session.add(item)
        item.title = request.form.get("title", "").strip()
        item.content = request.form.get("content", "").strip()
        item.is_important = request.form.get("is_important") == "on"
        item.is_active = request.form.get("is_active") == "on"
        pub = request.form.get("published_at")
        if pub:
            try:
                item.published_at = datetime.strptime(pub, "%Y-%m-%d")
            except ValueError:
                pass
        db.session.commit()
        if request.form.get("send_notify") == "on" and item.is_active:
            n = send_push_to_all(
                title=item.title,
                body=(item.content or "New school notice")[:120],
                url=f"/notices/{item.id}",
            )
            failed = getattr(n, "failed", 0)
            if failed:
                flash(f"Notice saved. Sent to {int(n)} device(s), {failed} failed.", "warning")
            else:
                flash(f"Notice saved. Notification sent to {int(n)} device(s).", "success")
        else:
            flash("Notice saved.", "success")
        return redirect(url_for("admin.notices"))
    return render_template("admin/notice_form.html", item=item)


@admin_bp.route("/notices/<int:item_id>/delete", methods=["POST"])
@admin_required
def notice_delete(item_id):
    item = Notice.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Notice deleted.", "success")
    return redirect(url_for("admin.notices"))


# ---------- News ----------
def slugify(text):
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:200] or "item"


@admin_bp.route("/news")
@admin_required
def news():
    items = News.query.order_by(News.published_at.desc()).all()
    return render_template("admin/news.html", items=items)


@admin_bp.route("/news/new", methods=["GET", "POST"])
@admin_bp.route("/news/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def news_form(item_id=None):
    item = News.query.get(item_id) if item_id else None
    if request.method == "POST":
        if not item:
            item = News()
            db.session.add(item)
        item.title = request.form.get("title", "").strip()
        slug = request.form.get("slug", "").strip() or slugify(item.title)
        # ensure unique
        existing = News.query.filter(News.slug == slug, News.id != (item.id or 0)).first()
        if existing:
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"
        item.slug = slug
        item.excerpt = request.form.get("excerpt", "").strip()
        item.content = request.form.get("content", "").strip()
        item.category = request.form.get("category", "News").strip()
        item.is_active = request.form.get("is_active") == "on"
        pub = request.form.get("published_at")
        if pub:
            try:
                item.published_at = datetime.strptime(pub, "%Y-%m-%d")
            except ValueError:
                pass
        img = request.files.get("image")
        if img and img.filename:
            path = save_upload(img, "news")
            if path:
                item.image_path = path
        db.session.commit()
        if request.form.get("send_notify") == "on" and item.is_active:
            n = send_push_to_all(
                title=item.title,
                body=(item.excerpt or item.content or "New school news")[:120],
                url=f"/news/{item.slug}",
            )
            failed = getattr(n, "failed", 0)
            if failed:
                flash(f"News saved. Sent to {int(n)} device(s), {failed} failed.", "warning")
            else:
                flash(f"News saved. Notification sent to {int(n)} device(s).", "success")
        else:
            flash("News saved.", "success")
        return redirect(url_for("admin.news"))
    return render_template("admin/news_form.html", item=item)


@admin_bp.route("/news/<int:item_id>/delete", methods=["POST"])
@admin_required
def news_delete(item_id):
    item = News.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("News deleted.", "success")
    return redirect(url_for("admin.news"))


# ---------- Blog ----------
@admin_bp.route("/blog")
@admin_required
def blog():
    items = Blog.query.order_by(Blog.published_at.desc()).all()
    return render_template("admin/blog.html", items=items)


@admin_bp.route("/blog/new", methods=["GET", "POST"])
@admin_bp.route("/blog/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def blog_form(item_id=None):
    item = Blog.query.get(item_id) if item_id else None
    if request.method == "POST":
        if not item:
            item = Blog()
            db.session.add(item)
        item.title = request.form.get("title", "").strip()
        slug = request.form.get("slug", "").strip() or slugify(item.title)
        existing = Blog.query.filter(Blog.slug == slug, Blog.id != (item.id or 0)).first()
        if existing:
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"
        item.slug = slug
        item.excerpt = request.form.get("excerpt", "").strip()
        item.content = request.form.get("content", "").strip()
        item.category = request.form.get("category", "School Life").strip()
        item.is_active = request.form.get("is_active") == "on"
        pub = request.form.get("published_at")
        if pub:
            try:
                item.published_at = datetime.strptime(pub, "%Y-%m-%d")
            except ValueError:
                pass
        img = request.files.get("image")
        if img and img.filename:
            path = save_upload(img, "blog")
            if path:
                item.image_path = path
        db.session.commit()
        flash("Blog post saved.", "success")
        return redirect(url_for("admin.blog"))
    return render_template("admin/blog_form.html", item=item)


@admin_bp.route("/blog/<int:item_id>/delete", methods=["POST"])
@admin_required
def blog_delete(item_id):
    item = Blog.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Blog post deleted.", "success")
    return redirect(url_for("admin.blog"))


# ---------- Gallery ----------
@admin_bp.route("/gallery")
@admin_required
def gallery():
    items = Gallery.query.order_by(Gallery.sort_order, Gallery.id.desc()).all()
    return render_template("admin/gallery.html", items=items)


@admin_bp.route("/gallery/new", methods=["GET", "POST"])
@admin_bp.route("/gallery/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def gallery_form(item_id=None):
    item = Gallery.query.get(item_id) if item_id else None
    if request.method == "POST":
        if not item:
            item = Gallery()
            db.session.add(item)
        item.title = request.form.get("title", "").strip()
        item.album = request.form.get("album", "General").strip() or "General"
        item.sort_order = int(request.form.get("sort_order") or 0)
        item.is_active = request.form.get("is_active") == "on"
        img = request.files.get("image")
        if img and img.filename:
            path = save_upload(img, "gallery")
            if path:
                item.image_path = path
        if not item.image_path and not item_id:
            flash("Image is required for new gallery item.", "error")
            return render_template("admin/gallery_form.html", item=item)
        db.session.commit()
        flash("Gallery item saved.", "success")
        return redirect(url_for("admin.gallery"))
    return render_template("admin/gallery_form.html", item=item)


@admin_bp.route("/gallery/<int:item_id>/delete", methods=["POST"])
@admin_required
def gallery_delete(item_id):
    item = Gallery.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Gallery item deleted.", "success")
    return redirect(url_for("admin.gallery"))


# ---------- Staff ----------
@admin_bp.route("/staff")
@admin_required
def staff():
    items = Staff.query.order_by(Staff.sort_order, Staff.name).all()
    return render_template("admin/staff.html", items=items)


@admin_bp.route("/staff/new", methods=["GET", "POST"])
@admin_bp.route("/staff/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def staff_form(item_id=None):
    item = Staff.query.get(item_id) if item_id else None
    if request.method == "POST":
        if not item:
            item = Staff()
            db.session.add(item)
        item.name = request.form.get("name", "").strip()
        item.designation = request.form.get("designation", "").strip()
        item.department = request.form.get("department", "").strip()
        item.bio = request.form.get("bio", "").strip()
        item.sort_order = int(request.form.get("sort_order") or 0)
        item.is_active = request.form.get("is_active") == "on"
        img = request.files.get("photo")
        if img and img.filename:
            path = save_upload(img, "staff")
            if path:
                item.photo_path = path
        db.session.commit()
        flash("Staff member saved.", "success")
        return redirect(url_for("admin.staff"))
    return render_template("admin/staff_form.html", item=item)


@admin_bp.route("/staff/<int:item_id>/delete", methods=["POST"])
@admin_required
def staff_delete(item_id):
    item = Staff.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Staff member deleted.", "success")
    return redirect(url_for("admin.staff"))


# ---------- Page Content (commitments, facilities, offers) ----------
@admin_bp.route("/content/<key>")
@admin_required
def content_list(key):
    if key not in ("commitments", "facilities", "offers"):
        abort(404)
    items = PageContent.query.filter_by(key=key).order_by(PageContent.sort_order).all()
    labels = {"commitments": "Commitments", "facilities": "Facilities", "offers": "What We Offer"}
    return render_template("admin/content_list.html", items=items, key=key, label=labels[key])


@admin_bp.route("/content/<key>/new", methods=["GET", "POST"])
@admin_bp.route("/content/<key>/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def content_form(key, item_id=None):
    if key not in ("commitments", "facilities", "offers"):
        abort(404)
    item = PageContent.query.get(item_id) if item_id else None
    if request.method == "POST":
        if not item:
            item = PageContent(key=key)
            db.session.add(item)
        item.title = request.form.get("title", "").strip()
        item.content = request.form.get("content", "").strip()
        item.icon = request.form.get("icon", "").strip()
        item.sort_order = int(request.form.get("sort_order") or 0)
        item.is_active = request.form.get("is_active") == "on"
        db.session.commit()
        flash("Content saved.", "success")
        return redirect(url_for("admin.content_list", key=key))
    labels = {"commitments": "Commitments", "facilities": "Facilities", "offers": "What We Offer"}
    return render_template("admin/content_form.html", item=item, key=key, label=labels[key])


@admin_bp.route("/content/<key>/<int:item_id>/delete", methods=["POST"])
@admin_required
def content_delete(key, item_id):
    item = PageContent.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Content deleted.", "success")
    return redirect(url_for("admin.content_list", key=key))


# ---------- Enquiries & Messages ----------
@admin_bp.route("/enquiries")
@admin_required
def enquiries():
    # Run auto-reply processing when admin opens the inbox
    try:
        from app.routes.public import process_auto_replies
        process_auto_replies()
    except Exception:
        pass
    items = AdmissionEnquiry.query.order_by(AdmissionEnquiry.created_at.desc()).all()
    return render_template("admin/enquiries.html", items=items)


@admin_bp.route("/enquiries/<int:item_id>/read", methods=["POST"])
@admin_required
def enquiry_read(item_id):
    item = AdmissionEnquiry.query.get_or_404(item_id)
    item.is_read = True
    # Marking as read by admin counts as handled — prevents auto-reply
    if not item.replied_at:
        item.replied_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for("admin.enquiries"))


@admin_bp.route("/enquiries/<int:item_id>/delete", methods=["POST"])
@admin_required
def enquiry_delete(item_id):
    item = AdmissionEnquiry.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Enquiry deleted.", "success")
    return redirect(url_for("admin.enquiries"))


@admin_bp.route("/messages")
@admin_required
def messages():
    items = ContactMessage.query.order_by(ContactMessage.created_at.desc()).all()
    return render_template("admin/messages.html", items=items)


@admin_bp.route("/messages/<int:item_id>/read", methods=["POST"])
@admin_required
def message_read(item_id):
    item = ContactMessage.query.get_or_404(item_id)
    item.is_read = True
    db.session.commit()
    return redirect(url_for("admin.messages"))


@admin_bp.route("/messages/<int:item_id>/delete", methods=["POST"])
@admin_required
def message_delete(item_id):
    item = ContactMessage.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Message deleted.", "success")
    return redirect(url_for("admin.messages"))


# ---------- Change password ----------
@admin_bp.route("/password", methods=["GET", "POST"])
@admin_required
def password():
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if not check_password_hash(current_user.password_hash, current):
            flash("Current password is incorrect.", "error")
        elif len(new) < 6:
            flash("New password must be at least 6 characters.", "error")
        elif new != confirm:
            flash("New passwords do not match.", "error")
        else:
            current_user.password_hash = generate_password_hash(new)
            db.session.commit()
            flash("Password updated.", "success")
            return redirect(url_for("admin.dashboard"))
    return render_template("admin/password.html")



# ---------- Push notifications (broadcast) ----------
@admin_bp.route("/notifications", methods=["GET", "POST"])
@admin_required
def notifications():
    if request.method == "POST":
        title = request.form.get("title", "").strip() or "New Vision Academy"
        body = request.form.get("body", "").strip() or "New update from school"
        url = request.form.get("url", "/").strip() or "/"
        result = send_push_to_all(title=title, body=body, url=url)
        n = int(result)
        failed = getattr(result, "failed", 0)
        errors = getattr(result, "errors", []) or []
        if n > 0 and failed == 0:
            flash(f"Notification sent to {n} subscriber(s). Real push works on HTTPS (Render).", "success")
        elif n > 0 and failed > 0:
            flash(
                f"Sent to {n} subscriber(s), {failed} failed. "
                + ("; ".join(errors[:2]) if errors else "Check server logs."),
                "warning",
            )
        else:
            detail = "; ".join(errors[:3]) if errors else (
                "No valid push keys on subscribers, or push service rejected the request. "
                "Ask users to open the site and tap Subscribe again."
            )
            flash(f"Notification sent to 0 subscriber(s). {detail}", "error")
        return redirect(url_for("admin.notifications"))
    all_subs = PushSubscription.query.order_by(PushSubscription.created_at.desc()).all()
    real_subs = sum(1 for s in all_subs if (s.endpoint or "").startswith("https://"))
    logs = SiteNotification.query.order_by(SiteNotification.created_at.desc()).limit(50).all()
    return render_template(
        "admin/notifications.html",
        subs=len(all_subs),
        real_subs=real_subs,
        subscribers=all_subs,
        logs=logs,
    )


@admin_bp.route("/notifications/<int:item_id>/delete", methods=["POST"])
@admin_required
def notification_delete(item_id):
    item = SiteNotification.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Notification deleted.", "success")
    return redirect(url_for("admin.notifications"))


@admin_bp.route("/notifications/clear", methods=["POST"])
@admin_required
def notifications_clear():
    SiteNotification.query.delete()
    db.session.commit()
    flash("All notification history cleared.", "success")
    return redirect(url_for("admin.notifications"))


@admin_bp.route("/subscribers/<int:item_id>/delete", methods=["POST"])
@admin_required
def subscriber_delete(item_id):
    item = PushSubscription.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Subscriber removed.", "success")
    return redirect(url_for("admin.notifications"))
