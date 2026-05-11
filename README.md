# База данных и система администрирования ГБОУ Школа № 1416

Практическая часть выпускной квалификационной работы. Включает:

- развёртывание PostgreSQL 16 в Docker;
- DDL-схема, ролевая модель (4 роли), представления, триггеры;
- **Row-Level Security** для кабинета учителя;
- ETL-модуль автоматизированного импорта (CSV / XLSX / JSON);
- **модуль формирования XLSX-выгрузок с форматированием**;
- модуль мониторинга СУБД (6 ключевых метрик);
- скрипт резервного копирования;
- веб-приложение с двумя сценариями использования:
  - администраторский интерфейс для трёх технических ролей;
  - **личный кабинет учителя** с авторизацией по email + bcrypt-пароль;
- набор тестов pytest (37 тестов: импорт, производительность, ролевая
  модель, RLS, выгрузки).

## Структура проекта

```
school_1416_db/
├── docker-compose.yml      Контейнер PostgreSQL 16
├── requirements.txt        Зависимости Python
├── README.md               Этот документ
│
├── sql/                    Скрипты инициализации БД
│   ├── 01_schema.sql         DDL — 11 таблиц + индексы
│   ├── 02_roles.sql          Роли admin_db / operator_user / auditor_user
│   ├── 03_seed.sql           Демонстрационные данные
│   ├── 04_views.sql          Представления для типовых запросов
│   └── 05_triggers.sql       Триггеры журналирования и контроля
│
├── etl/                    Модуль импорта
│   ├── import_data.py        Универсальный импортёр
│   ├── validators.py         Проверка структуры файлов
│   ├── generate_samples.py   Генератор тестовых файлов
│   └── samples/              Тестовые файлы импорта
│
├── monitoring/             Модуль мониторинга
│   ├── monitoring.py         Сбор метрик и запись в журнал
│   └── queries.sql           Готовые SQL для DBeaver
│
├── backup/                 Резервное копирование
│   ├── backup.sh             Linux / macOS
│   └── backup.bat            Windows
│
├── web_app/                Веб-приложение администратора
│   ├── app.py                Точка входа Flask
│   ├── config.py             Конфигурация
│   ├── templates/            Jinja2-шаблоны
│   └── static/               CSS
│
└── tests/                  Тесты pytest
    ├── conftest.py
    ├── test_import.py
    ├── test_performance.py
    └── test_roles.py
```

## Требования к окружению

| Компонент | Версия | Назначение |
|---|---|---|
| Docker | ≥ 24.0 | Запуск PostgreSQL |
| Python | ≥ 3.11 | ETL, мониторинг, веб |
| Браузер | любой современный | Веб-интерфейс |
| DBeaver | ≥ 23 | Графическое администрирование (опционально) |

## Быстрый старт

### 1. Запуск базы данных

```bash
docker compose up -d
```

При первом запуске контейнер автоматически выполнит все скрипты из `sql/`
в алфавитном порядке: создаст схему, роли, представления, триггеры
и загрузит демонстрационные данные.

Проверка статуса:

```bash
docker ps                                     # контейнер должен быть Up
docker logs school_1416_postgres | tail -30   # проверка инициализации
```

### 2. Установка Python-зависимостей

```bash
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Запуск веб-приложения

```bash
cd web_app
python app.py
```

Откройте `http://localhost:5000`. Учётные данные по умолчанию:

**Технические роли:**
| Роль | Логин | Пароль |
|---|---|---|
| Администратор БД | `admin_db` | `Admin123!` |
| Оператор | `operator_user` | `Operator123!` |
| Аудитор | `auditor_user` | `Auditor123!` |

**Учителя** (вход через таб «Учитель», пароль для всех — `Teacher123!`):
| Email | Учитель |
|---|---|
| `sidorov@school1416.ru` | Сидоров А. В. (математика) |
| `smirnova@school1416.ru` | Смирнова Е. С. (русский язык) |
| `kuznetsov@school1416.ru` | Кузнецов Д. И. (информатика) |
| `orlova@school1416.ru` | Орлова М. П. (история) |
| `nikitin@school1416.ru` | Никитин П. А. (физика) |
| `fedorova@school1416.ru` | Федорова О. М. (англ. язык) |
| `morozov@school1416.ru` | Морозов И. Р. (биология) |

## Сценарии работы

### Импорт из командной строки

```bash
cd etl
python import_data.py samples/students_import.xlsx students
python import_data.py samples/grades_import.csv  grades
python import_data.py samples/schedule_import.json schedule
```

### Импорт через веб-интерфейс

1. Войти как `admin_db` или `operator_user`.
2. Меню → «Импорт».
3. Выбрать целевую таблицу и файл.
4. После загрузки результат отобразится на этой же странице,
   запись появится в «Журнале импорта».

### Снятие метрик мониторинга

Разовый снимок в консоль:
```bash
cd monitoring
python monitoring.py
```

Регулярный сбор каждые 60 секунд (например, в фоне на сервере):
```bash
python monitoring.py --daemon --interval 60
```

Снимок через веб (только `admin_db`):
- Меню → «Мониторинг» → кнопка «📸 Снять снимок метрик сейчас».

### Резервное копирование

Linux / macOS:
```bash
./backup/backup.sh
```

Windows:
```cmd
backup\backup.bat
```

Скрипт создаёт файл вида `school_1416_db_YYYYMMDD_HHMMSS.dump` в формате
PostgreSQL custom (`-Fc`). Восстановление:

```bash
docker exec -i school_1416_postgres pg_restore \
    -U admin -d school_1416_db -c < backup/school_1416_db_20260101_120000.dump
```

Автоматизация в cron (Linux):
```cron
0 3 * * *  /home/user/school_1416_db/backup/backup.sh >> /var/log/school_backup.log 2>&1
```

### Запуск тестов

```bash
pytest tests/ -v
```

При запущенной БД будут выполнены три набора:
- `test_import.py` — корректность ETL,
- `test_performance.py` — время выполнения SELECT на представлениях,
- `test_roles.py` — соответствие матрицы доступа.

## Руководство администратора

### Подключение через DBeaver

1. New Database Connection → PostgreSQL.
2. Host: `localhost`, Port: `5432`, Database: `school_1416_db`.
3. User: `admin` / Password: `Admin123!` (для полного доступа)
   или одна из ролей ограниченного доступа.
4. Test Connection → Finish.

В дереве подключений будут видны:
- 11 таблиц предметной области и журналов;
- 5 представлений (`v_student_grades`, `v_class_schedule`,
  `v_attendance_summary`, `v_recent_imports`, `v_recent_monitoring`);
- 2 триггера (`trg_import_to_monitoring`, `trg_check_grade_active`);
- роли `admin_db`, `operator_user`, `auditor_user`.

ER-диаграмма: правый клик на схеме `public` → View Diagram.

### Регламентные работы

| Операция | Периодичность | Кто выполняет | Команда |
|---|---|---|---|
| Резервное копирование | Ежедневно в 03:00 | cron | `backup.sh` |
| Сбор метрик | Каждые 60 с | systemd / supervisor | `monitoring.py --daemon` |
| Проверка целостности | Еженедельно | DBA вручную | `pytest tests/` |
| Обновление PostgreSQL | По выходу патч-версий | DBA | `docker compose pull && docker compose up -d` |

### Действия при инцидентах

- **Импорт завершился ошибкой.** Открыть «Журнал импорта», найти запись
  со статусом `failed`. Проверить структуру файла (см. подсказку колонок
  на странице «Импорт»). Транзакция отката гарантирует, что данные в БД
  не повреждены.
- **Cache hit ratio упал ниже 0.9.** Возможен недостаток `shared_buffers`
  или активная индексная просадка. Проверить через `queries.sql` запрос 7
  (использование индексов).
- **Появились deadlocks.** Журнал PostgreSQL: `docker logs school_1416_postgres`.

### Разграничение доступа

Реализуется через роли PostgreSQL (см. `sql/02_roles.sql`):

| Таблица | admin_db | operator_user | auditor_user |
|---|---|---|---|
| students, teachers, classes, subjects, classrooms | S/I/U/D | S/I/U | SELECT |
| schedule, grades, attendance | S/I/U/D | S/I/U | SELECT |
| confidential_data | S/I/U/D | — | SELECT |
| import_log | S/I/U/D | SELECT | SELECT |
| monitoring_log | S/I/U/D | — | SELECT |

S = SELECT, I = INSERT, U = UPDATE, D = DELETE.

Веб-приложение использует переданный пользователем пароль для прямого
подключения к СУБД от имени роли. Это гарантирует, что разграничение
прав происходит **на уровне PostgreSQL** и не может быть обойдено
ошибкой в коде приложения.

## Кабинет учителя

Учителя авторизуются по email и паролю (хэш bcrypt в `teacher_accounts`).
В кабинете учитель видит:

- расписание своих уроков на ближайшие 2 недели,
- список своих предметов и классов (с кнопкой выгрузки),
- последние выставленные им оценки.

Учитель может:

- **скачать своё расписание** в XLSX за выбранный период (страница «Кабинет» → форма с датами → «Скачать XLSX»),
- **скачать ведомость оценок** класса по своему предмету в XLSX
  (Кабинет → «Мои предметы и классы» → клик на нужную пару).

Все запросы учителя автоматически фильтруются Row-Level Security:
учитель физически не может увидеть чужие уроки или оценки, даже если
изменит URL вручную. Эту защиту обеспечивает PostgreSQL, а не код Flask.

## Row-Level Security

Файл `sql/06_rls.sql` устанавливает RLS-политики для роли `teacher_user`:

- На таблицах `schedule` и `grades` включены политики, которые сравнивают
  `teacher_id` строки с параметром сессии `app.current_teacher_id`.
- Веб-приложение устанавливает этот параметр сразу после подключения
  к СУБД (см. `web_app/app.py`, функция `get_db()`).
- Технические роли (`admin_db`, `operator_user`, `auditor_user`)
  имеют отдельные политики `*_full_access` с `USING (TRUE)`, поэтому
  RLS на них не влияет.

Проверить работу RLS из psql:

```sql
-- admin_db видит всё
SELECT COUNT(*) FROM schedule;  -- 12

-- teacher_user без app.current_teacher_id не видит ничего
\c school_1416_db teacher_user
SELECT COUNT(*) FROM schedule;  -- 0

-- С установленным teacher_id=1 видит только записи Сидорова
SET app.current_teacher_id = '1';
SELECT COUNT(*) FROM schedule;  -- 2
```

## Модуль выгрузок XLSX

Файл `web_app/exporter.py` формирует Excel-отчёты с использованием openpyxl:

- цветовая индикация оценок (5 — зелёный, 4 — синий, 3 — жёлтый, 2 — оранжевый),
- жирные шапки на синем фоне,
- автоматическая ширина столбцов,
- объединение ячеек заголовка,
- чередующаяся заливка строк.

Доступные выгрузки:

| Маршрут | Кто доступен | Что выгружается |
|---|---|---|
| `/teacher/export/schedule?from=&to=` | Учитель | Расписание учителя за период |
| `/teacher/export/grades/<class_id>/<subject_id>` | Учитель | Ведомость оценок класс×предмет |
| `/export/students` | admin/operator/auditor | Полный список учеников |
| `/export/import-log` | admin/operator/auditor | Журнал импорта |
| `/export/monitoring-log` | admin/auditor | Журнал мониторинга |
