import pytest

from apps.classes.services.exam_prep_text_quality import (
    contains_presentation_forms,
    has_broken_persian_text,
    native_text_for_model,
    normalize_unicode_text,
)


pytestmark = pytest.mark.unit


def test_presentation_forms_are_detected_and_not_sent_as_native_evidence():
    broken = '؟ﺖﺳا ﺢﻴﺤﺻ ﻪﻨﻳﺰﮔ ماﺪﻛ'

    assert contains_presentation_forms(broken) is True
    assert has_broken_persian_text(broken) is True
    assert native_text_for_model(broken) == ''


def test_nfkc_normalizes_glyph_forms_but_does_not_claim_bidi_repair():
    normalized = normalize_unicode_text('ﺖﺳا')

    assert normalized == 'تسا'
    assert native_text_for_model('ﺖﺳا') == ''


def test_readable_persian_native_text_is_preserved():
    text = 'کدام گزینه درباره زیست فناوری نادرست است؟'

    assert has_broken_persian_text(text) is False
    assert native_text_for_model(text) == text
