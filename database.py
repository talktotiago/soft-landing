import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.environ.get('DB_PATH', os.path.join(os.path.dirname(__file__), 'soft_landing.db'))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS city_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city_name TEXT NOT NULL UNIQUE,
            data TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            quantity REAL DEFAULT 1,
            unit TEXT DEFAULT 'unit',
            price REAL DEFAULT 0
        )
    ''')
    try:
        cursor.execute('ALTER TABLE market_items ADD COLUMN price REAL DEFAULT 0')
    except Exception:
        pass
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY DEFAULT 1,
            name TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            currency TEXT NOT NULL DEFAULT 'USD',
            budget REAL DEFAULT 0
        )
    ''')
    try:
        cursor.execute('ALTER TABLE profile ADD COLUMN budget REAL DEFAULT 0')
    except Exception:
        pass
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS youtube_cache (
            city_name TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS calculator_data (
            id INTEGER PRIMARY KEY DEFAULT 1,
            data TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_comparisons (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            cities     TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def get_profile():
    conn = get_db()
    try:
        row = conn.execute('SELECT * FROM profile WHERE id = 1').fetchone()
        return dict(row) if row else {'name': '', 'email': '', 'currency': 'USD', 'budget': 0.0}
    finally:
        conn.close()


def save_profile(name, email, currency, budget=0.0):
    conn = get_db()
    try:
        conn.execute(
            'INSERT OR REPLACE INTO profile (id, name, email, currency, budget) VALUES (1, ?, ?, ?, ?)',
            (name, email, currency, float(budget or 0))
        )
        conn.commit()
    finally:
        conn.close()


def save_report(city_name, data):
    conn = get_db()
    try:
        conn.execute(
            'INSERT OR REPLACE INTO city_reports (city_name, data, created_at) VALUES (?, ?, ?)',
            (city_name, json.dumps(data), datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        conn.commit()
    finally:
        conn.close()


def get_report(city_name):
    conn = get_db()
    try:
        row = conn.execute(
            'SELECT data FROM city_reports WHERE LOWER(city_name) = LOWER(?)',
            (city_name,)
        ).fetchone()
        return json.loads(row['data']) if row else None
    finally:
        conn.close()


def get_report_age(city_name):
    conn = get_db()
    try:
        row = conn.execute(
            'SELECT created_at FROM city_reports WHERE LOWER(city_name) = LOWER(?)',
            (city_name,)
        ).fetchone()
        return row['created_at'] if row else None
    finally:
        conn.close()


def save_youtube_cache(city_name, data):
    conn = get_db()
    try:
        conn.execute(
            'INSERT OR REPLACE INTO youtube_cache (city_name, data, created_at) VALUES (?, ?, ?)',
            (city_name, json.dumps(data), datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        conn.commit()
    finally:
        conn.close()


def get_youtube_cache(city_name):
    conn = get_db()
    try:
        row = conn.execute(
            'SELECT data FROM youtube_cache WHERE LOWER(city_name) = LOWER(?)',
            (city_name,)
        ).fetchone()
        return json.loads(row['data']) if row else None
    finally:
        conn.close()


def get_all_reports(limit=None):
    conn = get_db()
    try:
        query = 'SELECT id, city_name, data, created_at FROM city_reports ORDER BY created_at DESC'
        if limit:
            query += f' LIMIT {int(limit)}'
        rows = conn.execute(query).fetchall()
        result = []
        for r in rows:
            entry = {'id': r['id'], 'city_name': r['city_name'], 'created_at': r['created_at']}
            try:
                entry['country'] = json.loads(r['data']).get('country', '')
            except Exception:
                entry['country'] = ''
            result.append(entry)
        return result
    finally:
        conn.close()


def delete_report(report_id):
    conn = get_db()
    try:
        conn.execute('DELETE FROM city_reports WHERE id = ?', (report_id,))
        conn.commit()
    finally:
        conn.close()


def save_calculator_data(data: dict):
    conn = get_db()
    try:
        conn.execute(
            'INSERT OR REPLACE INTO calculator_data (id, data, updated_at) VALUES (1, ?, ?)',
            (json.dumps(data), datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        conn.commit()
    finally:
        conn.close()


def get_calculator_data() -> dict:
    conn = get_db()
    try:
        row = conn.execute('SELECT data FROM calculator_data WHERE id = 1').fetchone()
        return json.loads(row['data']) if row else {}
    finally:
        conn.close()


def save_market_items(items):
    conn = get_db()
    try:
        conn.execute('DELETE FROM market_items')
        for item in items:
            conn.execute(
                'INSERT INTO market_items (item_name, quantity, unit, price) VALUES (?, ?, ?, ?)',
                (item.get('name', ''), float(item.get('quantity', 1)),
                 item.get('unit', 'unit'), float(item.get('price', 0)))
            )
        conn.commit()
    finally:
        conn.close()


def get_market_items():
    conn = get_db()
    try:
        return [dict(r) for r in conn.execute('SELECT * FROM market_items ORDER BY id').fetchall()]
    finally:
        conn.close()


def save_comparison(name, cities):
    conn = get_db()
    try:
        cur = conn.execute(
            'INSERT INTO saved_comparisons (name, cities) VALUES (?, ?)',
            (name, json.dumps(cities))
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_all_comparisons():
    conn = get_db()
    try:
        rows = conn.execute(
            'SELECT id, name, cities, created_at FROM saved_comparisons ORDER BY created_at DESC'
        ).fetchall()
        result = []
        for r in rows:
            entry = dict(r)
            try:
                entry['cities'] = json.loads(r['cities'])
            except Exception:
                entry['cities'] = []
            result.append(entry)
        return result
    finally:
        conn.close()


def update_comparison(comp_id, name, cities):
    conn = get_db()
    try:
        conn.execute(
            'UPDATE saved_comparisons SET name = ?, cities = ? WHERE id = ?',
            (name, json.dumps(cities), comp_id)
        )
        conn.commit()
    finally:
        conn.close()


def delete_comparison(comp_id):
    conn = get_db()
    try:
        conn.execute('DELETE FROM saved_comparisons WHERE id = ?', (comp_id,))
        conn.commit()
    finally:
        conn.close()
