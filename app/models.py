from datetime import datetime
from flask_login import UserMixin
from app import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    school_name = db.Column(db.String(200), default="New Vision Academy")
    tagline = db.Column(db.String(300), default="")
    phone = db.Column(db.String(50), default="")
    phone2 = db.Column(db.String(50), default="")
    phone3 = db.Column(db.String(50), default="")
    email = db.Column(db.String(120), default="")
    address = db.Column(db.String(300), default="")
    google_maps_address = db.Column(db.String(300), default="")
    latitude = db.Column(db.String(30), default="")
    longitude = db.Column(db.String(30), default="")
    registration_no = db.Column(db.String(100), default="")
    pan = db.Column(db.String(50), default="")
    facebook_url = db.Column(db.String(300), default="")
    whatsapp = db.Column(db.String(50), default="")
    established = db.Column(db.String(50), default="")
    grades_offered = db.Column(db.String(100), default="")
    admission_session = db.Column(db.String(50), default="")
    school_type = db.Column(db.String(100), default="")
    student_count = db.Column(db.String(100), default="")
    school_hours = db.Column(db.String(200), default="")
    district = db.Column(db.String(80), default="")
    municipality = db.Column(db.String(100), default="")
    ward = db.Column(db.String(20), default="")
    province = db.Column(db.String(80), default="")
    logo_path = db.Column(db.String(300), default="")
    principal_name = db.Column(db.String(120), default="")
    principal_title = db.Column(db.String(120), default="")
    principal_photo = db.Column(db.String(300), default="")
    principal_message = db.Column(db.Text, default="")
    about_text = db.Column(db.Text, default="")
    meta_description = db.Column(db.String(400), default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class HeroSlide(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    subtitle = db.Column(db.String(400), default="")
    image_path = db.Column(db.String(300), default="")
    button1_text = db.Column(db.String(80), default="")
    button1_url = db.Column(db.String(300), default="")
    button2_text = db.Column(db.String(80), default="")
    button2_url = db.Column(db.String(300), default="")
    badge_text = db.Column(db.String(120), default="")
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), nullable=False)
    content = db.Column(db.Text, default="")
    is_important = db.Column(db.Boolean, default=False)
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), nullable=False)
    slug = db.Column(db.String(280), unique=True, nullable=False)
    excerpt = db.Column(db.String(500), default="")
    content = db.Column(db.Text, default="")
    image_path = db.Column(db.String(300), default="")
    category = db.Column(db.String(80), default="News")
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Blog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), nullable=False)
    slug = db.Column(db.String(280), unique=True, nullable=False)
    excerpt = db.Column(db.String(500), default="")
    content = db.Column(db.Text, default="")
    image_path = db.Column(db.String(300), default="")
    category = db.Column(db.String(80), default="School Life")
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Gallery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), default="")
    image_path = db.Column(db.String(300), nullable=False)
    album = db.Column(db.String(120), default="General")
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Staff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    designation = db.Column(db.String(120), default="")
    department = db.Column(db.String(120), default="")
    photo_path = db.Column(db.String(300), default="")
    bio = db.Column(db.Text, default="")
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PageContent(db.Model):
    """Flexible content blocks: commitments, facilities, offers, etc."""
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), nullable=False, index=True)  # e.g. commitments, facilities, offers
    title = db.Column(db.String(200), default="")
    content = db.Column(db.Text, default="")
    icon = db.Column(db.String(80), default="")
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AdmissionEnquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(120), nullable=False)
    parent_name = db.Column(db.String(120), default="")
    phone = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), default="")
    grade = db.Column(db.String(50), default="")
    message = db.Column(db.Text, default="")
    is_read = db.Column(db.Boolean, default=False)
    reply_message = db.Column(db.Text, default="")
    replied_at = db.Column(db.DateTime, nullable=True)
    auto_replied = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), default="")
    phone = db.Column(db.String(50), default="")
    subject = db.Column(db.String(200), default="")
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PushSubscription(db.Model):
    """Browser push subscriptions for school update notifications."""
    id = db.Column(db.Integer, primary_key=True)
    endpoint = db.Column(db.Text, unique=True, nullable=False)
    p256dh = db.Column(db.String(512), default="")
    auth = db.Column(db.String(256), default="")
    user_agent = db.Column(db.String(300), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SiteNotification(db.Model):
    """Log of notifications sent from admin."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, default="")
    url = db.Column(db.String(300), default="/")
    sent_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
