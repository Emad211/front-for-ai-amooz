"""Build a REAL Persian PDF benchmark corpus (dev-only, run once).

Why this exists: synthetic fixtures can't prove Persian OCR quality. Real
Persian PDFs have notoriously broken text layers (presentation-form glyphs in
reversed order), which is exactly why this project extracts via a vision model
instead of the text layer. So we cannot use the PDF's own text as ground truth.

Instead we download a few open Persian Wikipedia articles as PDFs (CC BY-SA),
trim each to its first page to bound token cost, and capture the article's clean
plain-text *summary* (correct Persian, correct order) from the Wikipedia REST API
as the reference. The benchmark then measures how much of that reference text the
vision model correctly recovers from the rendered page (word recall), plus CER
for transparency, and asserts at least one embedded figure is extracted.

    python apps/classes/tests/fixtures/pdf/_build_real_corpus.py

Produces committed fixtures under ``pdf_corpus_real/`` + ``real_manifest.json``.
Re-running may differ as Wikipedia evolves; the committed snapshot is what tests
read. Attribution: text & media © Wikipedia contributors, CC BY-SA 4.0.
"""

from __future__ import annotations

import io
import json
import os
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "pdf_corpus_real")
UA = {"User-Agent": "ai-amooz-pdf-benchmark/1.0 (research; contact: dev@ai-amooz)"}

# (filename, wikipedia title, has an obvious lead figure?)
ARTICLES = [
    ("photosynthesis.pdf", "فتوسنتز", True),
    ("persian_gulf.pdf", "خلیج_فارس", True),
    ("iran.pdf", "ایران", True),
]

PAGES_PER_DOC = 1  # keep token cost minimal on the real benchmark


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=90).read()


def _summary_text(title: str) -> str:
    url = "https://fa.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title)
    data = json.loads(_get(url).decode("utf-8"))
    return (data.get("extract") or "").strip()


def _pdf(title: str) -> bytes:
    url = "https://fa.wikipedia.org/api/rest_v1/page/pdf/" + urllib.parse.quote(title)
    return _get(url)


def _trim(data: bytes, pages: int) -> bytes:
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(io.BytesIO(data))
    writer = PdfWriter()
    for i in range(min(pages, len(reader.pages))):
        writer.add_page(reader.pages[i])
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    manifest = {}
    for fname, title, has_fig in ARTICLES:
        try:
            ref = _summary_text(title)
            trimmed = _trim(_pdf(title), PAGES_PER_DOC)
        except Exception as exc:
            print(f"SKIP {fname} ({title}): {type(exc).__name__}: {exc}")
            continue
        with open(os.path.join(OUT, fname), "wb") as fh:
            fh.write(trimmed)
        manifest[fname] = {
            "lang": "persian",
            "title": title,
            "ref_text": ref,
            "expect_image": bool(has_fig),
            "source": f"https://fa.wikipedia.org/wiki/{title}",
            "license": "CC BY-SA 4.0",
        }
        print(f"wrote {fname}: {len(trimmed)} bytes, ref {len(ref)} chars")

    with open(os.path.join(OUT, "real_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print("Wrote real corpus:", ", ".join(sorted(manifest)))


if __name__ == "__main__":
    main()
