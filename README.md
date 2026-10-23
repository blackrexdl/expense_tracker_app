# ExpenseTrack — Flask Academic Prototype

A responsive, local web expense tracker built with HTML, CSS, JavaScript, Flask and SQLite. It includes hashed-password login, per-user transactions and categories, filters, CRUD (add/edit/delete), totals, Chart.js daily/weekly/monthly/yearly trends, monthly category reports, and per-category monthly budget alerts.

## Requirements

Python 3.10+ is recommended. SQLite is bundled with Python; no database server is needed.

## Setup and run

1. Open a terminal in this `expense_tracker_app` folder.
2. Create and activate a virtual environment:
   - macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate`
   - Windows: `py -m venv .venv && .venv\Scripts\activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and replace `SECRET_KEY` with a random value. (The app has a development fallback for first run.)
5. Start the app: `python run.py`
6. Visit `http://127.0.0.1:5000`, register, and log in. The SQLite database is automatically initialized in `instance/`.

## Tests

Run `python -m pytest` from this folder. Tests create temporary databases and do not alter your normal data.

## Notes

- Currency display uses ₹ but all values are regular numeric amounts; change the symbol in templates if needed.
- The Chart.js browser dependency is loaded from its public CDN. For a fully offline deployment, download Chart.js locally and update `templates/base.html`.
- This is an academic prototype. For production add CSRF protection, rate limiting, HTTPS, password-reset flows, audit logging, and a production server.
