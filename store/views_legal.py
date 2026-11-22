"""Страницы юридических документов и скачивание в форматах HTML / PDF / TXT / ODT."""
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse

from . import legal

# формат -> (MIME-тип, функция-сборщик); HTML обрабатывается отдельно (это шаблон)
BUILDERS = {
    "pdf": ("application/pdf", legal.to_pdf),
    "txt": ("text/plain; charset=utf-8", legal.to_txt),
    "odt": ("application/vnd.oasis.opendocument.text", legal.to_odt),
}


def _doc_or_404(slug):
    doc = legal.get_doc(slug)
    if doc is None:
        raise Http404("Документ не найден")
    return doc


def legal_page(request, slug):
    """Документ в браузере (открывается в новой вкладке) + ссылки на скачивание."""
    doc = _doc_or_404(slug)
    others = [{"title": legal.DOCS[s]["title"], "url": reverse(s)} for s in legal.DOCS if s != slug]
    return render(request, "legal_doc.html", {"doc": doc, "others": others, "download": False})


def legal_download(request, slug, fmt):
    """Скачивание: /docs/privacy.pdf, /docs/terms.odt, /docs/privacy.txt, /docs/privacy.html"""
    doc = _doc_or_404(slug)
    if fmt == "html":
        content = render_to_string("legal_doc.html", {"doc": doc, "download": True}).encode("utf-8")
        ctype = "text/html; charset=utf-8"
    elif fmt in BUILDERS:
        ctype, builder = BUILDERS[fmt]
        try:
            content = builder(doc)
        except legal.PdfUnavailable as exc:  # понятное сообщение вместо ошибки 500
            return HttpResponse(str(exc), status=503, content_type="text/plain; charset=utf-8")
    else:
        raise Http404("Неизвестный формат")
    resp = HttpResponse(content, content_type=ctype)
    resp["Content-Disposition"] = f'attachment; filename="{doc["filename"]}.{fmt}"'
    return resp
