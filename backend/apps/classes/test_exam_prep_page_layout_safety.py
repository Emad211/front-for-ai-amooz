import io

from PIL import Image, ImageDraw

from apps.classes.services.exam_prep_page_layout import classify_exam_page


def _sparse_figure_page() -> bytes:
    image = Image.new("RGB", (800, 1100), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((220, 260, 580, 760), outline="black", width=8)
    draw.line((260, 680, 540, 340), fill="black", width=6)
    output = io.BytesIO()
    image.save(output, format="PNG")
    image.close()
    return output.getvalue()


def test_sparse_visual_page_is_not_silently_skipped():
    decision = classify_exam_page(
        image=_sparse_figure_page(),
        native_text="شکل مربوط به سؤال قبل",
    )
    assert decision.content_class == "content"
    assert decision.layout in {"single", "uncertain"}
