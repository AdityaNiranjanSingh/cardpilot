# CardPilot deployment guide

This version is prepared for local testing, online backend hosting, cloud PostgreSQL, and Android APK sharing.

## What changed in v1.6


- Improved PDF statement upload with wider text extraction, optional password handling, Dr/Cr amount detection, common Indian date formats, and clearer scanned-PDF errors.
- Added PDF upload checks to the automated system test.
- Upgraded the landing page, app workspace, and statement results page with a cleaner professional visual design.
- Expected-only PDF rows are no longer incorrectly treated as missing rewards when actual credited rewards are not visible in the statement.
- Fixed the landing-page white overlay issue by removing the accidental white card background from hero text.
- Improved the landing page and admin portal design.
- Added admin user management with secure password reset.
- Admins cannot view user passwords because passwords are stored as one-way hashes.
- Added mobile app environment-variable support.
- Added `eas.json` for Android preview APK builds.
- Added PostgreSQL URL normalization for Render/Railway-style database URLs.

## Local Windows run

Double-click:

```text
run_windows.bat
```

Then open:

```text
http://127.0.0.1:8000
```

Admin login:

```text
admin@cardpilot.local
Admin@12345
```

Change the admin password before going online.

## Deploy backend to Render using Blueprint

1. Create a new GitHub repository.
2. Upload all files from this folder to that repository.
3. In Render, create a new Blueprint from the repository.
4. Render will read `render.yaml` and create:
   - one web service
   - one PostgreSQL database
5. Set `ADMIN_PASSWORD` in Render environment variables.
6. Deploy.
7. Open your backend URL, for example:

```text
https://cardpilot-web.onrender.com
```

The first startup imports the seed workbook and creates the database tables.

## Required production environment variables

```text
DATABASE_URL=provided-by-render-postgres
SECRET_KEY=long-random-secret
SESSION_HTTPS_ONLY=1
APP_BASE_URL=https://your-cardpilot-backend.onrender.com
CORS_ORIGINS=https://your-cardpilot-backend.onrender.com
ADMIN_EMAIL=your-admin-email@example.com
ADMIN_NAME=CardPilot Admin
ADMIN_PASSWORD=change-this-before-launch
```

## Mobile app after backend deployment

Go to:

```text
mobile_app
```

Install packages:

```bash
npm install
```

For Expo local preview:

```bash
EXPO_PUBLIC_API_URL=https://your-cardpilot-backend.onrender.com npm start
```

For Android APK sharing:

```bash
npm install -g eas-cli
eas login
eas build:configure
eas build -p android --profile preview
```

Before building, edit `mobile_app/eas.json` and set:

```text
EXPO_PUBLIC_API_URL=https://your-cardpilot-backend.onrender.com
```

Expo will give you a download link for the APK after the build finishes.

## Security note

Do not add a feature that lets an admin see user passwords. A professional app should never store plaintext passwords. CardPilot stores password hashes only and supports admin password reset instead.
