# CardPilot MVP v1.6

CardPilot is an AI-ready credit-card rewards workspace for:

- user sign up/login/logout
- saving personal credit cards
- best-card recommendations
- new-customer credit card advisor
- CSV/XLSX/PDF statement upload and reward discrepancy detection
- complaint draft generation
- admin analytics
- mobile app starter
- online deployment starter


## PDF statement upload notes

CardPilot v1.6 supports text-based PDF statements, including many rows with formats such as `12 Jun 2026 AMAZON 5,000.00 Dr`. Password-protected PDFs are supported when you enter the statement password. Scanned/image-only PDFs need OCR and should be exported as CSV/XLSX for this MVP.

## Run on Windows

Double-click:

```text
run_windows.bat
```

Then open:

```text
http://127.0.0.1:8000
```

Default local admin:

```text
Email: admin@cardpilot.local
Password: Admin@12345
```

Change this before deployment.

## Check everything

Double-click:

```text
check_all_windows.bat
```

or run:

```bash
python scripts/check_all.py
pytest -q
```

## Admin security

Admins can view user accounts, saved-card counts, statement counts, and activity. Admins cannot view user passwords. Passwords are stored as PBKDF2 hashes. Admins can reset a user password to a new temporary password.

## Online deployment

See:

```text
DEPLOYMENT_GUIDE.md
```

## Mobile app

The mobile app starter is inside:

```text
mobile_app
```

Set the online API URL with:

```text
EXPO_PUBLIC_API_URL
```
