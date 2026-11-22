"""Заголовки безопасности и проверка работоспособности (/healthz).

Middleware стоит в списке первым: /healthz отвечает, не обращаясь к сессиям и БД
(платформа хостинга использует такой адрес для проверки «жив ли сервис»).
"""
from django.conf import settings
from django.http import JsonResponse


class HealthAndHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/healthz":
            return self._health(request)
        response = self.get_response(request)
        self._set(response, "Content-Security-Policy", settings.CSP_POLICY)
        self._set(response, "Permissions-Policy", settings.PERMISSIONS_POLICY)
        # ответы API и личные страницы не должны попадать в кэш браузера и прокси
        if request.path.startswith(("/api/", "/profile/", "/panel/", "/cart/")):
            self._set(response, "Cache-Control", "no-store")
        return response

    @staticmethod
    def _set(response, name, value):
        if not response.has_header(name):
            response[name] = value

    @staticmethod
    def _health(request):
        data = {"status": "ok"}
        if request.GET.get("db") == "1":      # /healthz?db=1 — дополнительно проверяет БД
            from django.db import connection
            try:
                connection.ensure_connection()
                data["db"] = "ok"
            except Exception:                  # детали ошибки наружу не отдаём
                return JsonResponse({"status": "error", "db": "unavailable"}, status=503)
        return JsonResponse(data)
