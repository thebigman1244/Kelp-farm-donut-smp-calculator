from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"  # change later

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

DB = "database.db"

# ---------------- DB SETUP ----------------
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        kelp_plants REAL,
        smokers REAL,
        hours REAL
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- USER ----------------
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    conn.close()

    if user:
        return User(user[0], user[1])
    return None

# ---------------- CALC ----------------
def calculate(data):
    kelp_plants = float(data["kelp_plants"])
    smokers = float(data["smokers"])
    hours = float(data["hours"])

    seconds = hours * 3600

    kelp_generated = (seconds / 4) * kelp_plants
    smoker_capacity = (seconds / 5) * smokers

    processed = min(kelp_generated, smoker_capacity)

    blocks = processed / 9
    stacks = blocks / 64

    rods = processed / 12
    rod_stacks = rods / 64

    revenue = blocks * 750
    cost = rods * 150
    profit = revenue - cost

    return {
        "profit": round(profit, 2),
        "revenue": round(revenue, 2),
        "cost": round(cost, 2),
        "stacks": round(stacks, 2),
        "rod_stacks": round(rod_stacks, 2),
        "bottleneck": "Farm" if kelp_generated < smoker_capacity else "Smokers"
    }

# ---------------- ROUTES ----------------

@app.route("/", methods=["GET", "POST"])
def index():
    results = None
    if request.method == "POST":
        results = calculate(request.form)
    return render_template("index.html", results=results)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        conn = sqlite3.connect(DB)
        c = conn.cursor()

        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            flash("Account created!")
            return redirect(url_for("login"))
        except:
            flash("Username taken")

        conn.close()

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            login_user(User(user[0], user[1]))
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid login")

    return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM projects WHERE user_id=?", (current_user.id,))
    projects = c.fetchall()
    conn.close()

    return render_template("dashboard.html", projects=projects)

@app.route("/save", methods=["POST"])
@login_required
def save():
    name = request.form["name"]
    kelp = request.form["kelp_plants"]
    smokers = request.form["smokers"]
    hours = request.form["hours"]

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO projects (user_id, name, kelp_plants, smokers, hours) VALUES (?, ?, ?, ?, ?)",
              (current_user.id, name, kelp, smokers, hours))
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))

@app.route("/delete/<id>")
@login_required
def delete(id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DELETE FROM projects WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
