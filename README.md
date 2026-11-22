# VivoTech — интернет-магазин (Django + PostgreSQL), развёртывание на Timeweb Cloud

Лабораторная работа №4 «Хостинг, деплой и тестирование веб-приложения».
Стек: Python 3.12, Django 5.2, PostgreSQL, gunicorn, WhiteNoise, Docker.

## Структура развёртывания
| Файл | Назначение |
|---|---|
| `Dockerfile` | образ приложения (Python 3.12, шрифт DejaVu для PDF, gunicorn) |
| `entrypoint.sh` | при старте: проверка БД → миграции → статика → каталог и администратор → gunicorn |
| `config/settings.py`, `config/db_config.py` | все настройки из переменных окружения; HTTPS-флаги, CSP, HSTS |
| `store/security.py` | заголовки безопасности и проверка `/healthz` |
| `store/management/commands/` | `check_db`, `seed`, `bootstrap` (каталог + админ), `export_catalog` |
| `fixtures/catalog.json` | ваш каталог товаров (создаётся командой `export_catalog`) |
| `docker-compose.yml` | локальная проверка «как на сервере» |
| `tests/` | автотесты (pytest), нагрузочный сценарий k6, SQL-проверки целостности |

## Переменные окружения (на сервере)
`DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY` (обязательна), `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`,
`SITE_URL`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`. Подробнее — `.env.example`.

## Публикация на Timeweb Cloud (кратко)
1. Создать PostgreSQL в разделе «Базы данных» и записать адрес, порт, имя, пользователя, пароль.
2. Загрузить проект в репозиторий GitHub (папка `store/migrations/` из вашего проекта должна быть в репозитории).
3. Apps → Создать приложение → тип «Dockerfile» → выбрать репозиторий и ветку `main`.
4. Добавить переменные окружения (см. выше) и запустить деплой.
5. Открыть выданный адрес, затем указать его в `SITE_URL` и перезапустить приложение.

## Локальный запуск и тесты
```
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py runserver                      # разработка
pytest --cov                                    # автотесты и покрытие (SQLite, PostgreSQL не нужен)
docker compose up --build                       # проверка в контейнере: http://localhost:8000
```
Перед публикацией выгрузите каталог: `python manage.py export_catalog` (создаёт `fixtures/catalog.json`).
