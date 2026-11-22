#!/bin/sh
# Запуск контейнера: схема БД -> статика -> каталог и администратор -> веб-сервер.
set -eu

echo "[1/4] Проверка подключения к БД"
python manage.py check_db

echo "[2/4] Применение схемы БД (миграции)"
# --run-syncdb создаёт таблицы приложений без файлов миграций; если store/migrations есть в репозитории,
# применяются обычные миграции
python manage.py migrate --run-syncdb --noinput

echo "[3/4] Сбор статических файлов и первичная настройка"
python manage.py collectstatic --noinput
python manage.py bootstrap

echo "[4/4] Запуск gunicorn на 0.0.0.0:${PORT:-8000}"
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" --threads "${WEB_THREADS:-4}" \
  --timeout 60 --access-logfile - --error-logfile -
