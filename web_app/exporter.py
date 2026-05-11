"""
Модуль формирования XLSX-выгрузок.

Используется веб-приложением: учитель скачивает своё расписание и оценки,
администратор выгружает учеников и журналы. Все отчёты формируются с
оформлением — жирные заголовки, цветовая индикация оценок, объединение
ячеек по дням, автоширина столбцов.
"""

from __future__ import annotations

import io
from datetime import date
from typing import Iterable

from openpyxl import Workbook
from openpyxl.styles import (
    Alignment, Border, Font, PatternFill, Side,
)
from openpyxl.utils import get_column_letter


# --- Стили ------------------------------------------------------------------

# Шапка отчётов
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
HEADER_FILL = PatternFill(start_color="305496", end_color="305496",
                          fill_type="solid")
HEADER_ALIGN = Alignment(horizontal="center", vertical="center",
                         wrap_text=True)

# Разделители
THIN = Side(border_style="thin", color="B0B7BF")
ALL_BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

# Заливка для оценок
GRADE_FILLS = {
    5: PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"),
    4: PatternFill(start_color="DDEBF7", end_color="DDEBF7", fill_type="solid"),
    3: PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid"),
    2: PatternFill(start_color="F8CBAD", end_color="F8CBAD", fill_type="solid"),
}

# Чередование строк
ALT_FILL = PatternFill(start_color="F2F2F2", end_color="F2F2F2",
                       fill_type="solid")

CENTER = Alignment(horizontal="center", vertical="center")
LEFT   = Alignment(horizontal="left",   vertical="center", wrap_text=True)


# --- Утилиты ----------------------------------------------------------------

def _apply_header_row(ws, row_idx: int, headers: list[str]) -> None:
    """Применяет стиль шапки к строке row_idx."""
    for col_idx, value in enumerate(headers, start=1):
        cell = ws.cell(row=row_idx, column=col_idx, value=value)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = HEADER_ALIGN
        cell.border = ALL_BORDER
    ws.row_dimensions[row_idx].height = 28


def _autosize(ws, min_width: int = 8, max_width: int = 40) -> None:
    """Подгоняет ширину столбцов под содержимое (по максимальной длине)."""
    for col_idx in range(1, ws.max_column + 1):
        max_len = min_width
        for row_idx in range(1, ws.max_row + 1):
            v = ws.cell(row=row_idx, column=col_idx).value
            if v is None:
                continue
            length = len(str(v))
            if length > max_len:
                max_len = length
        ws.column_dimensions[get_column_letter(col_idx)].width = min(
            max_len + 2, max_width
        )


def _to_bytes(wb: Workbook) -> io.BytesIO:
    """Сохраняет workbook в BytesIO для отдачи через Flask send_file."""
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# --- Расписание учителя -----------------------------------------------------

def export_teacher_schedule(
    teacher_full_name: str,
    rows: Iterable[dict],
    date_from: date,
    date_to: date,
) -> io.BytesIO:
    """Формирует XLSX с расписанием учителя за период.

    Ожидается, что rows содержит словари с ключами:
        lesson_date, lesson_number, class_name, subject_name,
        room_number, building.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Расписание"

    # Заголовок
    ws.cell(row=1, column=1,
            value=f"Расписание занятий — {teacher_full_name}").font = \
        Font(bold=True, size=14)
    ws.cell(row=2, column=1,
            value=f"Период: с {date_from:%d.%m.%Y} по {date_to:%d.%m.%Y}")
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=6)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=6)

    headers = ["Дата", "День недели", "№ урока",
               "Класс", "Предмет", "Кабинет"]
    _apply_header_row(ws, 4, headers)

    weekdays_ru = {0: "Понедельник", 1: "Вторник", 2: "Среда",
                   3: "Четверг",     4: "Пятница", 5: "Суббота",
                   6: "Воскресенье"}

    rows = list(rows)
    rows.sort(key=lambda r: (r["lesson_date"], r["lesson_number"]))

    cur_date = None
    row_idx = 5
    for r in rows:
        weekday = weekdays_ru.get(r["lesson_date"].weekday(), "")
        ws.cell(row=row_idx, column=1, value=r["lesson_date"].strftime("%d.%m.%Y"))
        ws.cell(row=row_idx, column=2, value=weekday)
        ws.cell(row=row_idx, column=3, value=r["lesson_number"])
        ws.cell(row=row_idx, column=4, value=r["class_name"])
        ws.cell(row=row_idx, column=5, value=r["subject_name"])
        ws.cell(row=row_idx, column=6,
                value=f"каб. {r['room_number']}, {r['building']}")
        for c in range(1, 7):
            ws.cell(row=row_idx, column=c).border = ALL_BORDER
            ws.cell(row=row_idx, column=c).alignment = (
                CENTER if c in (1, 2, 3, 4) else LEFT
            )
        # Чередование цвета по дням
        if cur_date != r["lesson_date"]:
            cur_date = r["lesson_date"]
            apply_alt = (row_idx % 2 == 0)
        if apply_alt:
            for c in range(1, 7):
                ws.cell(row=row_idx, column=c).fill = ALT_FILL
        row_idx += 1

    if not rows:
        ws.cell(row=5, column=1, value="Нет занятий за выбранный период.")
        ws.merge_cells(start_row=5, start_column=1, end_row=5, end_column=6)

    _autosize(ws)
    return _to_bytes(wb)


# --- Оценки класса по предмету ---------------------------------------------

def export_class_grades(
    class_name: str,
    subject_name: str,
    teacher_full_name: str,
    students: list[dict],
    grade_dates: list[date],
    grades_map: dict,
) -> io.BytesIO:
    """Формирует ведомость оценок класса по предмету.

    students: список словарей со student_id, full_name.
    grade_dates: отсортированный список дат, в которые ставились оценки.
    grades_map: dict с ключами (student_id, date) → {value, comment}.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = f"{class_name} — {subject_name[:15]}"

    # Шапка-описание
    ws.cell(row=1, column=1,
            value=f"Ведомость оценок: класс {class_name}, "
                  f"предмет «{subject_name}»").font = Font(bold=True, size=14)
    ws.cell(row=2, column=1,
            value=f"Учитель: {teacher_full_name}")
    cols_total = 2 + len(grade_dates) + 1  # № + ФИО + даты + средний
    ws.merge_cells(start_row=1, start_column=1,
                   end_row=1, end_column=cols_total)
    ws.merge_cells(start_row=2, start_column=1,
                   end_row=2, end_column=cols_total)

    # Шапка таблицы
    headers = ["№", "ФИО ученика"]
    headers.extend([d.strftime("%d.%m") for d in grade_dates])
    headers.append("Средний балл")
    _apply_header_row(ws, 4, headers)

    # Тело
    for s_idx, student in enumerate(students, start=1):
        row_idx = 4 + s_idx
        ws.cell(row=row_idx, column=1, value=s_idx).alignment = CENTER
        ws.cell(row=row_idx, column=2, value=student["full_name"]).alignment = LEFT

        values = []
        for d_idx, gdate in enumerate(grade_dates, start=3):
            entry = grades_map.get((student["student_id"], gdate))
            if entry:
                cell = ws.cell(row=row_idx, column=d_idx,
                               value=entry["value"])
                cell.fill = GRADE_FILLS.get(entry["value"], ALT_FILL)
                cell.font = Font(bold=True)
                if entry.get("comment"):
                    cell.comment = None  # можно задать openpyxl Comment, опускаем
                values.append(entry["value"])
            else:
                ws.cell(row=row_idx, column=d_idx, value="—")
            ws.cell(row=row_idx, column=d_idx).alignment = CENTER

        # Средний балл
        avg_col = 3 + len(grade_dates)
        if values:
            avg_cell = ws.cell(row=row_idx, column=avg_col,
                               value=round(sum(values) / len(values), 2))
            avg_cell.font = Font(bold=True)
        else:
            ws.cell(row=row_idx, column=avg_col, value="—")
        ws.cell(row=row_idx, column=avg_col).alignment = CENTER

        for c in range(1, cols_total + 1):
            ws.cell(row=row_idx, column=c).border = ALL_BORDER

    if not students:
        ws.cell(row=5, column=1, value="В классе нет учеников.")
        ws.merge_cells(start_row=5, start_column=1,
                       end_row=5, end_column=cols_total)
    elif not grade_dates:
        ws.cell(row=5, column=3, value="Оценки ещё не выставлялись.")

    _autosize(ws, min_width=6)
    # ФИО шире
    ws.column_dimensions["B"].width = 32
    return _to_bytes(wb)


# --- Список учеников (админская выгрузка) -----------------------------------

def export_students_list(rows: Iterable[dict]) -> io.BytesIO:
    """Полный список учеников с расшифровкой класса и статуса."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Ученики"

    ws.cell(row=1, column=1, value="Список учеников ГБОУ Школа №1416").font = \
        Font(bold=True, size=14)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=8)

    headers = ["№", "Фамилия", "Имя", "Отчество", "Класс",
               "Дата рождения", "Год поступления", "Статус"]
    _apply_header_row(ws, 3, headers)

    for idx, r in enumerate(rows, start=1):
        row_idx = 3 + idx
        ws.cell(row=row_idx, column=1, value=idx).alignment = CENTER
        ws.cell(row=row_idx, column=2, value=r["last_name"])
        ws.cell(row=row_idx, column=3, value=r["first_name"])
        ws.cell(row=row_idx, column=4, value=r.get("middle_name") or "")
        ws.cell(row=row_idx, column=5, value=r["class_name"]).alignment = CENTER
        ws.cell(row=row_idx, column=6,
                value=r["birth_date"].strftime("%d.%m.%Y")).alignment = CENTER
        ws.cell(row=row_idx, column=7,
                value=r["admission_year"]).alignment = CENTER
        ws.cell(row=row_idx, column=8,
                value=r["student_status"]).alignment = CENTER
        for c in range(1, 9):
            ws.cell(row=row_idx, column=c).border = ALL_BORDER
            if idx % 2 == 0:
                ws.cell(row=row_idx, column=c).fill = ALT_FILL

    _autosize(ws)
    return _to_bytes(wb)


# --- Журнал импорта или мониторинга -----------------------------------------

def export_log(title: str, headers: list[str],
               rows: Iterable[tuple]) -> io.BytesIO:
    """Универсальная выгрузка журнала."""
    wb = Workbook()
    ws = wb.active
    ws.title = title[:30]

    ws.cell(row=1, column=1, value=title).font = Font(bold=True, size=14)
    ws.merge_cells(start_row=1, start_column=1,
                   end_row=1, end_column=len(headers))

    _apply_header_row(ws, 3, headers)

    for idx, row in enumerate(rows, start=1):
        row_idx = 3 + idx
        for c_idx, value in enumerate(row, start=1):
            cell = ws.cell(row=row_idx, column=c_idx, value=value)
            cell.border = ALL_BORDER
            cell.alignment = LEFT if c_idx == len(row) else CENTER
            if idx % 2 == 0:
                cell.fill = ALT_FILL

    _autosize(ws)
    return _to_bytes(wb)
