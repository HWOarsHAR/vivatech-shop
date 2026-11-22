from .models import Category


def common(request):
    """Переменные, доступные во всех шаблонах."""
    return {
        "current_user": getattr(request, "current_user", None),
        "menu_categories": Category.objects.all(),
    }
