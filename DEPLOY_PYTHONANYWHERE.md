# 🚀 BookMyGround — PythonAnywhere Deployment Guide

> Step-by-step guide. Don't skip any step.

---

## Step 1 — Open PythonAnywhere Bash Console

1. Go to [www.pythonanywhere.com](https://www.pythonanywhere.com) and **log in**
2. Go to **Dashboard** → **Consoles** tab
3. Under "Start a new console", click **Bash**

---

## Step 2 — Clone from GitHub

In the Bash console, run:

```bash
cd ~
git clone https://github.com/BaluG123/BookMyGround.git
cd BookMyGround
```

---

## Step 3 — Create Virtual Environment

PythonAnywhere has Python 3.10 pre-installed. Use it:

```bash
mkvirtualenv --python=/usr/bin/python3.10 bookmyground-venv
```

> This creates the virtualenv AND activates it. You'll see `(bookmyground-venv)` in your prompt.

If you ever need to reactivate later:
```bash
workon bookmyground-venv
```

---

## Step 4 — Install Dependencies

```bash
cd ~/BookMyGround
pip install -r requirements.txt
```

Wait for all packages to install (takes 2-3 minutes).

---

## Step 5 — Create the `.env` File

```bash
cd ~/BookMyGround
nano .env
```

Paste this content (replace `YOUR_USERNAME` with your PythonAnywhere username):

```
SECRET_KEY=bmg-prod-change-this-to-a-random-50-char-string-abc123xyz
DEBUG=False
ALLOWED_HOSTS=YOUR_USERNAME.pythonanywhere.com
FIREBASE_CREDENTIALS=firebase/serviceAccountKey.json
CORS_ALLOWED_ORIGINS=https://YOUR_USERNAME.pythonanywhere.com
CSRF_TRUSTED_ORIGINS=https://YOUR_USERNAME.pythonanywhere.com
```

Save: Press `Ctrl + O`, then `Enter`, then `Ctrl + X` to exit nano.

> ⚠️ Replace `YOUR_USERNAME` with your actual PythonAnywhere username (e.g., `BaluG123`)

---

## Step 6 — Run Migrations & Collect Static Files

```bash
cd ~/BookMyGround
python manage.py migrate
python manage.py collectstatic --noinput
```

---

## Step 7 — Create Superuser

```bash
python manage.py createsuperuser
```

Enter:
- Email: `admin@bookmyground.com` (or whatever you want)
- Full name: `Admin`
- Password: (choose a strong password)

---

## Step 8 — Seed Amenities Data

```bash
python manage.py shell -c "
from grounds.models import Amenity
amenities = [
    ('Parking', 'parking'), ('Drinking Water', 'water'),
    ('Washroom', 'washroom'), ('Changing Room', 'changing-room'),
    ('Floodlights', 'floodlight'), ('First Aid', 'first-aid'),
    ('Cafeteria', 'cafe'), ('Seating Area', 'seat'),
    ('Scoreboard', 'scoreboard'), ('Wi-Fi', 'wifi'),
    ('CCTV', 'cctv'), ('Locker Room', 'locker'),
    ('Shower', 'shower'), ('Equipment Rental', 'equipment'),
    ('Coaching Available', 'coach'),
]
for name, icon in amenities:
    Amenity.objects.get_or_create(name=name, defaults={'icon': icon})
print(f'Seeded {Amenity.objects.count()} amenities.')
"
```

---

## Step 9 — Configure the Web App

1. Go to PythonAnywhere **Dashboard**
2. Click the **Web** tab
3. Click **"Add a new web app"**
4. Click **Next** (on the domain page — it will be `YOUR_USERNAME.pythonanywhere.com`)
5. Select **"Manual configuration"** (NOT Django option)
6. Select **Python 3.10**
7. Click **Next**

---

## Step 10 — Configure WSGI File

On the **Web** tab, find the **"WSGI configuration file"** link — it will look like:
```
/var/www/YOUR_USERNAME_pythonanywhere_com_wsgi.py
```

Click it to edit. **Delete ALL existing content** and replace with:

```python
import os
import sys
from dotenv import load_dotenv

# Add your project directory to the sys.path
project_home = '/home/YOUR_USERNAME/BookMyGround'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Load environment variables
load_dotenv(os.path.join(project_home, '.env'))

# Set Django settings module
os.environ['DJANGO_SETTINGS_MODULE'] = 'bookmyground.settings'

# Import Django WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

> ⚠️ Replace `YOUR_USERNAME` with your actual PythonAnywhere username!

Click **Save**.

---

## Step 11 — Set the Virtualenv Path

On the **Web** tab, scroll to **"Virtualenv"** section:

Enter this path:
```
/home/YOUR_USERNAME/.virtualenvs/bookmyground-venv
```

Press Enter/Click the checkmark to save.

---

## Step 12 — Configure Static Files

On the **Web** tab, scroll to **"Static files"** section.

Add these two entries:

| URL | Directory |
|---|---|
| `/static/` | `/home/YOUR_USERNAME/BookMyGround/staticfiles` |
| `/media/` | `/home/YOUR_USERNAME/BookMyGround/media` |

Click the "Enter" or checkmark after each entry.

---

## Step 13 — Reload & Test!

1. Go back to the top of the **Web** tab
2. Click the green **"Reload YOUR_USERNAME.pythonanywhere.com"** button
3. Visit your site:

### Test URLs:

| What | URL |
|---|---|
| **API Docs (Swagger)** | `https://YOUR_USERNAME.pythonanywhere.com/api/docs/` |
| **Admin Panel** | `https://YOUR_USERNAME.pythonanywhere.com/admin/` |
| **API Root** | `https://YOUR_USERNAME.pythonanywhere.com/api/v1/grounds/` |
| **Amenities** | `https://YOUR_USERNAME.pythonanywhere.com/api/v1/grounds/amenities/` |

---

## 🔧 Troubleshooting

### If you see "Something went wrong" or a 500 error:

1. Go to the **Web** tab
2. Click **"Log files"** → **Error log**
3. Check the last few lines for the actual error

### Common issues:

| Error | Fix |
|---|---|
| `ModuleNotFoundError` | Virtualenv path is wrong. Check Step 11 |
| `DisallowedHost` | Your username in `.env` `ALLOWED_HOSTS` is wrong. Fix in Step 5 |
| `CSRF verification failed` | Update `CSRF_TRUSTED_ORIGINS` in `.env` with `https://` prefix |
| `Static files 404` | Re-run `python manage.py collectstatic --noinput` and check Step 12 paths |

### How to check error log quickly:
```bash
cat /var/log/YOUR_USERNAME.pythonanywhere.com.error.log | tail -30
```

---

## 📦 How to Update After Code Changes

Whenever you push new code to GitHub, run this on PythonAnywhere Bash:

```bash
cd ~/BookMyGround
git pull
workon bookmyground-venv
pip install -r requirements.txt    # only if dependencies changed
python manage.py migrate           # only if models changed
python manage.py collectstatic --noinput
```

Then go to **Web** tab → click **"Reload"**.

---

## 🔄 React Native Connection

Once deployed, update your React Native API client base URL:

```typescript
// src/api/client.ts
const API_BASE_URL = 'https://YOUR_USERNAME.pythonanywhere.com/api/v1';
```

All endpoints work exactly the same — just the base URL changes from `localhost:8001` to the PythonAnywhere domain.

---

## ✅ Deployment Checklist

```
[ ] Step 1  — Opened Bash console
[ ] Step 2  — Cloned repo from GitHub
[ ] Step 3  — Created virtualenv (bookmyground-venv)
[ ] Step 4  — Installed requirements
[ ] Step 5  — Created .env with correct username
[ ] Step 6  — Ran migrations + collectstatic
[ ] Step 7  — Created superuser
[ ] Step 8  — Seeded amenities
[ ] Step 9  — Created web app (manual config, Python 3.10)
[ ] Step 10 — Configured WSGI file
[ ] Step 11 — Set virtualenv path
[ ] Step 12 — Added static + media file mappings
[ ] Step 13 — Reloaded & tested
```
