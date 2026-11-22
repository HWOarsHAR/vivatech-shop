"""Тесты юридических документов: страницы и скачивание HTML / PDF / TXT / ODT."""
import io
import xml.etree.ElementTree as ET
import zipfile

import pytest

from store import legal

pytestmark = pytest.mark.django_db


def test_documents_are_complete():
    for slug in ("privacy", "terms"):
        doc = legal.get_doc(slug)
        assert doc["title"] and len(doc["sections"]) >= 10
        text = " ".join(p for s in doc["sections"] for p in s["paragraphs"])
        assert "{" not in text and "}" not in text            # все поля подставлены
        assert legal.COMPANY["email"] in text
    assert legal.get_doc("nope") is None


def test_privacy_covers_required_topics():
    text = " ".join(p for s in legal.get_doc("privacy")["sections"] for p in s["paragraphs"]).lower()
    for word in ("152-фз", "согласи", "третьим лицам", "рассылк", "cookie", "отзыв", "роскомнадзор", "территории российской федерации"):
        assert word in text, word


def test_txt_format():
    data = legal.to_txt(legal.get_doc("privacy"))
    assert data.startswith(b"\xef\xbb\xbf")                  # UTF-8 с BOM
    assert "ПОЛИТИКА ОБРАБОТКИ ПЕРСОНАЛЬНЫХ ДАННЫХ" in data.decode("utf-8-sig")


def test_odt_is_valid_package():
    z = zipfile.ZipFile(io.BytesIO(legal.to_odt(legal.get_doc("terms"))))
    first = z.infolist()[0]
    assert first.filename == "mimetype" and first.compress_type == zipfile.ZIP_STORED
    assert z.read("mimetype") == b"application/vnd.oasis.opendocument.text"
    root = ET.fromstring(z.read("content.xml"))                # XML корректен
    assert "Пользовательское соглашение" in "".join(root.itertext())
    ET.fromstring(z.read("META-INF/manifest.xml"))


def test_pdf_is_generated():
    pytest.importorskip("reportlab")
    try:
        data = legal.to_pdf(legal.get_doc("privacy"))
    except legal.PdfUnavailable:
        pytest.skip("нет шрифта с кириллицей в системе")
    assert data.startswith(b"%PDF") and len(data) > 5000


class TestViews:
    def test_pages_have_download_links(self, client):
        for slug, title in (("privacy", "Политика"), ("terms", "Пользовательское соглашение")):
            content = client.get(f"/{slug}/").content.decode("utf-8")
            assert title in content
            for fmt in ("pdf", "txt", "odt", "html"):
                assert f"/docs/{slug}.{fmt}" in content

    @pytest.mark.parametrize("slug, fmt, mime", [
        ("privacy", "txt", "text/plain"), ("terms", "txt", "text/plain"),
        ("privacy", "odt", "application/vnd.oasis.opendocument.text"),
        ("terms", "html", "text/html"),
    ])
    def test_downloads(self, client, slug, fmt, mime):
        r = client.get(f"/docs/{slug}.{fmt}")
        assert r.status_code == 200 and r["Content-Type"].startswith(mime)
        assert "attachment" in r["Content-Disposition"] and f".{fmt}" in r["Content-Disposition"]

    def test_pdf_download(self, client):
        r = client.get("/docs/privacy.pdf")
        assert r.status_code in (200, 503)                       # 503 — нет reportlab/шрифта
        if r.status_code == 200:
            assert r["Content-Type"] == "application/pdf" and r.content.startswith(b"%PDF")

    def test_unknown_document_or_format(self, client):
        assert client.get("/docs/nope.txt").status_code == 404
        assert client.get("/docs/privacy.exe").status_code == 404
