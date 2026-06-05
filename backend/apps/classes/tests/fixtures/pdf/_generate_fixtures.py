"""Generate the committed PDF fixtures + ground-truth manifest (dev-only).

Run once to (re)create the fixtures used by ``test_pdf_extraction_unit.py``.
NOT used in CI and NOT a runtime dependency — needs reportlab + Pillow + a
font with Arabic glyphs (Windows Tahoma). The produced *.pdf files and
manifest.json are committed; the tests only read them.

    python apps/classes/tests/fixtures/pdf/_generate_fixtures.py
"""

from __future__ import annotations

import io
import json
import os

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.environ.get('FIXTURE_FONT', r'C:\Windows\Fonts\tahoma.ttf')
pdfmetrics.registerFont(TTFont('Tahoma', FONT_PATH))

ENGLISH = (
    "The quick brown fox jumps over the lazy dog. "
    "Photosynthesis converts light energy into chemical energy stored in glucose."
)
PERSIAN = (
    "زبان فارسی یکی از زبان های کهن جهان است و ادبیات بسیار غنی دارد. "
    "ریاضیات پایه علوم مهندسی محسوب می شود."
)
PAGE1 = "This is the first page about algebra and equations."
PAGE2 = "This is the second page about geometry and triangles."

TABLE = [
    ["Name", "Score", "City"],
    ["Ali", "20", "Tehran"],
    ["Sara", "18", "Shiraz"],
    ["Reza", "15", "Yazd"],
]


def _simple_text_pdf(lines: list[str]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for page in lines if isinstance(lines[0], list) else [lines]:
        c.setFont("Tahoma", 14)
        y = 780
        for line in page:
            c.drawString(56, y, line)
            y -= 32
        c.showPage()
    c.save()
    return buf.getvalue()


def _table_pdf(matrix) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    t = Table(matrix, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("FONTNAME", (0, 0), (-1, -1), "Tahoma"),
        ("FONTSIZE", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    styles = getSampleStyleSheet()
    doc.build([Paragraph("Results table", styles["Heading2"]), Spacer(1, 12), t])
    return buf.getvalue()


def _scanned_pdf(text: str) -> bytes:
    """Image-only page (no text layer) → forces the vision route."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1000, 300), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, 36)
    except Exception:
        font = ImageFont.load_default()
    draw.text((30, 120), text, fill="black", font=font)
    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    img_buf.seek(0)

    from reportlab.lib.utils import ImageReader
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawImage(ImageReader(img_buf), 40, 500, width=500, height=150)
    c.showPage()
    c.save()
    return buf.getvalue()


def _make_png(color: str, w: int, h: int, label: str) -> "io.BytesIO":
    """A non-trivial PNG (gradient + shapes + label) — stands in for a figure.

    The gradient/noise keeps the encoded size realistic (>3KB) so the size
    filter in the extractor treats it as a real figure, not decorative.
    """
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (w, h), color)
    draw = ImageDraw.Draw(img)
    # Diagonal gradient + grid so the PNG does not compress to a few bytes.
    for x in range(0, w, 3):
        shade = (x * 7) % 255
        draw.line([(x, 0), (x, h)], fill=(shade, (shade + 80) % 255, (255 - shade) % 255))
    for yy in range(0, h, 12):
        draw.line([(0, yy), (w, yy)], fill="white")
    try:
        font = ImageFont.truetype(FONT_PATH, 28)
    except Exception:
        font = ImageFont.load_default()
    if label:
        draw.text((10, h // 2 - 14), label, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _images_pdf(text: str, figures, decorative=True) -> bytes:
    """A digital page with body text plus embedded figure images.

    ``figures`` is a list of (color, w, h, label). If ``decorative`` is set, a
    tiny 20x20 icon is also embedded — it must be filtered out by the extractor.
    """
    from reportlab.lib.utils import ImageReader

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Tahoma", 14)
    c.drawString(56, 800, text)
    y = 560
    for (color, w, h, label) in figures:
        png = _make_png(color, w, h, label)
        c.drawImage(ImageReader(png), 56, y, width=w * 0.6, height=h * 0.6)
        y -= int(h * 0.6) + 30
    if decorative:
        tiny = _make_png("gray", 20, 20, "")
        c.drawImage(ImageReader(tiny), 500, 800, width=14, height=14)
    c.showPage()
    c.save()
    return buf.getvalue()


def _blank_pdf() -> bytes:
    """A single empty page — must be detected and skipped (no LLM call)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.showPage()
    c.save()
    return buf.getvalue()


def _scanned_text_pdf(lines, persian: bool = False) -> bytes:
    """Image-only PDF (no text layer) showing correctly-shaped text.

    Persian is reshaped + bidi so the rasterized image reads correctly — this
    simulates a real scanned document for the VISION benchmark.
    """
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.lib.utils import ImageReader

    W, H = 1240, 1754  # ~A4 @ 150dpi
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, 44)
    y = 120
    for line in lines:
        s = line
        if persian:
            import arabic_reshaper
            from bidi.algorithm import get_display
            s = get_display(arabic_reshaper.reshape(line))
            w = draw.textlength(s, font=font)
            draw.text((W - 90 - w, y), s, fill="black", font=font)
        else:
            draw.text((90, y), s, fill="black", font=font)
        y += 90

    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    img_buf.seek(0)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    pw, ph = A4
    c.drawImage(ImageReader(img_buf), 0, 0, width=pw, height=ph, preserveAspectRatio=True, anchor="c")
    c.showPage()
    c.save()
    return buf.getvalue()


def _build_corpus() -> None:
    """Curated REAL-model benchmark corpus with measurable ground truth.

    Kept intentionally small (single-page docs) to bound token spend. Covers:
    English + Persian OCR, a richer Persian paragraph, a table (GFM fidelity),
    and a figure page (deterministic image-extraction count).
    """
    corpus_dir = os.path.join(HERE, "pdf_corpus")
    os.makedirs(corpus_dir, exist_ok=True)

    manifest = {}

    # --- scanned OCR docs (image-only) ---
    scanned = {
        "english_scanned.pdf": {
            "lang": "english",
            "lines": [
                "Newton's second law states that force",
                "equals mass times acceleration.",
            ],
        },
        "persian_scanned.pdf": {
            "lang": "persian",
            "lines": [
                "قانون دوم نیوتن بیان می کند که",
                "نیرو برابر است با جرم ضرب در شتاب",
            ],
        },
        "persian_paragraph.pdf": {
            "lang": "persian",
            "lines": [
                "فتوسنتز فرایندی است که در آن گیاهان",
                "انرژی نور خورشید را به انرژی شیمیایی",
                "تبدیل می کنند و در گلوکز ذخیره می شود.",
            ],
        },
    }
    for name, meta in scanned.items():
        data = _scanned_text_pdf(meta["lines"], persian=(meta["lang"] == "persian"))
        with open(os.path.join(corpus_dir, name), "wb") as fh:
            fh.write(data)
        manifest[name] = {"lang": meta["lang"], "text": " ".join(meta["lines"])}

    # --- table fidelity doc (digital table; vision must emit GFM) ---
    with open(os.path.join(corpus_dir, "table_doc.pdf"), "wb") as fh:
        fh.write(_table_pdf(TABLE))
    manifest["table_doc.pdf"] = {"lang": "english", "table": TABLE}

    # --- figure doc (deterministic image-extraction count) ---
    fig_text = "Two figures are shown below for the experiment."
    with open(os.path.join(corpus_dir, "figure_doc.pdf"), "wb") as fh:
        fh.write(_images_pdf(
            fig_text,
            [("red", 300, 200, "Fig A"), ("navy", 280, 180, "Fig B")],
            decorative=True,
        ))
    manifest["figure_doc.pdf"] = {"lang": "english", "text": fig_text, "expected_images": 2}

    with open(os.path.join(corpus_dir, "corpus_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print("Wrote corpus:", ", ".join(sorted(manifest)))


def _encrypt(data: bytes, password: str) -> bytes:
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(io.BytesIO(data))
    writer = PdfWriter()
    for p in reader.pages:
        writer.add_page(p)
    writer.encrypt(password)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def main() -> None:
    files = {}

    files["english.pdf"] = (_simple_text_pdf([ENGLISH]), {
        "text": ENGLISH, "pages": 1, "route": "text",
    })
    files["persian.pdf"] = (_simple_text_pdf([PERSIAN]), {
        "text": PERSIAN, "pages": 1, "route": "text",
    })
    files["twopage.pdf"] = (_simple_text_pdf([[PAGE1], [PAGE2]]), {
        "text": PAGE1 + "\n" + PAGE2, "pages": 2, "route": "text",
        "page_texts": [PAGE1, PAGE2],
    })
    files["table.pdf"] = (_table_pdf(TABLE), {
        "pages": 1, "route": "text", "table": TABLE,
    })
    files["scanned.pdf"] = (_scanned_pdf("OCR ME PLEASE"), {
        "pages": 1, "route": "vision",
    })
    files["images.pdf"] = (
        _images_pdf(
            "Figure demonstration page.",
            [("red", 300, 200, "Fig A"), ("navy", 280, 180, "Fig B")],
            decorative=True,
        ),
        {"pages": 1, "route": "vision", "embedded_images": 2},
    )
    files["blank.pdf"] = (_blank_pdf(), {"pages": 1, "blank": True})

    manifest = {}
    for name, (data, meta) in files.items():
        with open(os.path.join(HERE, name), "wb") as fh:
            fh.write(data)
        manifest[name] = meta

    enc = _encrypt(files["english.pdf"][0], "secret123")
    with open(os.path.join(HERE, "encrypted.pdf"), "wb") as fh:
        fh.write(enc)
    manifest["encrypted.pdf"] = {"pages": 1, "encrypted": True}

    with open(os.path.join(HERE, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)

    print("Wrote fixtures:", ", ".join(sorted(manifest)))
    _build_corpus()


if __name__ == "__main__":
    main()
