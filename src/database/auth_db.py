import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_reset_code():
    return secrets.token_hex(4).upper()  # 8-character code

def save_reset_code(identifier, code):
    conn = sqlite3.connect('medical_portal.db')
    c = conn.cursor()
    expires = datetime.now() + timedelta(hours=1)
    c.execute("INSERT OR REPLACE INTO password_reset (email, reset_code, expires) VALUES (?, ?, ?)", (identifier, code, expires))
    conn.commit()
    conn.close()

def verify_reset_code(identifier, code):
    conn = sqlite3.connect('medical_portal.db')
    c = conn.cursor()
    c.execute("SELECT reset_code, expires FROM password_reset WHERE email=?", (identifier,))
    row = c.fetchone()
    conn.close()
    if row and row[0] == code and datetime.now() < datetime.fromisoformat(row[1]):
        return True
    return False

def reset_password(identifier, new_password):
    conn = sqlite3.connect('medical_portal.db')
    c = conn.cursor()
    hashed_pw = hash_password(new_password)
    if "@" in identifier:
        c.execute("UPDATE users SET password=? WHERE email=?", (hashed_pw, identifier))
    else:
        c.execute("UPDATE users SET password=? WHERE username=?", (hashed_pw, identifier))
    conn.commit()
    conn.close()
    return c.rowcount > 0

def get_user_by_email(email):
    if not email:
        return None
    email = email.strip().lower()
    conn = sqlite3.connect('medical_portal.db')
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE LOWER(email)=?", (email,))
    user = c.fetchone()
    conn.close()
    return user[0] if user else None

def get_user_by_username(username):
    if not username:
        return None
    username = username.strip()
    conn = sqlite3.connect('medical_portal.db')
    c = conn.cursor()
    c.execute("SELECT username, email FROM users WHERE LOWER(username)=?", (username.lower(),))
    user = c.fetchone()
    conn.close()
    return user if user else None

def init_db():
    conn = sqlite3.connect('medical_portal.db')
    c = conn.cursor()
    # Table for users
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT)''')
    # Add email column if missing in an older database schema
    c.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in c.fetchall()]
    if 'email' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN email TEXT")
    # Table for history
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (username TEXT, question TEXT, response TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    # Table for password reset
    c.execute('''CREATE TABLE IF NOT EXISTS password_reset 
                 (email TEXT, reset_code TEXT, expires DATETIME)''')
    conn.commit()
    conn.close()

def add_user(username, password, email):
    try:
        username = username.strip()
        email = email.strip().lower() if email else None
        conn = sqlite3.connect('medical_portal.db')
        c = conn.cursor()
        hashed_pw = hash_password(password)
        c.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)", (username, hashed_pw, email))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Username already exists
    except Exception as e:
        print(f"Error adding user: {e}")
        return False
    finally:
        conn.close()

def authenticate_user(identifier, password):
    if not identifier or not password:
        return None
    identifier = identifier.strip()
    hashed_pw = hash_password(password)
    conn = sqlite3.connect('medical_portal.db')
    c = conn.cursor()
    if "@" in identifier:
        c.execute("SELECT username, password FROM users WHERE LOWER(email)=?", (identifier.lower(),))
    else:
        c.execute("SELECT username, password FROM users WHERE LOWER(username)=?", (identifier.lower(),))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    username, stored_password = row
    if stored_password == hashed_pw or stored_password == password:
        return username
    return None

def verify_user(username, password):
    return authenticate_user(username, password) is not None

def save_history(username, question, response):
    conn = sqlite3.connect('medical_portal.db')
    c = conn.cursor()
    c.execute("INSERT INTO history (username, question, response) VALUES (?, ?, ?)", 
              (username, question, response))
    conn.commit()
    conn.close()

def get_history(username):
    conn = sqlite3.connect('medical_portal.db')
    c = conn.cursor()
    c.execute("SELECT question, response, timestamp FROM history WHERE username=? ORDER BY timestamp DESC", (username,))
    data = c.fetchall()
    conn.close()
    return data