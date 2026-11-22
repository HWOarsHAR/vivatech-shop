"""Общие вспомогательные функции для тестов."""
import json


def _kw(token):
    kw = {"content_type": "application/json"}
    if token:
        kw["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return kw


def jpost(client, path, data=None, token=None):
    return client.post(path, data=json.dumps({} if data is None else data), **_kw(token))


def jput(client, path, data=None, token=None):
    return client.put(path, data=json.dumps({} if data is None else data), **_kw(token))


def jget(client, path, token=None):
    kw = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    return client.get(path, **kw)


def session_login(client, user):
    """Вход «через сессию» (для HTML-страниц и админ-панели) без обращения к форме входа."""
    s = client.session
    s["user_id"] = user.id
    s["role"] = user.role
    s.save()


def reg_payload(**kw):
    data = {"name": "Иван Петров", "email": "ivan@example.com", "phone": "", "password": "Passw0rd!",
            "confirm_password": "Passw0rd!", "consent": True, "terms": True, "ads": False}
    data.update(kw)
    return data
