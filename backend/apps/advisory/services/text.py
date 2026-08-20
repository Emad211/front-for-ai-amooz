"""Pure text helpers for the advisory app — no Django imports on purpose.

The catalog is typed by hand in Django admin, in Persian. That guarantees the
same subject gets entered more than once in visually identical but byte-wise
different forms: Arabic ``ي``/``ك`` instead of Persian ``ی``/``ک``, Persian or
Arabic-Indic digits, a stray ZWNJ, a double space, a tashkeel mark pasted in
from a PDF. Uniqueness on the raw ``name`` would happily accept every one of
them and then split one student's subject history across two rows.

So a ``Subject`` carries a derived key alongside its display name, and
uniqueness is enforced on the key.
"""

from __future__ import annotations

import re
import unicodedata

# Arabic → Persian letter folding. This is a *key*, not display text, so the
# folding is deliberately lossy (ة → ه, ئ → ی): two spellings that a Persian
# reader would call the same subject must collapse to the same key.
_LETTER_FOLD = str.maketrans({
    'ك': 'ک',
    'ي': 'ی',
    'ى': 'ی',
    'ئ': 'ی',
    'ۀ': 'ه',
    'ة': 'ه',
    'ﻩ': 'ه',
    'ە': 'ه',
    'أ': 'ا',
    'إ': 'ا',
    'آ': 'ا',
    'ٱ': 'ا',
    'ٲ': 'ا',
    'ٳ': 'ا',
    'ؤ': 'و',
})

_DIGIT_FOLD = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')

# Tashkeel/diacritics, the tatweel elongation, and the zero-width + bidi control
# characters that make two visually identical Persian strings compare unequal.
# Written as escapes on purpose: these are invisible or combining code points, so
# pasting them literally into the source makes the class unreadable and easy to
# corrupt in an editor.
_STRIP_RE = re.compile(
    '['
    'ـ'              # tatweel elongation
    'ً-ٕ'        # tashkeel, maddah, hamza above/below
    'ٰ'              # superscript alef
    '​-‏'        # ZWSP, ZWNJ, ZWJ, LRM, RLM
    '‪-‮'        # bidi embedding / override
    '﻿'              # BOM
    ']'
)

# All whitespace is removed rather than collapsed: «زیست شناسی» and «زیست‌شناسی»
# and «زیستشناسی» are one subject typed three ways, and «ریاضی ۱» / «ریاضی۱» are
# one subject too. Two genuinely different subjects never differ only by spacing.
_WHITESPACE_RE = re.compile(r'\s+')


def normalize_subject_name(raw: object) -> str:
    """Return the duplicate-detection key for a subject name.

    Never longer than the input (it only folds and removes characters), so the
    key column can share the display column's ``max_length``.
    """
    text = '' if raw is None else str(raw)
    # NFKC first: it maps Arabic presentation forms (ﻻ, ﯽ, …) onto their base
    # letters, so the letter folding below sees a single canonical form.
    text = unicodedata.normalize('NFKC', text)
    text = text.translate(_LETTER_FOLD).translate(_DIGIT_FOLD)
    text = _STRIP_RE.sub('', text)
    text = _WHITESPACE_RE.sub('', text)
    # casefold, not lower: the catalog will eventually hold Latin names too
    # (Math, IELTS) and casefold is the aggressive, locale-independent form.
    return text.casefold()


def mask_phone(raw: object) -> str:
    """Return a phone number with its middle hidden: ``0912***6789``.

    Used wherever a phone leaves the server attached to *someone else's* record —
    the student's pending-invite banner shows which number an advisor addressed,
    which is the only way to recognise a wrong-number invite, but the full number
    of a third party is not the student's to read.

    Anything that is not an 11-digit Iranian mobile is masked conservatively
    rather than echoed back, so a malformed value can never leak in full.
    """
    digits = ''.join(ch for ch in str(raw or '') if ch.isascii() and ch.isdigit())
    if len(digits) == 11:
        return f'{digits[:4]}***{digits[-4:]}'
    if len(digits) > 4:
        return f'{digits[:2]}***{digits[-2:]}'
    return '***'
