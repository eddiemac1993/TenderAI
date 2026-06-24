# TenderAI

TenderAI is a Django procurement assistant for Zambian suppliers and contractors. The first version focuses on practical records first: company profiles, document storage, tender entry/import, quotations, invoices, bid checklists, and placeholder hooks for AI analysis and ZPPA public tender imports.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install django reportlab python-docx pypdf
python manage.py makemigrations
python manage.py migrate
python manage.py seed_core_companies
python manage.py createsuperuser
python manage.py runserver
```

Environment variables:

```bash
set DJANGO_SECRET_KEY=change-me
set DJANGO_DEBUG=1
set DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
set DJANGO_TIME_ZONE=Africa/Lusaka
```

## Production deployment

Recommended platform setup:

- Build command: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
- Start command: `gunicorn tenderai.wsgi:application --log-file -`
- Database: PostgreSQL via `DATABASE_URL`
- Static files: WhiteNoise
- Uploaded media: local disk for small/private deployments; use managed object storage for durable production media

Required environment variables are shown in `.env.example`. Set `TENDERAI_REQUIRE_LOGIN=1` in production so every app page requires authentication.

After first deploy:

```bash
python manage.py createsuperuser
python manage.py seed_core_companies
```

For sensitive company documents, keep HTTPS enabled, use strong admin passwords, and back up PostgreSQL regularly.

## PythonAnywhere with SQLite

For a simple first deployment, you can use SQLite on PythonAnywhere. PythonAnywhere's Django guide says SQLite is the simplest option at this stage, and you should use the Web tab/WSGI app instead of `runserver`.

1. Push this folder to GitHub.
2. Open a PythonAnywhere Bash console.
3. Clone the repo:

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/TenderAI.git
cd TenderAI
```

4. Create and activate a virtual environment:

```bash
mkvirtualenv tenderai --python=python3.13
pip install -r requirements-pythonanywhere.txt
```

If Python 3.13 is not available on your PythonAnywhere account, use the newest Python version shown in the PythonAnywhere Web tab and update `runtime.txt` only for other platforms.

5. Run setup commands:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py seed_core_companies
python manage.py createsuperuser
```

6. In the PythonAnywhere Web tab:

- Add a new manual web app.
- Choose Django/WSGI using your virtualenv.
- Set source code to `/home/YOUR_USERNAME/TenderAI`.
- Set virtualenv to `/home/YOUR_USERNAME/.virtualenvs/tenderai`.
- Edit the WSGI file and paste the contents of `pythonanywhere_wsgi.py`.
- Replace `YOUR_USERNAME` in that file with your PythonAnywhere username.
- Reload the web app.

7. Static/media settings on the Web tab:

- Static URL: `/static/`
- Static directory: `/home/YOUR_USERNAME/TenderAI/staticfiles`
- Media URL: `/media/`
- Media directory: `/home/YOUR_USERNAME/TenderAI/media`

SQLite file path will be `/home/YOUR_USERNAME/TenderAI/db.sqlite3`. Back it up regularly because it will contain your TenderAI data.

Note: PythonAnywhere free accounts restrict outbound internet access. If the public ZPPA domains are not allowed from the account, the in-app scraper will log a failed scrape instead of crashing. Manual ZPPA import and CSV import will still work. A paid PythonAnywhere account or another host may be needed for live public scraping.

Workaround for PythonAnywhere free accounts:

1. Run this locally where ZPPA is reachable:

```bash
python manage.py export_zppa_public_tenders zppa_today.json --today --limit 10
```

2. Open the hosted app and go to **Tenders > Import ZPPA JSON**.
3. Upload `zppa_today.json`.

This keeps the hosted app useful even when PythonAnywhere blocks outbound scraping.

## ZPPA import

Use the public scrape button at `/tenders/`, the manual import page at `/tenders/zppa/import/`, or import a CSV of public tender data:

```bash
python manage.py scrape_zppa_public_tenders --today --limit 10
python manage.py export_zppa_public_tenders zppa_today.json --today --limit 10
```

```bash
python manage.py import_zppa_tenders path\to\zppa_tenders.csv
```

Expected CSV headers: `title,tender_number,procuring_entity,category,closing_date,submission_method,source_url_or_reference`.

This project intentionally does not bypass authentication or scrape protected pages. The scraper reads only visible public tender links from the public e-GP landing page. Future Playwright/Selenium work should be limited to public ZPPA pages and should respect the site terms.

## AI analysis

Tender pages include an upload form for solicitation documents. PDF and DOCX files are converted to text and analyzed with rule-based extractors for required documents, dates, evaluation criteria, forms, bid security, and site visit signals. Replace the rule-based functions in `ai_engine/services.py` with an OpenAI-backed service later, keeping extracted requirements stored as `TenderRequirement` records.

## Exports

Quotations and invoices export to PDF using ReportLab. Bid packs generate both DOCX and PDF files and include cover letter, form of bid, bid checklist, price schedule, company document checklist, company profile summary, similar experience placeholder, litigation declaration, power of attorney, delivery confirmation, and warranty/undertaking sections.
