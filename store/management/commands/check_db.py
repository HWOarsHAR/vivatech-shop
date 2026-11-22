from django.core.management.base import BaseCommand, CommandError

from config.db_config import check_connection


class Command(BaseCommand):
    help = "Проверка соединения с PostgreSQL (Задание 2)"

    def handle(self, *args, **opts):
        ok, msg = check_connection()
        if not ok:
            raise CommandError(msg)
        self.stdout.write(self.style.SUCCESS(msg))
