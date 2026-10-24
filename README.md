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

## Free deployment with Render

The project now includes `render.yaml`, `Procfile`, `wsgi.py`, a `/health` endpoint, `.python-version`, and `.gitignore`.

1. Create a new GitHub repository. Upload the contents of this folder, but never commit `.env`, `.venv`, `instance/`, or `static/uploads/`.
2. In Render, choose **New → Blueprint**, connect the repository, and select the `render.yaml` file.
3. Render creates a free Python web service, installs `requirements.txt`, and uses the production Gunicorn command automatically.
4. Render generates `SECRET_KEY`. If creating the service manually, set a long random `SECRET_KEY`, set the build command to `pip install -r requirements.txt`, the start command to `gunicorn --workers 2 --threads 4 --bind 0.0.0.0:$PORT wsgi:app`, and health check path to `/health`.
5. Open the supplied `onrender.com` URL after deploy completes.

### Important free-tier limitation

This SQLite app is suitable for a free online **demo**. Render's free web services have an ephemeral filesystem: the database and uploaded receipts are lost on a restart, deploy, or idle spin-down. Free services also spin down after 15 minutes of inactivity and can take about a minute to wake up. For permanent public use, migrate the database and uploads to external persistent storage before deploying. See [Render's free-tier documentation](https://render.com/docs/free).
