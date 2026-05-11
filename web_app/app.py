"""
Веб-приложение БД school_1416_db.

Поддерживает четыре типа пользователей:
  • admin_db, operator_user, auditor_user — технические роли PostgreSQL,
    логин = имя роли, пароль = пароль роли.
  • Учитель — авторизуется по email + пароль (хэш bcrypt в teacher_accounts).
    Веб-приложение подключается к СУБД под служебной ролью teacher_user
    и устанавливает app.current_teacher_id для RLS-политик.

Запуск:  cd web_app && python app.py
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

# Чтобы импортировать etl-модули из соседней папки
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "etl"))
sys.path.insert(0, str(ROOT / "monitoring"))

import psycopg2
import psycopg2.extras
from flask import (
    Flask, flash, g, redirect, render_template, request, send_file, session,
    url_for,
)
from werkzeug.utils import secure_filename

from config import Config
from import_data import import_file, TABLE_SPECS  # noqa: E402
from monitoring import collect_metrics, write_to_log  # noqa: E402

import exporter

app = Flask(__name__)
app.config.from_object(Config)
os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)


# ============================================================================
# Подключение к БД
# ============================================================================

def get_db():
    """Возвращает psycopg2-соединение от имени роли текущего пользователя.

    Для технических ролей подключаемся напрямую под их учёткой.
    Для учителей подключаемся под teacher_user и устанавливаем
    app.current_teacher_id, чтобы RLS-политики видели «свои» строки.
    """
    if "db_conn" in g:
        return g.db_conn

    user_kind = session.get("user_kind")
    if not user_kind:
        return None

    if user_kind == "role":
        # admin_db / operator_user / auditor_user
        g.db_conn = psycopg2.connect(
            host=app.config["DB_HOST"],
            port=app.config["DB_PORT"],
            dbname=app.config["DB_NAME"],
            user=session["username"],
            password=session["password"],
        )
    elif user_kind == "teacher":
        g.db_conn = psycopg2.connect(
            host=app.config["DB_HOST"],
            port=app.config["DB_PORT"],
            dbname=app.config["DB_NAME"],
            user=app.config["TEACHER_DB_ROLE"],
            password=app.config["TEACHER_DB_PASSWORD"],
        )
        # Сообщаем СУБД, какой именно учитель работает в этом сеансе.
        # Это значение читается RLS-политиками через current_setting().
        with g.db_conn.cursor() as cur:
            cur.execute("SELECT set_config('app.current_teacher_id', %s, false)",
                        (str(session["teacher_id"]),))
        g.db_conn.commit()
    return g.db_conn


@app.teardown_appcontext
def close_db(exc):
    conn = g.pop("db_conn", None)
    if conn is not None:
        conn.close()


def query(sql: str, params: tuple = ()) -> list[dict]:
    conn = get_db()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def execute_write(sql: str, params: tuple = ()) -> None:
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    except psycopg2.Error:
        conn.rollback()
        raise


def friendly_db_error(exc: psycopg2.Error) -> str:
    """Переводит технические ошибки PostgreSQL в человекочитаемый текст."""
    constraint = getattr(exc.diag, "constraint_name", "") or ""
    messages = {
        "schedule_class_id_lesson_date_lesson_number_key":
            "У этого класса уже есть урок в выбранную дату и номер урока.",
        "schedule_classroom_id_lesson_date_lesson_number_key":
            "Кабинет уже занят в выбранную дату и номер урока.",
        "schedule_teacher_id_lesson_date_lesson_number_key":
            "Преподаватель уже занят в выбранную дату и номер урока.",
    }
    if constraint in messages:
        return messages[constraint]
    primary = getattr(exc.diag, "message_primary", "") or ""
    if primary:
        return primary
    return str(exc).splitlines()[0]


# ============================================================================
# Декораторы
# ============================================================================

def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_kind" not in session:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


def role_required(*roles):
    """Доступ только для указанных технических ролей."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if session.get("user_kind") != "role" or \
               session.get("username") not in roles:
                flash("Недостаточно прав для просмотра раздела.", "warning")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapper
    return decorator


def teacher_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if session.get("user_kind") != "teacher":
            flash("Раздел доступен только учителям.", "warning")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapper


# ============================================================================
# Шаблонные данные
# ============================================================================

@app.context_processor
def inject_user():
    role_labels = {
        "admin_db":      "Администратор БД",
        "operator_user": "Оператор",
        "auditor_user":  "Аудитор",
    }
    user_kind = session.get("user_kind")
    if user_kind == "role":
        username = session.get("username")
        return {
            "current_user_kind": "role",
            "current_user":      username,
            "current_role":      role_labels.get(username),
            "is_admin":     username == "admin_db",
            "is_operator":  username == "operator_user",
            "is_auditor":   username == "auditor_user",
            "is_teacher":   False,
            "now": datetime.now,
        }
    if user_kind == "teacher":
        return {
            "current_user_kind": "teacher",
            "current_user":      session.get("teacher_email"),
            "current_role":      "Учитель",
            "teacher_full_name": session.get("teacher_full_name"),
            "is_admin": False, "is_operator": False,
            "is_auditor": False, "is_teacher": True,
            "now": datetime.now,
        }
    return {
        "current_user_kind": None,
        "current_user": None, "current_role": None,
        "is_admin": False, "is_operator": False,
        "is_auditor": False, "is_teacher": False,
        "now": datetime.now,
    }


# ============================================================================
# Авторизация
# ============================================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        kind = request.form.get("kind", "role")

        if kind == "role":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            if username not in app.config["ALLOWED_ROLES"]:
                flash("Неизвестная роль.", "danger")
                return render_template("login.html")
            try:
                test = psycopg2.connect(
                    host=app.config["DB_HOST"], port=app.config["DB_PORT"],
                    dbname=app.config["DB_NAME"],
                    user=username, password=password, connect_timeout=5,
                )
                test.close()
            except psycopg2.OperationalError as exc:
                flash(f"Ошибка авторизации: {exc}", "danger")
                return render_template("login.html")
            session.clear()
            session["user_kind"] = "role"
            session["username"]  = username
            session["password"]  = password
            flash(f"Добро пожаловать, {username}", "success")
            return redirect(request.args.get("next") or url_for("dashboard"))

        # kind == "teacher": email + пароль, проверяем через crypt()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # Подключаемся под admin_db чтобы прочитать teacher_accounts
        # (учителю нельзя читать чужие учётки).
        try:
            admin_conn = psycopg2.connect(
                host=app.config["DB_HOST"], port=app.config["DB_PORT"],
                dbname=app.config["DB_NAME"],
                user="admin_db", password="Admin123!", connect_timeout=5,
            )
        except psycopg2.OperationalError as exc:
            flash(f"Ошибка подключения к БД: {exc}", "danger")
            return render_template("login.html")
        try:
            with admin_conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            ) as cur:
                cur.execute("""
                    SELECT ta.teacher_id, ta.email, ta.is_active,
                           (ta.password_hash = crypt(%s, ta.password_hash))
                              AS password_ok,
                           t.last_name, t.first_name, t.middle_name,
                           t.position_title
                    FROM teacher_accounts ta
                    JOIN teachers t ON t.teacher_id = ta.teacher_id
                    WHERE ta.email = %s
                """, (password, email))
                acc = cur.fetchone()

            if not acc or not acc["password_ok"] or not acc["is_active"]:
                flash("Неверный email или пароль.", "danger")
                return render_template("login.html")

            with admin_conn.cursor() as cur:
                cur.execute("UPDATE teacher_accounts "
                            "SET last_login_at = CURRENT_TIMESTAMP "
                            "WHERE teacher_id = %s", (acc["teacher_id"],))
                admin_conn.commit()
        finally:
            admin_conn.close()

        full_name = " ".join(filter(None, [
            acc["last_name"], acc["first_name"], acc["middle_name"]
        ]))
        session.clear()
        session["user_kind"]         = "teacher"
        session["teacher_id"]        = acc["teacher_id"]
        session["teacher_email"]     = acc["email"]
        session["teacher_full_name"] = full_name
        session["teacher_position"]  = acc["position_title"]
        flash(f"Добро пожаловать, {full_name}", "success")
        return redirect(url_for("teacher_profile"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из системы.", "info")
    return redirect(url_for("login"))


# ============================================================================
# Дашборд (для технических ролей)
# ============================================================================

@app.route("/")
@login_required
def dashboard():
    if session.get("user_kind") == "teacher":
        return redirect(url_for("teacher_profile"))

    stats = {
        "students_total": query("SELECT COUNT(*) AS c FROM students")[0]["c"],
        "teachers_total": query("SELECT COUNT(*) AS c FROM teachers")[0]["c"],
        "classes_total":  query("SELECT COUNT(*) AS c FROM classes")[0]["c"],
        "grades_total":   query("SELECT COUNT(*) AS c FROM grades")[0]["c"],
    }

    metrics = None
    try:
        cur_conn = get_db()
        with cur_conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:
            cur.execute("""
                SELECT pg_database_size(current_database()) AS db_size,
                       (SELECT COUNT(*) FROM pg_stat_activity
                         WHERE state = 'active') AS active_conn
            """)
            metrics = cur.fetchone()
    except psycopg2.Error:
        get_db().rollback()

    recent_events = []
    try:
        recent_events = query(
            "SELECT * FROM v_recent_monitoring LIMIT 10"
        )
    except psycopg2.Error:
        get_db().rollback()

    return render_template(
        "dashboard.html",
        stats=stats, metrics=metrics, recent_events=recent_events,
    )


# ============================================================================
# Просмотр данных (общие страницы)
# ============================================================================

@app.route("/students")
@login_required
def students():
    if session.get("user_kind") == "teacher":
        return redirect(url_for("teacher_profile"))

    search = request.args.get("q", "").strip()
    class_filter = request.args.get("class_id", "").strip()

    sql = """
        SELECT s.student_id, s.last_name, s.first_name, s.middle_name,
               s.birth_date, s.admission_year, s.student_status,
               c.class_name
          FROM students s
          JOIN classes c ON c.class_id = s.class_id
         WHERE 1=1
    """
    params: list = []
    if search:
        sql += " AND (s.last_name ILIKE %s OR s.first_name ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])
    if class_filter:
        sql += " AND s.class_id = %s"
        params.append(int(class_filter))
    sql += " ORDER BY s.last_name, s.first_name"

    rows = query(sql, tuple(params))
    classes = query("SELECT class_id, class_name FROM classes "
                    "ORDER BY class_name")
    return render_template(
        "students.html",
        rows=rows, classes=classes,
        search=search, class_filter=class_filter,
        statuses=("active", "graduated", "expelled"),
    )


@app.route("/students/<int:student_id>/status", methods=["POST"])
@role_required("admin_db")
def update_student_status(student_id: int):
    new_status = request.form.get("student_status", "").strip()
    if new_status not in {"active", "graduated", "expelled"}:
        flash("Некорректный статус ученика.", "danger")
        return redirect(url_for("students"))
    try:
        execute_write(
            "UPDATE students SET student_status = %s WHERE student_id = %s",
            (new_status, student_id),
        )
        flash("Статус ученика обновлён.", "success")
    except psycopg2.Error as exc:
        flash(f"Ошибка обновления статуса: {friendly_db_error(exc)}",
              "danger")
    return redirect(url_for("students"))


# ============================================================================
# Оценки и расписание (общие страницы — для admin/operator/auditor)
# ============================================================================

def _grade_form_options() -> dict:
    return {
        "students": query("""
            SELECT s.student_id,
                   s.last_name || ' ' || s.first_name || ' (' ||
                   c.class_name || ', ' || s.student_status || ')' AS fio
              FROM students s JOIN classes c ON c.class_id = s.class_id
             ORDER BY s.last_name, s.first_name
        """),
        "subjects": query("SELECT subject_id, subject_name FROM subjects "
                          "ORDER BY subject_name"),
        "teachers": query("""
            SELECT teacher_id,
                   last_name || ' ' || first_name || ' ' ||
                   COALESCE(middle_name, '') AS teacher_name
              FROM teachers ORDER BY last_name, first_name
        """),
    }


def _schedule_form_options() -> dict:
    return {
        "classes": query("SELECT class_id, class_name FROM classes "
                         "ORDER BY class_name"),
        "subjects": query("SELECT subject_id, subject_name FROM subjects "
                          "ORDER BY subject_name"),
        "teachers": query("""
            SELECT teacher_id,
                   last_name || ' ' || first_name || ' ' ||
                   COALESCE(middle_name, '') AS teacher_name
              FROM teachers ORDER BY last_name, first_name
        """),
        "classrooms": query("""
            SELECT classroom_id,
                   room_number || ', ' || building AS classroom_name
              FROM classrooms ORDER BY building, room_number
        """),
    }


@app.route("/grades", methods=["GET", "POST"])
@login_required
def grades():
    if session.get("user_kind") == "teacher":
        return redirect(url_for("teacher_profile"))

    if request.method == "POST":
        if session["username"] not in {"admin_db", "operator_user"}:
            flash("Недостаточно прав.", "warning")
            return redirect(url_for("grades"))
        try:
            execute_write(
                """INSERT INTO grades
                   (student_id, subject_id, teacher_id, grade_value,
                    grade_date, grade_comment)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (int(request.form["student_id"]),
                 int(request.form["subject_id"]),
                 int(request.form["teacher_id"]),
                 int(request.form["grade_value"]),
                 request.form["grade_date"],
                 request.form.get("grade_comment") or None),
            )
            flash("Оценка выставлена.", "success")
        except (ValueError, psycopg2.Error) as exc:
            msg = friendly_db_error(exc) if isinstance(exc, psycopg2.Error) \
                  else "Проверьте заполнение формы."
            flash(f"Ошибка: {msg}", "danger")
        return redirect(url_for("grades"))

    student_filter = request.args.get("student_id", "").strip()
    sql = "SELECT * FROM v_student_grades WHERE 1=1"
    params: list = []
    if student_filter:
        sql += " AND student_id = %s"
        params.append(int(student_filter))
    sql += " ORDER BY grade_date DESC, grade_id DESC LIMIT 200"

    rows = query(sql, tuple(params))
    students_list = query(
        "SELECT student_id, last_name || ' ' || first_name AS fio "
        "FROM students ORDER BY last_name, first_name"
    )
    return render_template(
        "grades.html", rows=rows, students=students_list,
        student_filter=student_filter,
        form_options=_grade_form_options(),
    )


@app.route("/schedule", methods=["GET", "POST"])
@login_required
def schedule():
    if session.get("user_kind") == "teacher":
        return redirect(url_for("teacher_profile"))

    if request.method == "POST":
        if session["username"] not in {"admin_db", "operator_user"}:
            flash("Недостаточно прав.", "warning")
            return redirect(url_for("schedule"))
        try:
            execute_write(
                """INSERT INTO schedule
                   (class_id, subject_id, teacher_id, classroom_id,
                    lesson_date, lesson_number)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (int(request.form["class_id"]),
                 int(request.form["subject_id"]),
                 int(request.form["teacher_id"]),
                 int(request.form["classroom_id"]),
                 request.form["lesson_date"],
                 int(request.form["lesson_number"])),
            )
            flash("Урок добавлен в расписание.", "success")
        except (ValueError, psycopg2.Error) as exc:
            msg = friendly_db_error(exc) if isinstance(exc, psycopg2.Error) \
                  else "Проверьте заполнение формы."
            flash(f"Ошибка: {msg}", "danger")
        return redirect(url_for("schedule"))

    date_filter = request.args.get("date", "").strip()
    class_filter = request.args.get("class_id", "").strip()
    sql = "SELECT * FROM v_class_schedule WHERE 1=1"
    params: list = []
    if date_filter:
        sql += " AND lesson_date = %s"; params.append(date_filter)
    if class_filter:
        sql += " AND class_id = %s"; params.append(int(class_filter))
    sql += " ORDER BY lesson_date, lesson_number, class_name LIMIT 200"

    rows = query(sql, tuple(params))
    options = _schedule_form_options()
    return render_template(
        "schedule.html",
        rows=rows, classes=options["classes"], form_options=options,
        date_filter=date_filter, class_filter=class_filter,
    )


# ============================================================================
# Импорт и журналы
# ============================================================================

@app.route("/import", methods=["GET", "POST"])
@role_required("admin_db", "operator_user")
def import_view():
    result = None
    if request.method == "POST":
        file = request.files.get("file")
        table = request.form.get("table", "").strip()
        if not file or not file.filename:
            flash("Файл не выбран.", "danger")
            return redirect(url_for("import_view"))
        if table not in TABLE_SPECS:
            flash(f"Неподдерживаемая таблица: {table}", "danger")
            return redirect(url_for("import_view"))
        ext = Path(file.filename).suffix.lower()
        if ext not in app.config["ALLOWED_EXTENSIONS"]:
            flash(f"Неподдерживаемое расширение: {ext}", "danger")
            return redirect(url_for("import_view"))
        save_path = Path(app.config["UPLOAD_DIR"]) / secure_filename(file.filename)
        file.save(save_path)
        result = import_file(save_path, table)
        if result["status"] == "completed":
            flash(f"Импорт завершён: загружено {result['rows_loaded']} строк "
                  f"(import_id={result['import_id']})", "success")
        else:
            flash(f"Импорт завершился с ошибкой: {result.get('error')}",
                  "danger")
    return render_template("import.html",
                           tables=list(TABLE_SPECS), result=result)


@app.route("/import-log")
@login_required
def import_log():
    if session.get("user_kind") == "teacher":
        return redirect(url_for("teacher_profile"))
    rows = query("SELECT * FROM import_log ORDER BY import_time DESC LIMIT 100")
    return render_template("import_log.html", rows=rows)


@app.route("/monitoring")
@role_required("admin_db", "auditor_user")
def monitoring_view():
    rows = query("SELECT * FROM monitoring_log ORDER BY event_time DESC LIMIT 100")
    return render_template("monitoring.html", rows=rows)


@app.route("/monitoring/snapshot", methods=["POST"])
@role_required("admin_db")
def monitoring_snapshot():
    try:
        metrics = collect_metrics()
        write_to_log(metrics)
        flash("Снимок метрик сохранён в журнал мониторинга.", "success")
    except Exception as exc:
        flash(f"Ошибка сбора метрик: {exc}", "danger")
    return redirect(url_for("monitoring_view"))


# ============================================================================
# Кабинет учителя
# ============================================================================

@app.route("/teacher")
@teacher_required
def teacher_profile():
    """Главная страница кабинета учителя."""
    today = date.today()
    two_weeks = today + timedelta(days=14)

    schedule_rows = query("""
        SELECT s.schedule_id, s.lesson_date, s.lesson_number,
               c.class_name, sub.subject_name,
               cr.room_number, cr.building
          FROM schedule s
          JOIN classes c ON c.class_id = s.class_id
          JOIN subjects sub ON sub.subject_id = s.subject_id
          JOIN classrooms cr ON cr.classroom_id = s.classroom_id
         WHERE s.lesson_date BETWEEN %s AND %s
         ORDER BY s.lesson_date, s.lesson_number
    """, (today, two_weeks))

    grade_rows = query("""
        SELECT g.grade_id, g.grade_date, g.grade_value, g.grade_comment,
               st.last_name || ' ' || st.first_name AS student_full_name,
               c.class_name, sub.subject_name
          FROM grades g
          JOIN students st ON st.student_id = g.student_id
          JOIN classes c   ON c.class_id    = st.class_id
          JOIN subjects sub ON sub.subject_id = g.subject_id
         ORDER BY g.grade_date DESC, g.grade_id DESC
         LIMIT 30
    """)

    # Класс+предмет, по которым этот учитель ведёт уроки
    teaching = query("""
        SELECT DISTINCT c.class_id, c.class_name,
               sub.subject_id, sub.subject_name
          FROM schedule s
          JOIN classes c    ON c.class_id    = s.class_id
          JOIN subjects sub ON sub.subject_id = s.subject_id
         ORDER BY c.class_name, sub.subject_name
    """)

    return render_template(
        "teacher_profile.html",
        schedule_rows=schedule_rows,
        grade_rows=grade_rows,
        teaching=teaching,
        date_from=today, date_to=two_weeks,
    )


# ============================================================================
# Выгрузки в XLSX
# ============================================================================

def _send_xlsx(buf, filename: str):
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


@app.route("/teacher/export/schedule")
@teacher_required
def export_my_schedule():
    """Учитель скачивает своё расписание за период."""
    try:
        d_from = datetime.strptime(
            request.args.get("from", ""), "%Y-%m-%d"
        ).date()
        d_to = datetime.strptime(
            request.args.get("to", ""), "%Y-%m-%d"
        ).date()
    except ValueError:
        d_from = date.today()
        d_to = d_from + timedelta(days=13)

    rows = query("""
        SELECT s.lesson_date, s.lesson_number,
               c.class_name, sub.subject_name,
               cr.room_number, cr.building
          FROM schedule s
          JOIN classes c    ON c.class_id    = s.class_id
          JOIN subjects sub ON sub.subject_id = s.subject_id
          JOIN classrooms cr ON cr.classroom_id = s.classroom_id
         WHERE s.lesson_date BETWEEN %s AND %s
         ORDER BY s.lesson_date, s.lesson_number
    """, (d_from, d_to))

    buf = exporter.export_teacher_schedule(
        teacher_full_name=session.get("teacher_full_name", ""),
        rows=rows, date_from=d_from, date_to=d_to,
    )
    fname = f"schedule_{session['teacher_id']}_{d_from}_{d_to}.xlsx"
    return _send_xlsx(buf, fname)


@app.route("/teacher/export/grades/<int:class_id>/<int:subject_id>")
@teacher_required
def export_my_grades(class_id: int, subject_id: int):
    """Учитель скачивает оценки своего класса по своему предмету."""
    # Проверяем, что учитель действительно ведёт этот предмет в этом классе.
    # RLS-политика на schedule сама ограничит выборку — если тут есть строки,
    # значит учитель к этому классу+предмету причастен.
    teaches = query("""
        SELECT 1 FROM schedule
         WHERE class_id = %s AND subject_id = %s LIMIT 1
    """, (class_id, subject_id))
    if not teaches:
        flash("Вы не ведёте этот предмет в этом классе.", "warning")
        return redirect(url_for("teacher_profile"))

    class_info = query(
        "SELECT class_name FROM classes WHERE class_id = %s",
        (class_id,))[0]
    subject_info = query(
        "SELECT subject_name FROM subjects WHERE subject_id = %s",
        (subject_id,))[0]

    # Список учеников класса
    students_list = query("""
        SELECT student_id,
               last_name || ' ' || first_name ||
               COALESCE(' ' || middle_name, '') AS full_name
          FROM students
         WHERE class_id = %s AND student_status = 'active'
         ORDER BY last_name, first_name
    """, (class_id,))

    # Все оценки по предмету для этого класса
    # (RLS гарантирует, что мы видим только оценки этого учителя)
    raw_grades = query("""
        SELECT g.student_id, g.grade_date, g.grade_value, g.grade_comment
          FROM grades g
          JOIN students s ON s.student_id = g.student_id
         WHERE s.class_id = %s AND g.subject_id = %s
         ORDER BY g.grade_date
    """, (class_id, subject_id))

    grade_dates = sorted({g["grade_date"] for g in raw_grades})
    grades_map = {(g["student_id"], g["grade_date"]):
                  {"value": g["grade_value"],
                   "comment": g["grade_comment"]}
                  for g in raw_grades}

    buf = exporter.export_class_grades(
        class_name=class_info["class_name"],
        subject_name=subject_info["subject_name"],
        teacher_full_name=session.get("teacher_full_name", ""),
        students=students_list,
        grade_dates=grade_dates,
        grades_map=grades_map,
    )
    fname = (f"grades_{class_info['class_name']}_"
             f"{subject_info['subject_name'][:15]}.xlsx")
    return _send_xlsx(buf, fname)


# Админские выгрузки
@app.route("/export/students")
@role_required("admin_db", "operator_user", "auditor_user")
def export_students():
    rows = query("""
        SELECT s.last_name, s.first_name, s.middle_name,
               s.birth_date, s.admission_year, s.student_status,
               c.class_name
          FROM students s JOIN classes c ON c.class_id = s.class_id
         ORDER BY c.class_name, s.last_name, s.first_name
    """)
    buf = exporter.export_students_list(rows)
    return _send_xlsx(buf, f"students_{date.today()}.xlsx")


@app.route("/export/import-log")
@login_required
def export_import_log():
    if session.get("user_kind") == "teacher":
        return redirect(url_for("teacher_profile"))
    rows = query("""
        SELECT import_id, source_name, import_time, rows_loaded, status
          FROM import_log ORDER BY import_time DESC
    """)
    data = [(r["import_id"], r["source_name"],
             r["import_time"].strftime("%Y-%m-%d %H:%M:%S"),
             r["rows_loaded"], r["status"]) for r in rows]
    buf = exporter.export_log(
        title="Журнал импорта",
        headers=["ID", "Источник", "Время", "Загружено", "Статус"],
        rows=data,
    )
    return _send_xlsx(buf, f"import_log_{date.today()}.xlsx")


@app.route("/export/monitoring-log")
@role_required("admin_db", "auditor_user")
def export_monitoring_log():
    rows = query("""
        SELECT log_id, event_time, event_type, description
          FROM monitoring_log ORDER BY event_time DESC
    """)
    data = [(r["log_id"],
             r["event_time"].strftime("%Y-%m-%d %H:%M:%S"),
             r["event_type"], r["description"]) for r in rows]
    buf = exporter.export_log(
        title="Журнал мониторинга",
        headers=["ID", "Время", "Тип события", "Описание"],
        rows=data,
    )
    return _send_xlsx(buf, f"monitoring_log_{date.today()}.xlsx")


# ============================================================================
# Точка входа
# ============================================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)
