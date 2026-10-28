import os, sqlite3, json, csv, io, secrets
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
    {"key":"age_group","label":"1. What is your age group?","type":"choice","options":["Under 18","18-20","21-23","24 or above"]},
    {"key":"study_level","label":"2. What is your current education level?","type":"choice","options":["Undergraduate","Postgraduate","Other"]},
    {"key":"daily_hours","label":"3. How many hours do you use your smartphone daily?","type":"choice","options":["0-2 hours","2-4 hours","4-6 hours","More than 6 hours"]},
    {"key":"main_use","label":"4. What is your main purpose for using a smartphone?","type":"choice","options":["Study or learning","Social media","Gaming","Entertainment","Communication","Other"]},
    {"key":"morning_check","label":"5. Do you check your phone immediately after waking up?","type":"choice","options":["Never","Rarely","Sometimes","Often","Always"]},
    {"key":"study_distraction","label":"6. Does smartphone use distract you while studying?","type":"choice","options":["Never","Rarely","Sometimes","Often","Always"]},
    {"key":"sleep_effect","label":"7. How often does smartphone use affect your sleep?","type":"choice","options":["Never","Rarely","Sometimes","Often","Always"]},
    {"key":"distracted","label":"8. Do you feel distracted because of your smartphone?","type":"choice","options":["Never","Rarely","Sometimes","Often","Always"]},
    {"key":"reduce_attempt","label":"9. Have you tried to reduce your smartphone usage?","type":"choice","options":["Yes","No"]},
    {"key":"academic_impact","label":"10. How much does smartphone use affect your academic performance?","type":"choice","options":["Not at all","A little","Moderately","A lot"]}
]

def db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS admins (
            username TEXT PRIMARY KEY, password_hash TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            age_confirmed INTEGER NOT NULL,
            study_level TEXT NOT NULL,
            answers TEXT NOT NULL,
            score INTEGER NOT NULL,
            indicator TEXT NOT NULL)""")
        existing = c.execute("SELECT username FROM admins WHERE username=?", (ADMIN_USER,)).fetchone()
        if not existing:
            c.execute("INSERT INTO admins(username,password_hash) VALUES(?,?)",
                      (ADMIN_USER, generate_password_hash(ADMIN_PASS)))

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_user"):
            flash("Please sign in to access the admin dashboard.", "warning")
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper

def calculate_score(answers):
    # Transparent exploratory indicator; not a validated clinical measure.
    scale_keys = ["bedtime","study_distraction","unplanned","reduce_difficult","sleep_effect",
                  "notifications","delayed_tasks","academic_impact","anxious","night_check","social_interrupt"]
    score = 0
    for key in scale_keys:
        try:
            score += max(0, min(4, int(answers.get(key, 0))))
        except (ValueError, TypeError):
            pass
    if score <= 14:
        return score, "Lower indicator"
    if score <= 29:
        return score, "Moderate indicator"
    return score, "Higher indicator"

@app.route("/")
def index():
    with db() as c:
        rows = c.execute("SELECT answers, score, indicator FROM responses").fetchall()
    total = len(rows)
    hours_map = {"0–2 hours":1, "2–4 hours":3, "4–6 hours":5, "6–8 hours":7, "More than 8 hours":9}
    hours = []
    higher = 0
    use_counts = {x:0 for x in ["0–2 hours","2–4 hours","4–6 hours","6–8 hours","More than 8 hours"]}
    indicator_counts = {"Lower indicator":0,"Moderate indicator":0,"Higher indicator":0}
    for r in rows:
        a = json.loads(r["answers"])
        h = a.get("daily_hours")
        if h in use_counts: use_counts[h] += 1
        if h in hours_map: hours.append(hours_map[h])
        indicator_counts[r["indicator"]] = indicator_counts.get(r["indicator"], 0) + 1
        if r["indicator"] == "Higher indicator": higher += 1
    avg = round(sum(hours)/len(hours),1) if hours else None
    return render_template("index.html", total=total, avg=avg, higher=higher,
                           use_counts=use_counts, indicator_counts=indicator_counts)

@app.route("/survey", methods=["GET","POST"])
def survey():
    if request.method == "POST":
        if request.form.get("consent") != "yes":
            flash("Please confirm that you are 18 or older and consent to participate.", "warning")
            return redirect(url_for("survey"))
        study_level = request.form.get("study_level","")
        if study_level not in ["Undergraduate","Postgraduate","Other"]:
            flash("Please select your study level.", "warning")
            return redirect(url_for("survey"))
        answers = {}
        for q in QUESTIONS:
          if q["type"] == "text":
            answers[q["key"]] = request.form.get(q["key"], "").strip()[:1000]
        else:
            val = request.form.get(q["key"], "")
            if val not in [str(i) for i in range(len(q["options"]))]:
                print("INVALID SURVEY ANSWER:", q["key"], repr(val))
                flash(
                    f"Please check your answer for: {q['label']}",
                    "warning"
                )
                return redirect(url_for("survey"))
            answers[q["key"]] = int(val)

    score, indicator = calculate_score(answers)
        with db() as c:
            c.execute("INSERT INTO responses(created_at,age_confirmed,study_level,answers,score,indicator) VALUES(?,?,?,?,?,?)",
                      (datetime.now(timezone.utc).isoformat(timespec="seconds"),1,study_level,json.dumps(answers),score,indicator))
        return render_template("thanks.html", score=score, indicator=indicator)
    return render_template("survey.html", questions=QUESTIONS)

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username","")
        password = request.form.get("password","")
        with db() as c:
            row = c.execute("SELECT * FROM admins WHERE username=?", (username,)).fetchone()
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
    with db() as c:
        rows = c.execute("SELECT * FROM responses ORDER BY id DESC").fetchall()
    records = []
    for row in rows:
        d = dict(row)
        d["answers"] = json.loads(d["answers"])
        records.append(d)
    total = len(records)
    avg = round(sum(r["score"] for r in records)/total,1) if total else 0
    indicators = {"Lower indicator":0,"Moderate indicator":0,"Higher indicator":0}
    for r in records: indicators[r["indicator"]] = indicators.get(r["indicator"],0)+1
    return render_template("admin.html", records=records, total=total, avg=avg, indicators=indicators, questions=QUESTIONS)

@app.route("/admin/export")
@admin_required
def export_csv():
    with db() as c:
        rows = c.execute("SELECT * FROM responses ORDER BY id").fetchall()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["response_id","created_at_utc","study_level","score","indicator"]+[q["key"] for q in QUESTIONS])
    for row in rows:
        a = json.loads(row["answers"])
        writer.writerow([row["id"],row["created_at"],row["study_level"],row["score"],row["indicator"]]+[a.get(q["key"],"") for q in QUESTIONS])
    return Response(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition":"attachment; filename=mindmeter_responses.csv"})

@app.route("/about")
def about():
    return render_template("about.html")

init_db()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)), debug=False)
