"""
Веб-приложение администратора БД school_1416_db.

Архитектура:
  • Flask + Jinja2 + Bootstrap 5
  • Авторизация через PostgreSQL-роли: введённые логин/пароль используются
    для прямого подключения к СУБД. Если PostgreSQL принял соединение —
    значит роль валидна. Все запросы выполняются от имени этой роли,
    и СУБД сама обеспечивает разграничение прав (см. 02_roles.sql).
  • Меню адаптируется под роль: admin_db видит всё, operator_user не
    видит мониторинг, auditor_user не видит импорт.

Запуск:
    cd web_app && python app.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from functools import wraps
from pathlib import Path

# Чтобы импортировать etl-модули из соседней папки
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "etl"))
sys.path.insert(0, str(ROOT / "monitoring"))

import psycopg2
import psycopg2.extras
from flask import (
    Flask, flash, g, redirect, render_template, request, session,
    url_for,
)
from werkzeug.utils import secure_filename

from config import Config

# Импорт ETL и мониторинга из соседних пакетов
from import_data import import_file, TABLE_SPECS  # noqa: E402
from monitoring import collect_metrics            # noqa: E402

app = Flask(__name__)
app.config.from_object(Config)

os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)


# --- Подключение к БД от имени текущего пользователя ------------------------

def get_db():
    """Возвращает psycopg2-соединение от имени роли текущего пользователя.

    Соединение живёт в пределах одного запроса (g) и закрывается
    автоматически.
    """
    if "db_conn" not in g:
        if "username" not in session:
            return None
        g.db_conn = psycopg2.connect(
            host=app.config["DB_HOST"],
            port=app.config["DB_PORT"],
            dbname=app.config["DB_NAME"],
            user=session["username"],
            password=session["password"],
        )
    return g.db_conn


@app.teardown_appcontext
def close_db(exc):
    conn = g.pop("db_conn", None)
    if conn is not None:
        conn.close()


def query(sql: str, params: tuple = ()) -> list[dict]:
    """Выполняет SELECT и возвращает результат в виде list[dict]."""
    conn = get_db()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def execute_write(sql: str, params: tuple = ()) -> None:
    """Выполняет INSERT/UPDATE и фиксирует транзакцию."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    except psycopg2.Error:
        conn.rollback()
        raise


def friendly_db_error(exc: psycopg2.Error) -> str:
    """Возвращает понятное пользователю описание ошибки СУБД."""
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


def schedule_form_options() -> dict:
    """Справочники для формы расписания."""
    return {
        "classes": query(
            "SELECT class_id, class_name FROM classes ORDER BY class_name"
        ),
        "subjects": query(
            "SELECT subject_id, subject_name FROM subjects ORDER BY subject_name"
        ),
        "teachers": query("""
            SELECT teacher_id,
                   last_name || ' ' || first_name || ' ' ||
                   COALESCE(middle_name, '') AS teacher_name
            FROM teachers
            ORDER BY last_name, first_name
        """),
        "classrooms": query("""
            SELECT classroom_id,
                   room_number || ', ' || building AS classroom_name
            FROM classrooms
            ORDER BY building, room_number
        """),
    }


def grade_form_options() -> dict:
    """Справочники для формы выставления оценки."""
    return {
        "students": query("""
            SELECT s.student_id,
                   s.last_name || ' ' || s.first_name || ' (' ||
                   c.class_name || ', ' || s.student_status || ')' AS fio
            FROM students s
            JOIN classes c ON c.class_id = s.class_id
            ORDER BY s.last_name, s.first_name
        """),
        "subjects": query(
            "SELECT subject_id, subject_name FROM subjects ORDER BY subject_name"
        ),
        "teachers": query("""
            SELECT teacher_id,
                   last_name || ' ' || first_name || ' ' ||
                   COALESCE(middle_name, '') AS teacher_name
            FROM teachers
            ORDER BY last_name, first_name
        """),
    }


# --- Декораторы доступа -----------------------------------------------------

def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if "username" not in session:
                return redirect(url_for("login"))
            if session["username"] not in roles:
                flash("Недостаточно прав для просмотра раздела.", "warning")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapper
    return decorator


# --- Глобальные данные для шаблонов -----------------------------------------

@app.context_processor
def inject_user():
    role_labels = {
        "admin_db":      "Администратор БД",
        "operator_user": "Оператор",
        "auditor_user":  "Аудитор",
    }
    username = session.get("username")
    return {
        "current_user":  username,
        "current_role":  role_labels.get(username),
        "is_admin":      username == "admin_db",
        "is_operator":   username == "operator_user",
        "is_auditor":    username == "auditor_user",
        "now":           datetime.now,
    }


# --- Маршруты: авторизация --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username not in app.config["ALLOWED_ROLES"]:
            flash("Неизвестная роль.", "danger")
            return render_template("login.html")

        # Пробуем подключиться под этими учётными данными
        try:
            test_conn = psycopg2.connect(
                host=app.config["DB_HOST"],
                port=app.config["DB_PORT"],
                dbname=app.config["DB_NAME"],
                user=username,
                password=password,
                connect_timeout=5,
            )
            test_conn.close()
        except psycopg2.OperationalError as exc:
            flash(f"Ошибка авторизации: {exc}", "danger")
            return render_template("login.html")

        session["username"] = username
        session["password"] = password
        flash(f"Добро пожаловать, {username}", "success")
        return redirect(request.args.get("next") or url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из системы.", "info")
    return redirect(url_for("login"))


# --- Маршруты: дашборд ------------------------------------------------------

@app.route("/")
@login_required
def dashboard():
    # Базовая статистика — её видят все роли
    stats = {}
    stats["students_total"] = query(
        "SELECT COUNT(*) AS c FROM students"
    )[0]["c"]
    stats["teachers_total"] = query(
        "SELECT COUNT(*) AS c FROM teachers"
    )[0]["c"]
    stats["classes_total"] = query(
        "SELECT COUNT(*) AS c FROM classes"
    )[0]["c"]
    stats["grades_total"] = query(
        "SELECT COUNT(*) AS c FROM grades"
    )[0]["c"]

    # Метрики мониторинга — пробуем собрать через системные представления.
    # Если у роли нет прав — показываем заглушку.
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
        cur_conn.rollback() if cur_conn else None

    # Последние события мониторинга (через представление)
    recent_events = []
    try:
        recent_events = query(
            "SELECT * FROM v_recent_monitoring LIMIT 10"
        )
    except psycopg2.Error:
        get_db().rollback()

    return render_template(
        "dashboard.html",
        stats=stats,
        metrics=metrics,
        recent_events=recent_events,
    )


# --- Маршруты: просмотр данных ----------------------------------------------

@app.route("/students")
@login_required
def students():
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
    classes = query(
        "SELECT class_id, class_name FROM classes ORDER BY class_name"
    )
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
        flash(f"Ошибка обновления статуса: {friendly_db_error(exc)}", "danger")
    return redirect(url_for("students"))


@app.route("/grades", methods=["GET", "POST"])
@login_required
def grades():
    if request.method == "POST":
        if session["username"] not in {"admin_db", "operator_user"}:
            flash("Недостаточно прав для выставления оценок.", "warning")
            return redirect(url_for("grades"))

        student_id = request.form.get("student_id", "").strip()
        subject_id = request.form.get("subject_id", "").strip()
        teacher_id = request.form.get("teacher_id", "").strip()
        grade_value = request.form.get("grade_value", "").strip()
        grade_date = request.form.get("grade_date", "").strip()
        grade_comment = request.form.get("grade_comment", "").strip() or None

        try:
            execute_write(
                """
                INSERT INTO grades (
                    student_id, subject_id, teacher_id, grade_value,
                    grade_date, grade_comment
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    int(student_id),
                    int(subject_id),
                    int(teacher_id),
                    int(grade_value),
                    grade_date,
                    grade_comment,
                ),
            )
            flash("Оценка выставлена.", "success")
        except (ValueError, psycopg2.Error) as exc:
            message = (
                friendly_db_error(exc)
                if isinstance(exc, psycopg2.Error)
                else "Проверьте заполнение формы оценки."
            )
            flash(f"Ошибка выставления оценки: {message}", "danger")
        return redirect(url_for("grades", student_id=student_id))

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
        "grades.html",
        rows=rows, students=students_list,
        student_filter=student_filter,
        form_options=grade_form_options(),
    )


@app.route("/schedule", methods=["GET", "POST"])
@login_required
def schedule():
    if request.method == "POST":
        if session["username"] not in {"admin_db", "operator_user"}:
            flash("Недостаточно прав для изменения расписания.", "warning")
            return redirect(url_for("schedule"))

        class_id = request.form.get("class_id", "").strip()
        subject_id = request.form.get("subject_id", "").strip()
        teacher_id = request.form.get("teacher_id", "").strip()
        classroom_id = request.form.get("classroom_id", "").strip()
        lesson_date = request.form.get("lesson_date", "").strip()
        lesson_number = request.form.get("lesson_number", "").strip()

        try:
            execute_write(
                """
                INSERT INTO schedule (
                    class_id, subject_id, teacher_id, classroom_id,
                    lesson_date, lesson_number
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    int(class_id),
                    int(subject_id),
                    int(teacher_id),
                    int(classroom_id),
                    lesson_date,
                    int(lesson_number),
                ),
            )
            flash("Урок добавлен в расписание.", "success")
        except (ValueError, psycopg2.Error) as exc:
            message = (
                friendly_db_error(exc)
                if isinstance(exc, psycopg2.Error)
                else "Проверьте заполнение формы расписания."
            )
            flash(f"Ошибка изменения расписания: {message}", "danger")
        return redirect(url_for("schedule", date=lesson_date, class_id=class_id))

    date_filter = request.args.get("date", "").strip()
    class_filter = request.args.get("class_id", "").strip()

    sql = "SELECT * FROM v_class_schedule WHERE 1=1"
    params: list = []
    if date_filter:
        sql += " AND lesson_date = %s"
        params.append(date_filter)
    if class_filter:
        sql += " AND class_id = %s"
        params.append(int(class_filter))
    sql += " ORDER BY lesson_date, lesson_number, class_name LIMIT 200"

    rows = query(sql, tuple(params))
    options = schedule_form_options()
    return render_template(
        "schedule.html",
        rows=rows, classes=options["classes"],
        form_options=options,
        date_filter=date_filter, class_filter=class_filter,
    )


@app.route("/schedule/<int:schedule_id>/edit", methods=["GET", "POST"])
@role_required("admin_db", "operator_user")
def edit_schedule(schedule_id: int):
    rows = query(
        """
        SELECT schedule_id, class_id, subject_id, teacher_id, classroom_id,
               lesson_date, lesson_number
        FROM schedule
        WHERE schedule_id = %s
        """,
        (schedule_id,),
    )
    if not rows:
        flash("Запись расписания не найдена.", "warning")
        return redirect(url_for("schedule"))
    lesson = rows[0]

    if request.method == "POST":
        class_id = request.form.get("class_id", "").strip()
        subject_id = request.form.get("subject_id", "").strip()
        teacher_id = request.form.get("teacher_id", "").strip()
        classroom_id = request.form.get("classroom_id", "").strip()
        lesson_date = request.form.get("lesson_date", "").strip()
        lesson_number = request.form.get("lesson_number", "").strip()

        try:
            execute_write(
                """
                UPDATE schedule
                   SET class_id = %s,
                       subject_id = %s,
                       teacher_id = %s,
                       classroom_id = %s,
                       lesson_date = %s,
                       lesson_number = %s
                 WHERE schedule_id = %s
                """,
                (
                    int(class_id),
                    int(subject_id),
                    int(teacher_id),
                    int(classroom_id),
                    lesson_date,
                    int(lesson_number),
                    schedule_id,
                ),
            )
            flash("Урок в расписании обновлён.", "success")
            return redirect(
                url_for("schedule", date=lesson_date, class_id=class_id)
            )
        except (ValueError, psycopg2.Error) as exc:
            message = (
                friendly_db_error(exc)
                if isinstance(exc, psycopg2.Error)
                else "Проверьте заполнение формы расписания."
            )
            flash(f"Ошибка изменения расписания: {message}", "danger")

    return render_template(
        "schedule_form.html",
        lesson=lesson,
        form_options=schedule_form_options(),
    )


# --- Маршруты: импорт -------------------------------------------------------

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

        # Сохраняем файл
        safe_name = secure_filename(file.filename)
        save_path = Path(app.config["UPLOAD_DIR"]) / safe_name
        file.save(save_path)

        # Запускаем ETL — импортёр работает под учёткой admin
        # (это намеренно: web-роль operator_user может писать в таблицы,
        # но запись в import_log делается единым служебным каналом)
        result = import_file(save_path, table)

        if result["status"] == "completed":
            flash(
                f"Импорт завершён: загружено {result['rows_loaded']} строк "
                f"(import_id={result['import_id']})",
                "success",
            )
        else:
            flash(
                f"Импорт завершился с ошибкой: {result.get('error')}",
                "danger",
            )

    return render_template(
        "import.html",
        tables=list(TABLE_SPECS),
        result=result,
    )


@app.route("/import-log")
@login_required
def import_log():
    rows = query(
        "SELECT * FROM import_log ORDER BY import_time DESC LIMIT 100"
    )
    return render_template("import_log.html", rows=rows)


# --- Маршруты: мониторинг ---------------------------------------------------

@app.route("/monitoring")
@role_required("admin_db", "auditor_user")
def monitoring_view():
    rows = query(
        "SELECT * FROM monitoring_log ORDER BY event_time DESC LIMIT 100"
    )
    return render_template("monitoring.html", rows=rows)


@app.route("/monitoring/snapshot", methods=["POST"])
@role_required("admin_db")
def monitoring_snapshot():
    """Снимает текущие метрики и записывает в журнал."""
    try:
        # Используем admin-конфигурацию из переменных окружения,
        # потому что часть метрик требует системных привилегий
        from monitoring import write_to_log
        metrics = collect_metrics()
        write_to_log(metrics)
        flash("Снимок метрик сохранён в журнал мониторинга.", "success")
    except Exception as exc:
        flash(f"Ошибка сбора метрик: {exc}", "danger")
    return redirect(url_for("monitoring_view"))


# --- Запуск -----------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
