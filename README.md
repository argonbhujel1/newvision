# New Vision Academy – School Website

Full-featured school website for **New Vision Academy, Urlabari-8, Morang** with Python (Flask) backend and complete Admin Panel.

## Features

### Public website
- Home with hero slider, stats, principal message, commitments, facilities, gallery, notices, news, blog
- About, Principal message, Staff list, Gallery, Notice board, News, Blog
- Admission enquiry form & Contact form
- Responsive design (navy / gold theme similar to modern boarding school sites)

### Admin panel (`/admin`)
- Login (default: **admin** / **admin123**)
- School settings (name, phones, address, GPS, logo, principal, about text, etc.)
- Hero slides CRUD
- Notices, News, Blog CRUD with images
- Gallery management
- Staff management
- Commitments, Facilities, “What We Offer” content blocks
- Admission enquiries & contact messages inbox
- Change password

## Tech stack
- Python 3 + Flask
- Flask-SQLAlchemy (SQLite)
- Flask-Login
- Jinja2 templates + custom CSS

## Quick start

```bash
cd new_vision_academy
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
python run.py
```

Open:
- Website: http://127.0.0.1:5000
- Admin:   http://127.0.0.1:5000/admin  
  Login: `admin` / `admin123`

**Important:** Change the admin password after first login.

## Production notes
- Set a strong `SECRET_KEY` environment variable
- Use a production WSGI server (e.g. gunicorn): `gunicorn -w 2 -b 0.0.0.0:8000 run:app`
- For uploads and database, ensure `instance/` and `app/static/uploads/` are writable

## School details (seeded)
- **Name:** New Vision Academy  
- **Phone:** +977 98413 33476  
- **Type:** Private English Medium School  
- **Level:** ECD/Nursery to Grade 10 (SEE)  
- **Location:** Urlabari-8, Morang, Koshi Province, Nepal  
- **GPS:** 26.6749, 87.6336  
- **Maps:** JJVP+XP5, Rajghat, Urlabari-8, Morang, Nepal  
- **Hours:** Sunday–Friday 9:00 AM – 5:00 PM (Saturday closed)  
- **Students:** ~228 (IEMIS 2081)

All of the above can be edited from **Admin → School Settings**.


## New features (v2)

- **Floating WhatsApp & Call buttons** – fixed bottom-right on all public pages
- **Loading screen** – shown on first page load
- **Cookie consent** – accept/decline banner before storing preferences
- **Push notifications** – visitors who allow notifications get alerts when admin publishes notices/news or sends a broadcast from **Admin → Push Notifications**
- **WhatsApp number** editable in School Settings
- Improved colour palette (navy / gold / CTA)

### How notifications work
1. Visitor opens the website (must be **HTTPS** on Render) → loading screen → cookie banner
2. After **Accept**, they tap **Subscribe** and allow browser notifications
3. Browser creates a real Web Push subscription (stored on server)
4. Admin publishes a Notice/News with “Send phone notification” checked, **or** uses **Admin → Push Notifications** to broadcast
5. Phones receive the alert **even when the website is closed** (background Web Push)

**Admin → Push Notifications** also lists:
- All sent notifications (with **Delete** / Clear all)
- All subscribers (Web Push vs polling-only) with **Remove**

> After deploying this update, old subscribers should open the site once and tap Subscribe again so a real push endpoint is saved. VAPID keys are included; override with env `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` if needed.

## Mobile & uploads (v3)

- **Mobile-friendly** public site and admin panel (hamburger menu on phone, larger touch targets, safe-area for notched phones)
- **Admin → School Settings** controls name, phones, WhatsApp, address, GPS, logo, principal message, about text, SEO, hours, student count — every letter is editable
- **Hero slides, notices, news, blog, gallery, staff, commitments, facilities, offers** all fully CRUD from admin
- **Images:** PNG, JPG, JPEG, GIF, WebP. HEIC is optional (if `pillow-heif` builds on the host); Safari on iPhone usually uploads JPEG already.


## Image storage (Cloudinary)

Uploads (logo, gallery, slides, news, staff, principal photo) go to **Cloudinary** when configured.

On Render → Environment, set either:

```
CLOUDINARY_URL=cloudinary://617947781794296:YOUR_SECRET@dmmrcq4ro
```

or:

```
CLOUDINARY_CLOUD_NAME=dmmrcq4ro
CLOUDINARY_API_KEY=617947781794296
CLOUDINARY_API_SECRET=YOUR_SECRET
```

If Cloudinary is unavailable, files fall back to local `app/static/uploads/` (ephemeral on Render free disk).
