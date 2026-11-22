from .models import User


class CurrentUserMiddleware:
    """Кладёт в request.current_user пользователя из сессии (или None)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.current_user = None
        uid = request.session.get("user_id")
        if uid:
            request.current_user = User.objects.filter(pk=uid).first()
            if request.current_user is None:  # пользователя удалили — чистим сессию
                request.session.flush()
        return self.get_response(request)
