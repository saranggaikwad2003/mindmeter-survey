import os
import sqlite3
import json
import csv
import io
import secrets
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from werkzeug.security import generate_password_hash, check_password_hash

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT, "data", "responses.db")

app = Flask(__name__)
app.secret_key = os.environ.get("MINDMETER_SECRET_KEY", secrets.token_hex(32))

ADMIN_USER = os.environ.get("MINDMETER_ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("MINDMETER_ADMIN_PASSWORD", "ChangeMe123!")

QUESTIONS = [
    {"key": "age_group", "label": "1. What is your age group?", "type": "choice",
     "options": ["Under 18", "18-20", "21-23", "24 or above"]},
    {"key": "study_level", "label": "2. What is your current education level?", "type": "choice",
     "options": ["Undergraduate", "Postgraduate", "Other"]},
    {"key": "daily_hours", "label": "3. How many hours do you use your smartphone daily?", "type": "choice",
     "options": ["0-2 hours", "2-4 hours", "4-6 hours", "More than 6 hours"]},
    {"key": "main_use", "label": "4. What is your main purpose for using a smartphone?", "type": "choice",
     "options": ["Study or learning", "Social media", "Gaming", "Entertainment", "Communication", "Other"]},
    {"key": "morning_check", "label": "5. Do you check your phone immediately after waking up?", "type": "choice",
     "options": ["Never", "Rarely", "Sometimes", "Often", "Always"]},
    {"key": "study_distraction", "label": "6. Does smartphone use distract you while studying?", "type": "choice",
     "options": ["Never", "Rarely", "Sometimes", "Often", "Always"]},
    {"key": "sleep_effect", "label": "7. How often does smartphone use affect your sleep?", "type": "choice",
     "options": ["Never", "Rarely", "Sometimes", "Often", "Always"]},
    {"key": "distracted", "label": "8. Do you feel distracted because of your smartphone?", "type": "choice",
     "options": ["Never", "Rarely", "Sometimes", "Often", "Always"]},
    {"key": "reduce_attempt", "label": "9. Have you tried to reduce your smartphone usage?", "type": "choice",
     "options": ["Yes", "No"]},
    {"key": "academic_impact", "label": "10. How much does smartphone use affect your academic performance?", "type": "choice",
     "options": ["Not at all", "A little", "Moderately", "A lot"]},
]


def db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                age_confirmed INTEGER NOT NULL,
                study_level TEXT NOT NULL,
                answers TEXT NOT NULL,
                score INTEGER NOT NULL,
                indicator TEXT NOT NULL
            )
        """)
        existing = conn.execute(
            "SELECT username FROM admins WHERE username = ?", (ADMIN_USER,)
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO admins(username, password_hash) VALUES (?, ?)",
                (ADMIN_USER, generate_password_hash(ADMIN_PASS))
            )


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_user"):
            flash("Please sign in to access the admin dashboard.", "warning")
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper


def calculate_score(answers):
    # Exploratory indicator only; not a validated clinical test.
    score_keys = [
        "morning_check",
        "study_distraction",
        "sleep_effect",
        "distracted",
        "academic_impact"
    ]

    score = sum(int(answers.get(key, 0)) for key in score_keys)

    if score <= 6:
        return score, "Lower indicator"
    elif score <= 12:
        return score, "Moderate indicator"
    return score, "Higher indicator"


@app.route("/")
def index():
    with db() as conn:
        rows = conn.execute(
            "SELECT answers, score, indicator FROM responses"
        ).fetchall()

    total = len(rows)
    hour_options = ["0-2 hours", "2-4 hours", "4-6 hours", "More than 6 hours"]
    hour_values = {"0-2 hours": 1, "2-4 hours": 3, "4-6 hours": 5, "More than 6 hours": 7}

    use_counts = {option: 0 for option in hour_options}
    indicator_counts = {
        "Lower indicator": 0,
        "Moderate indicator": 0,
        "Higher indicator": 0
    }
    hours = []
    higher = 0

    for row in rows:
        try:
            answers = json.loads(row["answers"])
        except (json.JSONDecodeError, TypeError):
            answers = {}

        value = answers.get("daily_hours")
        if isinstance(value, int) and 0 <= value < len(hour_options):
            option = hour_options[value]
            use_counts[option] += 1
            hours.append(hour_values[option])

        indicator = row["indicator"]
        indicator_counts[indicator] = indicator_counts.get(indicator, 0) + 1
        if indicator == "Higher indicator":
            higher += 1

    avg = round(sum(hours) / len(hours), 1) if hours else None

    return render_template(
        "index.html",
        total=total,
        avg=avg,
        higher=higher,
        use_counts=use_counts,
        indicator_counts=indicator_counts
    )


@app.route("/survey", methods=["GET", "POST"])
def survey():
    if request.method == "GET":
        return render_template("survey.html", questions=QUESTIONS)

    if request.form.get("consent") != "yes":
        flash("Please confirm that you are 18 or older and consent to participate.", "warning")
        return redirect(url_for("survey"))

    answers = {}

    for question in QUESTIONS:
        key = question["key"]
        value = request.form.get(key, "")
        valid_values = [str(i) for i in range(len(question["options"]))]

        if value not in valid_values:
            flash(f"Please check your answer for: {question['label']}", "warning")
            return redirect(url_for("survey"))

        answers[key] = int(value)

    if answers["age_group"] == 0:
        flash("This survey is only for participants aged 18 or older.", "warning")
        return redirect(url_for("survey"))

    study_level = QUESTIONS[1]["options"][answers["study_level"]]
    score, indicator = calculate_score(answers)

    with db() as conn:
        conn.execute("""
            INSERT INTO responses
            (created_at, age_confirmed, study_level, answers, score, indicator)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            1,
            study_level,
            json.dumps(answers),
            score,
            indicator
        ))

    return render_template("thanks.html", score=score, indicator=indicator)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        with db() as conn:
            row = conn.execute(
                "SELECT * FROM admins WHERE username = ?", (username,)
            ).fetchone()

        if row and check_password_hash(row["password_hash"], password):
            session["admin_user"] = username
            return redirect(url_for("admin_dashboard"))

        flash("Incorrect username or password.", "danger")

    return render_template("login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM responses ORDER BY id DESC"
        ).fetchall()

    records = []
    for row in rows:
        record = dict(row)
        try:
            record["answers"] = json.loads(record["answers"])
        except (json.JSONDecodeError, TypeError):
            record["answers"] = {}
        records.append(record)

    total = len(records)
    avg = round(sum(r["score"] for r in records) / total, 1) if total else 0

    indicators = {
        "Lower indicator": 0,
        "Moderate indicator": 0,
        "Higher indicator": 0
    }
    for record in records:
        name = record["indicator"]
        indicators[name] = indicators.get(name, 0) + 1

    return render_template(
        "admin.html",
        records=records,
        total=total,
        avg=avg,
        indicators=indicators,
        questions=QUESTIONS
    )


@app.route("/admin/export")
@admin_required
def export_csv():
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM responses ORDER BY id"
        ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["response_id", "created_at_utc", "study_level", "score", "indicator"]
        + [q["key"] for q in QUESTIONS]
    )

    for row in rows:
        try:
            answers = json.loads(row["answers"])
        except (json.JSONDecodeError, TypeError):
            answers = {}

        writer.writerow(
            [row["id"], row["created_at"], row["study_level"],
             row["score"], row["indicator"]]
            + [answers.get(q["key"], "") for q in QUESTIONS]
        )

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=mindmeter_responses.csv"}
    )


@app.route("/about")
def about():
    return render_template("about.html")


init_db()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
