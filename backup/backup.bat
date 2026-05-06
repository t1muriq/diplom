@echo off
rem Резервное копирование БД school_1416_db (Windows).
rem Запуск: backup.bat

setlocal

set SCRIPT_DIR=%~dp0
set CONTAINER=school_1416_postgres
set DB_NAME=school_1416_db
set DB_USER=admin

rem Формируем имя файла с датой и временем
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set DT=%%I
set TIMESTAMP=%DT:~0,8%_%DT:~8,6%
set DUMP_FILE=%SCRIPT_DIR%school_1416_db_%TIMESTAMP%.dump

echo [%TIME%] Создание бэкапа: %DUMP_FILE%

docker exec -t %CONTAINER% pg_dump -U %DB_USER% -d %DB_NAME% -Fc > "%DUMP_FILE%"

if errorlevel 1 (
    echo ОШИБКА: pg_dump завершился с ошибкой
    exit /b 1
)

echo [%TIME%] Готово.

endlocal
