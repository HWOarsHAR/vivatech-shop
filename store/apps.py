from django.apps import AppConfig
from django.db.backends.signals import connection_created


def _patch_sqlite(sender, connection, **kwargs):
    if connection.vendor == "sqlite":
        from . import sqlite_compat
        sqlite_compat.install(connection.connection)


class StoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "store"
    verbose_name = "Магазин"

    def ready(self):
        # при каждом открытии соединения с SQLite подключаем Unicode-совместимый LIKE
        connection_created.connect(_patch_sqlite, dispatch_uid="store_sqlite_like")
