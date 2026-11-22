"""REST-подобное API (Задание 6). Аутентификация — JWT (заголовок Authorization: Bearer ...).

Все API-вью помечены csrf_exempt: они защищены не cookie, а токеном в заголовке,
поэтому CSRF-атака через браузер невозможна.
"""
import json
from datetime import timedelta

import jwt
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .auth import (decode_token, get_api_user, hash_password, jwt_required, log_action,
                   make_tokens, verify_password)
from .forms import (CheckoutConsentForm, FeedbackForm, LoginForm, PasswordChangeForm,
                   ProfileForm, RegisterForm, normalize_phone)
from .models import CartItem, Feedback, Order, OrderItem, Product, User, UserSession


# ---------- вспомогательные функции ----------
def body(request) -> dict:
    """Тело запроса: JSON (fetch) или обычные form-data."""
    if request.content_type == "application/json":
        try:
            data = json.loads(request.body or b"{}")
            return data if isinstance(data, dict) else {}
        except ValueError:
            return {}
    return request.POST.dict()


def form_errors(form):
    return JsonResponse({"errors": {k: [str(e) for e in v] for k, v in form.errors.items()}}, status=400)


def user_json(u: User):
    return {"id": u.id, "name": u.name, "email": u.email, "phone": u.phone, "role": u.role,
            "created_at": u.created_at.isoformat(),
            "last_login": u.last_login.isoformat() if u.last_login else None}


def product_json(p: Product):
    return {"id": p.id, "name": p.name, "short_description": p.short_description,
            "price": float(p.price), "image": p.image_url, "available": p.available,
            "url": f"/product/{p.id}/"}


def client_ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    return (fwd.split(",")[0].strip() if fwd else request.META.get("REMOTE_ADDR")) or None


def search_products(q: str, sort: str = ""):
    """Поиск по названию, краткому и полному описанию (регистронезависимо, ILIKE в PostgreSQL)."""
    qs = Product.objects.filter(Q(name__icontains=q) | Q(short_description__icontains=q) |
                                Q(description__icontains=q))
    order = {"price": "price", "-price": "-price", "name": "name"}.get(sort, "-created_at")
    return qs.order_by(order)


# ---------- аутентификация ----------
@csrf_exempt
@require_POST
def register(request):
    form = RegisterForm(body(request))
    if not form.is_valid():
        return form_errors(form)
    d = form.cleaned_data
    user = User.objects.create(name=d["name"], email=d.get("email"), phone=d.get("phone"),
                               password_hash=hash_password(d["password"]),  # bcrypt
                               consent_at=timezone.now(),
                               terms_accepted_at=timezone.now(),
                               ads_consent_at=timezone.now() if d.get("ads") else None)
    log_action(user, "register", "/register/")
    return JsonResponse({"message": "Регистрация успешна", "user": user_json(user)}, status=201)


@csrf_exempt
@require_POST
def login(request):
    form = LoginForm(body(request))
    if not form.is_valid():
        return form_errors(form)
    value = form.cleaned_data["login"].strip()
    if "@" in value:
        user = User.objects.filter(email=value.lower()).first()
    else:
        phone = normalize_phone(value)
        user = User.objects.filter(phone=phone).first() if phone else None
    if user is None or not verify_password(form.cleaned_data["password"], user.password_hash):
        return JsonResponse({"errors": {"__all__": ["Неверный email или пароль"]}}, status=401)

    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])

    # Серверная сессия (хранится в БД) + запись в user_sessions
    request.session["user_id"] = user.id
    request.session["role"] = user.role
    request.session.cycle_key()  # новый ключ сессии — защита от session fixation
    UserSession.objects.create(
        user=user, session_token=request.session.session_key, ip_address=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
        expires_at=timezone.now() + timedelta(seconds=settings.SESSION_COOKIE_AGE))
    log_action(user, "login", "/login/")
    return JsonResponse({"user": user_json(user), **make_tokens(user)})


@csrf_exempt
@require_POST
def refresh(request):
    """Обмен refresh-токена на новый access-токен."""
    token = body(request).get("refresh", "")
    try:
        payload = decode_token(token, "refresh")
    except jwt.PyJWTError:
        return JsonResponse({"error": "Refresh-токен недействителен"}, status=401)
    user = User.objects.filter(pk=payload["sub"]).first()
    if user is None:
        return JsonResponse({"error": "Пользователь не найден"}, status=401)
    return JsonResponse(make_tokens(user))


@csrf_exempt
@require_POST
def logout(request):
    user = get_api_user(request) or request.current_user
    if user:
        UserSession.objects.filter(session_token=request.session.session_key).delete()
        log_action(user, "logout", "/logout/")
    request.session.flush()  # уничтожаем серверную сессию
    return JsonResponse({"message": "Вы вышли из системы"})


# ---------- профиль ----------
@csrf_exempt
@require_http_methods(["GET", "PUT"])
@jwt_required
def profile(request):
    user = request.api_user
    if request.method == "GET":
        return JsonResponse(user_json(user))
    form = ProfileForm(body(request), user=user)
    if not form.is_valid():
        return form_errors(form)
    user.name = form.cleaned_data["name"]
    user.email = form.cleaned_data["email"]
    user.phone = form.cleaned_data["phone"]
    user.save(update_fields=["name", "email", "phone"])
    log_action(user, "update_profile", "/profile/")
    return JsonResponse(user_json(user))


@csrf_exempt
@require_POST
@jwt_required
def change_password(request):
    user = request.api_user
    form = PasswordChangeForm(body(request), user=user)
    if not form.is_valid():
        return form_errors(form)
    user.password_hash = hash_password(form.cleaned_data["new_password"])
    user.save(update_fields=["password_hash"])
    log_action(user, "change_password", "/profile/")
    return JsonResponse({"message": "Пароль изменён"})


# ---------- обратная связь ----------
@csrf_exempt
@require_http_methods(["GET", "POST"])
@jwt_required
def feedback(request):
    user = request.api_user
    if request.method == "POST":
        form = FeedbackForm(body(request))
        if not form.is_valid():
            return form_errors(form)
        d = form.cleaned_data
        d.pop("consent", None)
        fb = Feedback.objects.create(user=user, consent_at=timezone.now(), **d)
        log_action(user, "send_feedback", "/feedback/")
        return JsonResponse({"id": fb.id, "message": "Спасибо! Сообщение отправлено"}, status=201)
    items = [{"id": f.id, "subject": f.subject, "message": f.message, "rating": f.rating,
              "status": f.get_status_display(), "created_at": f.created_at.isoformat()}
             for f in Feedback.objects.filter(user=user)]
    return JsonResponse({"results": items})


# ---------- поиск ----------
@csrf_exempt
@require_http_methods(["GET"])
def search(request):
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse({"errors": {"q": ["Минимум 2 символа"]}}, status=400)
    results = [product_json(p) for p in search_products(q, request.GET.get("sort", ""))[:50]]
    # история поиска в сессии (последние 10 уникальных)
    hist = [h for h in request.session.get("search_history", []) if h != q]
    request.session["search_history"] = ([q] + hist)[:10]
    log_action(get_api_user(request), "search", q)
    return JsonResponse({"query": q, "count": len(results), "results": results})


# ---------- журнал действий ----------
@csrf_exempt
@require_http_methods(["GET"])
@jwt_required
def actions(request):
    try:
        limit = min(max(int(request.GET.get("limit", 20)), 1), 100)
    except ValueError:
        limit = 20
    items = [{"action": a.action, "page": a.page, "created_at": a.created_at.isoformat()}
             for a in request.api_user.actions.all()[:limit]]
    return JsonResponse({"results": items})


# ---------- корзина ----------
def _cart_response(cart: dict):
    """cart = {product_id: qty} -> JSON с актуальными ценами из БД."""
    prods = Product.objects.in_bulk([int(i) for i in cart])
    items, total = [], 0
    for pid, qty in cart.items():
        p = prods.get(int(pid))
        if p and p.available:
            items.append({**product_json(p), "product_id": p.id, "qty": qty,
                          "subtotal": float(p.price) * qty})
            total += float(p.price) * qty
    return JsonResponse({"items": items, "total": round(total, 2)})


@csrf_exempt
@require_http_methods(["GET", "PUT"])
def cart(request):
    """Корзина: всегда в сессии; если есть JWT — дополнительно в БД (cart_items)."""
    user = get_api_user(request)
    if request.method == "PUT":
        items = body(request).get("items")
        if not isinstance(items, list):
            return JsonResponse({"errors": {"items": ["Ожидался список"]}}, status=400)
        wanted = {}
        for it in items:
            try:
                pid, qty = int(it["product_id"]), int(it["qty"])
            except (KeyError, TypeError, ValueError):
                return JsonResponse({"errors": {"items": ["Некорректный элемент"]}}, status=400)
            if not 1 <= qty <= 99:
                return JsonResponse({"errors": {"items": ["Количество от 1 до 99"]}}, status=400)
            wanted[pid] = qty
        valid = Product.objects.filter(pk__in=wanted, available=True).values_list("id", flat=True)
        clean = {pid: wanted[pid] for pid in valid}
        request.session["cart"] = {str(k): v for k, v in clean.items()}  # краткосрочно — сессия
        if user:  # долгосрочно — БД, привязка к пользователю
            with transaction.atomic():
                CartItem.objects.filter(user=user).delete()
                CartItem.objects.bulk_create(
                    [CartItem(user=user, product_id=pid, quantity=q) for pid, q in clean.items()])
        return _cart_response(clean)
    if user:
        cart_data = {ci.product_id: ci.quantity for ci in CartItem.objects.filter(user=user)}
    else:
        cart_data = request.session.get("cart", {})
    return _cart_response(cart_data)


# ---------- заказы ----------
@csrf_exempt
@require_http_methods(["GET", "POST"])
@jwt_required
def orders(request):
    user = request.api_user
    if request.method == "POST":
        consent_form = CheckoutConsentForm(body(request))
        if not consent_form.is_valid():
            return form_errors(consent_form)
        # Цены берём из БД, а не от клиента (клиенту доверять нельзя)
        cart_items = list(CartItem.objects.filter(user=user, product__available=True)
                          .select_related("product"))
        if not cart_items:
            return JsonResponse({"error": "Корзина пуста"}, status=400)
        with transaction.atomic():
            total = sum(ci.product.price * ci.quantity for ci in cart_items)
            now = timezone.now()
            order = Order.objects.create(user=user, total=total, consent_at=now,
                                         third_party_consent_at=now, terms_accepted_at=now)
            OrderItem.objects.bulk_create([OrderItem(order=order, product=ci.product, name=ci.product.name,
                                                     price=ci.product.price, quantity=ci.quantity)
                                           for ci in cart_items])
            CartItem.objects.filter(user=user).delete()
        request.session["cart"] = {}
        log_action(user, "checkout", f"order #{order.id}")
        return JsonResponse({"id": order.id, "total": float(order.total)}, status=201)
    data = [{"id": o.id, "status": o.get_status_display(), "total": float(o.total),
             "created_at": o.created_at.isoformat(),
             "items": [{"name": i.name, "price": float(i.price), "qty": i.quantity} for i in o.items.all()]}
            for o in Order.objects.filter(user=user).prefetch_related("items")]
    return JsonResponse({"results": data})
