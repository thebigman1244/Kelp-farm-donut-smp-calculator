from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-later")

DB_PATH = "database.db"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message_category = "error"


# -----------------------------
# Database helpers
# -----------------------------
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            kelp_plants REAL NOT NULL,
            smokers REAL NOT NULL,
            hours REAL NOT NULL,
            sell_price_per_block REAL NOT NULL,
            blaze_rod_cost REAL NOT NULL,
            seconds_per_smoker_item REAL NOT NULL,
            items_per_blaze_rod REAL NOT NULL,
            seconds_per_growth_tick REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )

    conn.commit()
    conn.close()


init_db()


# -----------------------------
# User model
# -----------------------------
class User(UserMixin):
    def __init__(self, user_id, username):
        self.id = str(user_id)
        self.username = username


@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user = conn.execute(
        "SELECT id, username FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()

    if user:
        return User(user["id"], user["username"])
    return None


# -----------------------------
# Defaults + formatting
# -----------------------------
DEFAULTS = {
    "kelp_plants": 45,
    "smokers": 2,
    "hours": 24,
    "sell_price_per_block": 750.0,
    "blaze_rod_cost": 150.0,
    "seconds_per_smoker_item": 5.0,
    "items_per_blaze_rod": 12.0,
    "seconds_per_growth_tick": 4.0,
}


def fmt_money(value: float) -> str:
    return "${:,.2f}".format(value)


def fmt_num(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}"
    return f"{value:,.2f}"


# -----------------------------
# Calculator logic
# -----------------------------
def calc(data: dict) -> dict:
    kelp_plants = float(data["kelp_plants"])
    smokers = float(data["smokers"])
    hours = float(data["hours"])
    sell_price_per_block = float(data["sell_price_per_block"])
    blaze_rod_cost = float(data["blaze_rod_cost"])
    seconds_per_smoker_item = float(data["seconds_per_smoker_item"])
    items_per_blaze_rod = float(data["items_per_blaze_rod"])
    seconds_per_growth_tick = float(data["seconds_per_growth_tick"])

    total_seconds = hours * 3600.0

    # Farm-side production estimate
    farm_raw_kelp = (total_seconds / seconds_per_growth_tick) * kelp_plants

    # Smoker-side max capacity
    smoker_capacity_raw_kelp = (total_seconds / seconds_per_smoker_item) * smokers

    # Real processed total
    processed_raw_kelp = min(farm_raw_kelp, smoker_capacity_raw_kelp)
    unused_farm_output = max(farm_raw_kelp - smoker_capacity_raw_kelp, 0.0)

    dried_kelp_blocks = processed_raw_kelp / 9.0
    dried_kelp_block_stacks = dried_kelp_blocks / 64.0

    blaze_rods_total = processed_raw_kelp / items_per_blaze_rod
    blaze_rod_stacks_total = blaze_rods_total / 64.0
    blaze_rods_per_smoker = blaze_rods_total / smokers if smokers > 0 else 0.0
    blaze_rod_stacks_per_smoker = blaze_rods_per_smoker / 64.0

    gross_revenue = dried_kelp_blocks * sell_price_per_block
    blaze_rod_total_cost = blaze_rods_total * blaze_rod_cost
    net_profit = gross_revenue - blaze_rod_total_cost

    bottleneck = "farm growth" if farm_raw_kelp < smoker_capacity_raw_kelp else "smokers"
    smoker_utilization = (
        (processed_raw_kelp / smoker_capacity_raw_kelp) * 100.0
        if smoker_capacity_raw_kelp > 0
        else 0.0
    )
    farm_utilization = (
        (processed_raw_kelp / farm_raw_kelp) * 100.0
        if farm_raw_kelp > 0
        else 0.0
    )

    return {
        "farm_raw_kelp": farm_raw_kelp,
        "smoker_capacity_raw_kelp": smoker_capacity_raw_kelp,
        "processed_raw_kelp": processed_raw_kelp,
        "unused_farm_output": unused_farm_output,
        "dried_kelp_blocks": dried_kelp_blocks,
        "dried_kelp_block_stacks": dried_kelp_block_stacks,
        "blaze_rods_total": blaze_rods_total,
        "blaze_rod_stacks_total": blaze_rod_stacks_total,
        "blaze_rods_per_smoker": blaze_rods_per_smoker,
        "blaze_rod_stacks_per_smoker": blaze_rod_stacks_per_smoker,
        "gross_revenue": gross_revenue,
        "blaze_rod_total_cost": blaze_rod_total_cost,
        "net_profit": net_profit,
        "bottleneck": bottleneck,
        "smoker_utilization": smoker_utilization,
        "farm_utilization": farm_utilization,
    }


# -----------------------------
# Routes
# -----------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    form = DEFAULTS.copy()
    results = None
    error = None

    if request.method == "POST":
        action = request.form.get("action", "calculate")

        try:
            form = {
                "kelp_plants": float(request.form.get("kelp_plants", DEFAULTS["kelp_plants"])),
                "smokers": float(request.form.get("smokers", DEFAULTS["smokers"])),
                "hours": float(request.form.get("hours", DEFAULTS["hours"])),
                "sell_price_per_block": float(
                    request.form.get("sell_price_per_block", DEFAULTS["sell_price_per_block"])
                ),
                "blaze_rod_cost": float(
                    request.form.get("blaze_rod_cost", DEFAULTS["blaze_rod_cost"])
                ),
                "seconds_per_smoker_item": float(
                    request.form.get(
                        "seconds_per_smoker_item", DEFAULTS["seconds_per_smoker_item"]
                    )
                ),
                "items_per_blaze_rod": float(
                    request.form.get("items_per_blaze_rod", DEFAULTS["items_per_blaze_rod"])
                ),
                "seconds_per_growth_tick": float(
                    request.form.get(
                        "seconds_per_growth_tick", DEFAULTS["seconds_per_growth_tick"]
                    )
                ),
            }

            if form["kelp_plants"] <= 0:
                raise ValueError("Kelp plants must be greater than 0.")
            if form["smokers"] <= 0:
                raise ValueError("Smokers must be greater than 0.")
            if form["hours"] <= 0:
                raise ValueError("Run time must be greater than 0.")
            if form["sell_price_per_block"] < 0 or form["blaze_rod_cost"] < 0:
                raise ValueError("Prices cannot be negative.")
            if (
                form["seconds_per_smoker_item"] <= 0
                or form["items_per_blaze_rod"] <= 0
                or form["seconds_per_growth_tick"] <= 0
            ):
                raise ValueError("Timing and fuel values must be greater than 0.")

            results = calc(form)

            if action == "save_project":
                if not current_user.is_authenticated:
                    flash("Log in first to save projects.", "error")
                else:
                    project_name = request.form.get("project_name", "").strip()
                    if not project_name:
                        raise ValueError("Project name is required to save.")
                    conn = get_db_connection()
                    conn.execute(
                        """
                        INSERT INTO projects (
                            user_id, name, kelp_plants, smokers, hours,
                            sell_price_per_block, blaze_rod_cost,
                            seconds_per_smoker_item, items_per_blaze_rod,
                            seconds_per_growth_tick
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            current_user.id,
                            project_name,
                            form["kelp_plants"],
                            form["smokers"],
                            form["hours"],
                            form["sell_price_per_block"],
                            form["blaze_rod_cost"],
                            form["seconds_per_smoker_item"],
                            form["items_per_blaze_rod"],
                            form["seconds_per_growth_tick"],
                        ),
                    )
                    conn.commit()
                    conn.close()
                    flash(f'Project "{project_name}" saved.', "success")

        except Exception as exc:
            error = str(exc)

    return render_template(
        "index.html",
        form=form,
        results=results,
        error=error,
        fmt_money=fmt_money,
        fmt_num=fmt_num,
    )


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        try:
            if len(username) < 3:
                raise ValueError("Username must be at least 3 characters.")
            if len(password) < 6:
                raise ValueError("Password must be at least 6 characters.")

            password_hash = generate_password_hash(password)

            conn = get_db_connection()
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            conn.commit()

            user = conn.execute(
                "SELECT id, username FROM users WHERE username = ?",
                (username,),
            ).fetchone()
            conn.close()

            login_user(User(user["id"], user["username"]))
            flash("Account created successfully.", "success")
            return redirect(url_for("dashboard"))

        except sqlite3.IntegrityError:
            error = "That username is already taken."
        except Exception as exc:
            error = str(exc)

    return render_template("signup.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_db_connection()
        user = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            login_user(User(user["id"], user["username"]))
            flash("Logged in.", "success")
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid username or password."

    return render_template("login.html", error=error)


@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db_connection()
    projects = conn.execute(
        """
        SELECT id, name, kelp_plants, smokers, hours,
               sell_price_per_block, blaze_rod_cost,
               seconds_per_smoker_item, items_per_blaze_rod,
               seconds_per_growth_tick, created_at
        FROM projects
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (current_user.id,),
    ).fetchall()
    conn.close()

    return render_template("dashboard.html", projects=projects)


@app.route("/load-project/<int:project_id>")
@login_required
def load_project(project_id):
    conn = get_db_connection()
    project = conn.execute(
        """
        SELECT *
        FROM projects
        WHERE id = ? AND user_id = ?
        """,
        (project_id, current_user.id),
    ).fetchone()
    conn.close()

    if not project:
        flash("Project not found.", "error")
        return redirect(url_for("dashboard"))

    form = {
        "kelp_plants": project["kelp_plants"],
        "smokers": project["smokers"],
        "hours": project["hours"],
        "sell_price_per_block": project["sell_price_per_block"],
        "blaze_rod_cost": project["blaze_rod_cost"],
        "seconds_per_smoker_item": project["seconds_per_smoker_item"],
        "items_per_blaze_rod": project["items_per_blaze_rod"],
        "seconds_per_growth_tick": project["seconds_per_growth_tick"],
    }
    results = calc(form)

    return render_template(
        "index.html",
        form=form,
        results=results,
        error=None,
        fmt_money=fmt_money,
        fmt_num=fmt_num,
    )


@app.route("/delete-project/<int:project_id>", methods=["POST"])
@login_required
def delete_project(project_id):
    conn = get_db_connection()
    conn.execute(
        "DELETE FROM projects WHERE id = ? AND user_id = ?",
        (project_id, current_user.id),
    )
    conn.commit()
    conn.close()

    flash("Project deleted.", "success")
    return redirect(url_for("dashboard"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
