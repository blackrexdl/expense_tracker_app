import os, sqlite3
from datetime import date
from functools import wraps
from flask import Flask, g, session, redirect, url_for
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        return False

def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True, template_folder='../templates', static_folder='../static')
    app.config.from_object('config.Config')
    if test_config: app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)
    def get_db():
        if 'db' not in g:
            g.db = sqlite3.connect(app.config['DATABASE']); g.db.row_factory = sqlite3.Row
            g.db.execute('PRAGMA foreign_keys = ON')
        return g.db
    @app.teardown_appcontext
    def close_db(_=None):
        db = g.pop('db', None)
        if db: db.close()
    app.get_db = get_db
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql') as f: db.executescript(f.read().decode())
        db.commit()
    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if 'user_id' not in session: return redirect(url_for('login'))
            return view(*args, **kwargs)
        return wrapped
    app.login_required = login_required
    from .routes import register_routes
    register_routes(app)
    return app
