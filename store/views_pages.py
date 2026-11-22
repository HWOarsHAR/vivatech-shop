"""HTML-страницы магазина."""
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils.http import url_has_allowed_host_and_scheme

from .auth import log_action, login_required
from .models import Category, Product
from .views_api import search_products

SORTS = {"new": ("-created_at", "Новинки"), "price": ("price", "Цена ↑"),
         "-price": ("-price", "Цена ↓"), "name": ("name", "Название А–Я")}


def index(request):
    qs = Product.objects.filter(available=True)
    cat = request.GET.get("category")
    if cat:
        qs = qs.filter(categories__alias=cat)
    sort = request.GET.get("sort", "new")
    qs = qs.order_by(SORTS.get(sort, SORTS["new"])[0])
    page = Paginator(qs.distinct(), 8).get_page(request.GET.get("page"))
    # «последние просмотренные» — из сессии (Задание 5)
    ids = request.session.get("last_viewed", [])
    viewed = sorted(Product.objects.filter(pk__in=ids), key=lambda p: ids.index(p.id))
    return render(request, "index.html", {"page": page, "sorts": SORTS, "sort": sort,
                                          "cat": cat, "viewed": viewed})


def product_detail(request, pk):
    product = get_object_or_404(Product.objects.prefetch_related("properties", "images"), pk=pk)
    ids = [i for i in request.session.get("last_viewed", []) if i != pk]
    request.session["last_viewed"] = ([pk] + ids)[:5]          # храним 5 последних
    log_action(request.current_user, "view_product", f"/product/{pk}/")
    return render(request, "product.html", {"p": product})


def search_page(request):
    q = request.GET.get("q", "").strip()
    results, error = None, None
    if q:
        if len(q) < 2:
            error = "Введите минимум 2 символа"
        else:
            results = search_products(q, request.GET.get("sort", ""))
            hist = [h for h in request.session.get("search_history", []) if h != q]
            request.session["search_history"] = ([q] + hist)[:10]
            log_action(request.current_user, "search", q)
    return render(request, "search.html", {"q": q, "results": results, "error": error,
                                           "history": request.session.get("search_history", [])})


def register_page(request):
    return render(request, "register.html")


def login_page(request):
    nxt = request.GET.get("next", "/profile/")
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts=None):  # защита от open redirect
        nxt = "/profile/"
    return render(request, "login.html", {"next": nxt})


def feedback_page(request):
    return render(request, "feedback.html")


@login_required
def profile_page(request):
    # Доступ только по активной сессии; данные страница подгружает из API по JWT
    return render(request, "profile.html")


def cart_page(request):
    return render(request, "cart.html")


def privacy(request):
    """Политика конфиденциальности — открывается в новой вкладке (target=_blank)."""
    return render(request, "privacy.html")


def privacy_download(request):
    """Та же политика, но как скачиваемый файл."""
    html = render_to_string("privacy.html", request=request)
    resp = HttpResponse(html, content_type="text/html; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="privacy_policy.html"'
    return resp
