import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "admin.login"
login_manager.login_message_category = "warning"


def create_app():
    app = Flask(__name__)
    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "nva-change-this-secret-key-in-production-2026")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "instance", "school.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = os.path.join(basedir, "app", "static", "uploads")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(os.path.join(basedir, "instance"), exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    @app.template_filter("media_url")
    def media_url_filter(path):
        """Resolve local upload path or absolute Cloudinary URL for <img src>."""
        if not path:
            return ""
        p = str(path).strip()
        if p.startswith("http://") or p.startswith("https://") or p.startswith("//"):
            return p
        from flask import url_for
        return url_for("static", filename=p)

    def media_url(path):
        return media_url_filter(path)

    app.jinja_env.globals["media_url"] = media_url


    from app.models import User, Settings, Notice, News, Blog, Gallery, HeroSlide, Staff, PageContent, PushSubscription, SiteNotification

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.routes.public import public_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    with app.app_context():
        db.create_all()
        ensure_schema()
        seed_data()

    return app



def ensure_schema():
    """Add missing columns to existing SQLite DB (simple migration)."""
    from sqlalchemy import text, inspect
    insp = inspect(db.engine)
    tables = insp.get_table_names()

    # Settings columns
    if "settings" in tables:
        cols = {c["name"] for c in insp.get_columns("settings")}
        alters = []
        wanted = {
            "whatsapp": "VARCHAR(50) DEFAULT ''",
            "phone2": "VARCHAR(50) DEFAULT ''",
            "phone3": "VARCHAR(50) DEFAULT ''",
            "google_maps_address": "VARCHAR(300) DEFAULT ''",
            "latitude": "VARCHAR(30) DEFAULT ''",
            "longitude": "VARCHAR(30) DEFAULT ''",
            "logo_path": "VARCHAR(300) DEFAULT ''",
            "principal_photo": "VARCHAR(300) DEFAULT ''",
            "principal_name": "VARCHAR(120) DEFAULT ''",
            "principal_title": "VARCHAR(120) DEFAULT ''",
            "principal_message": "TEXT DEFAULT ''",
            "about_text": "TEXT DEFAULT ''",
            "meta_description": "VARCHAR(400) DEFAULT ''",
            "school_hours": "VARCHAR(200) DEFAULT ''",
            "student_count": "VARCHAR(100) DEFAULT ''",
            "school_type": "VARCHAR(100) DEFAULT ''",
            "admission_session": "VARCHAR(50) DEFAULT ''",
            "grades_offered": "VARCHAR(100) DEFAULT ''",
            "established": "VARCHAR(50) DEFAULT ''",
            "district": "VARCHAR(80) DEFAULT ''",
            "municipality": "VARCHAR(100) DEFAULT ''",
            "ward": "VARCHAR(20) DEFAULT ''",
            "province": "VARCHAR(80) DEFAULT ''",
            "registration_no": "VARCHAR(100) DEFAULT ''",
            "pan": "VARCHAR(50) DEFAULT ''",
            "facebook_url": "VARCHAR(300) DEFAULT ''",
            "tagline": "VARCHAR(300) DEFAULT ''",
        }
        for name, typ in wanted.items():
            if name not in cols:
                alters.append(f"ALTER TABLE settings ADD COLUMN {name} {typ}")
        with db.engine.begin() as conn:
            for sql in alters:
                try:
                    conn.execute(text(sql))
                except Exception:
                    pass
        if alters:
            print(f"[schema] added settings columns: {[a.split()[5] for a in alters]}")

    # AdmissionEnquiry columns for auto-reply feature
    if "admission_enquiry" in tables:
        cols = {c["name"] for c in insp.get_columns("admission_enquiry")}
        alters = []
        wanted = {
            "reply_message": "TEXT DEFAULT ''",
            "replied_at": "DATETIME",
            "auto_replied": "BOOLEAN DEFAULT 0",
        }
        for name, typ in wanted.items():
            if name not in cols:
                alters.append(f"ALTER TABLE admission_enquiry ADD COLUMN {name} {typ}")
        with db.engine.begin() as conn:
            for sql in alters:
                try:
                    conn.execute(text(sql))
                except Exception:
                    pass
        if alters:
            print(f"[schema] added admission_enquiry columns: {[a.split()[5] for a in alters]}")


def seed_data():
    """Seed default admin and school settings if empty."""
    from app.models import User, Settings, Notice, News, Blog, Gallery, HeroSlide, Staff, PageContent, PushSubscription, SiteNotification
    from werkzeug.security import generate_password_hash
    from datetime import datetime, date

    if not User.query.filter_by(username="admin").first():
        admin = User(
            username="admin",
            email="admin@newvisionacademy.edu.np",
            password_hash=generate_password_hash("admin123"),
            is_admin=True,
        )
        db.session.add(admin)

    if not Settings.query.first():
        settings = Settings(
            school_name="New Vision Academy",
            tagline="Education Is The Light Of Life",
            phone="+977 98413 33476",
            phone2="",
            phone3="",
            email="info@newvisionacademy.edu.np",
            address="Urlabari-8, Morang, Koshi Province, Nepal",
            google_maps_address="JJVP+XP5, Rajghat, Urlabari-8, Morang, Nepal",
            latitude="26.6749",
            longitude="87.6336",
            registration_no="",
            pan="",
            facebook_url="",
            whatsapp="9779841333476",
            established="205X BS",
            grades_offered="ECD / Nursery – Grade 10 (SEE)",
            admission_session="2083",
            school_type="Private English Medium School",
            student_count="Approximately 228 students (IEMIS 2081)",
            school_hours="Sunday–Friday: 9:00 AM – 5:00 PM | Saturday: Closed",
            district="Morang",
            municipality="Urlabari Municipality",
            ward="8",
            province="Koshi",
            logo_path="",
            principal_name="Principal Name",
            principal_title="Principal",
            principal_message=(
                "Welcome to New Vision Academy. We are committed to providing quality English-medium "
                "education in a safe, disciplined and child-friendly environment. Our focus is on "
                "academic excellence, character development and preparing every student for success "
                "in SEE and beyond."
            ),
            about_text=(
                "New Vision Academy is a private English medium school located in Urlabari-8, Morang, "
                "Koshi Province, Nepal. We offer education from ECD/Nursery to Grade 10 (SEE). "
                "The school provides smart classrooms, computer and science laboratories, library, "
                "sports, ECA and cultural programs with experienced teaching staff in a child-friendly environment."
            ),
            meta_description="New Vision Academy, Urlabari-8, Morang – Private English Medium School from ECD/Nursery to Grade 10 (SEE).",
        )
        db.session.add(settings)

    if not PageContent.query.filter_by(key="commitments").first():
        commitments = [
            ("Experienced Teachers", "A dedicated teaching team supports classroom learning, discipline and student progress every day."),
            ("Technology Friendly Learning", "Smart classrooms and computer laboratory help students learn with modern digital tools."),
            ("Child Friendly Environment", "Safe, welcoming classrooms and a culture of care and encouragement."),
            ("Science & Library", "Well-equipped science laboratory and library support practical and research-based learning."),
            ("Sports & ECA", "Sports, physical education, cultural programs and extracurricular activities for all-round growth."),
            ("SEE Preparation", "Focused examination and SEE preparation to help students achieve strong results."),
        ]
        for i, (title, desc) in enumerate(commitments):
            db.session.add(PageContent(key="commitments", title=title, content=desc, sort_order=i, is_active=True))

    if not PageContent.query.filter_by(key="facilities").first():
        facilities = [
            "English-medium education",
            "Nursery (ECD) to Grade 10 (SEE)",
            "Smart classrooms",
            "Computer laboratory",
            "Science laboratory",
            "Library",
            "Sports and physical education",
            "Extracurricular Activities (ECA)",
            "Cultural programs",
            "Experienced teaching staff",
            "Child-friendly classrooms",
            "Examination and SEE preparation",
            "Clean drinking water",
            "Separate toilets for boys and girls",
            "School assembly ground",
            "Parent–Teacher interaction programs",
        ]
        for i, f in enumerate(facilities):
            db.session.add(PageContent(key="facilities", title=f, content="", sort_order=i, is_active=True))

    if not PageContent.query.filter_by(key="offers").first():
        offers = [
            ("Project and Presentation Based Work", "Students learn by doing through practical tasks, classroom presentation and guided participation."),
            ("CCA / ECA Opportunities", "Music, dance, art, sports and school activities support confident all-round development."),
            ("Sports Training", "Physical education and sports help students stay active, disciplined and collaborative."),
            ("Smart Classrooms & Labs", "Technology-friendly learning with computer and science laboratories."),
            ("Safe and Disciplined School", "A school culture that values safety, structure and respectful behaviour."),
            ("Parent–Teacher Interaction", "Regular communication and programs to keep families involved in student progress."),
        ]
        for i, (title, desc) in enumerate(offers):
            db.session.add(PageContent(key="offers", title=title, content=desc, sort_order=i, is_active=True))

    if not HeroSlide.query.first():
        slides = [
            HeroSlide(
                title="Admission Open for 2083 B.S.",
                subtitle="A disciplined, child-friendly learning space in Urlabari-8, Morang for ECD to Grade 10.",
                button1_text="Admission Open",
                button1_url="/admission",
                button2_text="Contact School",
                button2_url="/contact",
                badge_text="ADMISSION OPEN FOR 2083 B.S.",
                sort_order=0,
                is_active=True,
            ),
            HeroSlide(
                title="Education Is The Light Of Life",
                subtitle="New Vision Academy – Private English Medium School",
                button1_text="Learn More",
                button1_url="/about",
                button2_text="Gallery",
                button2_url="/gallery",
                badge_text="",
                sort_order=1,
                is_active=True,
            ),
            HeroSlide(
                title="Quality Education from ECD to SEE",
                subtitle="Smart classrooms, labs, sports and experienced teachers in Urlabari.",
                button1_text="Our Facilities",
                button1_url="/about",
                button2_text="Apply Now",
                button2_url="/admission",
                badge_text="",
                sort_order=2,
                is_active=True,
            ),
        ]
        for s in slides:
            db.session.add(s)

    if not Notice.query.first():
        notices = [
            Notice(
                title="Admission Open for Session 2083",
                content="New Vision Academy welcomes new admissions from ECD/Nursery to Grade 10 for the academic session 2083. School visits and parent enquiries are welcome.",
                is_important=True,
                published_at=datetime(2026, 4, 1),
                is_active=True,
            ),
            Notice(
                title="School Visits and Parent Enquiries Are Welcome",
                content="Parents and guardians are invited to visit the school during school hours (Sunday–Friday, 9:00 AM – 5:00 PM) to learn more about our programs and facilities.",
                is_important=False,
                published_at=datetime(2026, 3, 15),
                is_active=True,
            ),
            Notice(
                title="Academic Calendar 2083",
                content="The academic calendar and important dates for session 2083 will be shared with enrolled students and displayed on the notice board.",
                is_important=False,
                published_at=datetime(2026, 3, 1),
                is_active=True,
            ),
        ]
        for n in notices:
            db.session.add(n)

    if not News.query.first():
        news_items = [
            News(
                title="Welcome to the New Academic Session",
                slug="welcome-new-session",
                excerpt="New Vision Academy begins the new academic year with renewed focus on quality learning and student growth.",
                content="New Vision Academy is pleased to welcome students and families to the new academic session. We remain committed to English-medium education, character development and preparing every learner for success.",
                category="School News",
                published_at=datetime(2026, 4, 10),
                is_active=True,
            ),
            News(
                title="School Visits Continue for New Families",
                slug="school-visits-new-families",
                excerpt="Campus visits are open for families considering admission to New Vision Academy.",
                content="We encourage parents to visit our campus in Urlabari-8 to see our classrooms, labs and facilities and meet our teaching staff.",
                category="School Visit",
                published_at=datetime(2026, 3, 10),
                is_active=True,
            ),
        ]
        for n in news_items:
            db.session.add(n)

    if not Blog.query.first():
        blogs = [
            Blog(
                title="Building a Child-Friendly Learning Space",
                slug="building-child-friendly-learning-space",
                excerpt="A supportive school culture is one of the strongest foundations for steady learning and character growth.",
                content="At New Vision Academy we believe that a child-friendly environment—safe classrooms, encouraging teachers and balanced activities—helps every student learn with confidence and joy.",
                category="School Life",
                published_at=datetime(2026, 3, 18),
                is_active=True,
            ),
            Blog(
                title="Why Project Learning Matters",
                slug="why-project-learning-matters",
                excerpt="Project-based learning helps students build confidence, teamwork and real understanding beyond memorisation.",
                content="Through projects and presentations, students at New Vision Academy develop practical skills, communication and deeper understanding of concepts.",
                category="Learning",
                published_at=datetime(2026, 3, 14),
                is_active=True,
            ),
        ]
        for b in blogs:
            db.session.add(b)

    if not Staff.query.first():
        staff = [
            Staff(name="Principal Name", designation="Principal", department="Administration", sort_order=0, is_active=True),
            Staff(name="Coordinator Name", designation="Academic Coordinator", department="Academics", sort_order=1, is_active=True),
        ]
        for s in staff:
            db.session.add(s)

    db.session.commit()
