"""Совместимость с SQLite: регистронезависимый поиск для кириллицы.

Встроенный оператор LIKE в SQLite различает регистр букв вне ASCII, поэтому запрос «смартфон»
не нашёл бы «Смартфон» (в PostgreSQL ILIKE работает корректно). Здесь LIKE подменяется
функцией с поддержкой Юникода; Django использует её для lookup'ов contains / icontains.
"""
import re


def unicode_like(pattern, value, escape=None):
    """Реализация SQL-оператора `value LIKE pattern [ESCAPE escape]` без учёта регистра."""
    if pattern is None or value is None:
        return None
    parts, i = [], 0
    while i < len(pattern):
        ch = pattern[i]
        if escape and ch == escape and i + 1 < len(pattern):
            i += 1
            parts.append(re.escape(pattern[i]))
        elif ch == "%":
            parts.append(".*")
        elif ch == "_":
            parts.append(".")
        else:
            parts.append(re.escape(ch))
        i += 1
    return 1 if re.fullmatch("".join(parts), str(value), re.IGNORECASE | re.DOTALL) else 0


def install(dbapi_connection):
    """Подменяет like() в соединении SQLite (с ESCAPE и без него)."""
    dbapi_connection.create_function("LIKE", 2, unicode_like)
    dbapi_connection.create_function("LIKE", 3, unicode_like)
