"""Measurable text-extraction quality metrics (dependency-free).

Used by the PDF-extraction test suite to produce hard, numeric accuracy
figures: Character Error Rate (CER), Word Error Rate (WER), and table-cell
accuracy. All metrics support Persian/Arabic normalization so cosmetic
differences (Arabic vs Persian yeh/kaf, digit scripts, tatweel, diacritics,
bidi/zero-width marks, whitespace) do not inflate the error.

These are pure functions with no Django/third-party dependency so they can be
imported and asserted on in any context.
"""

from __future__ import annotations

from typing import Sequence

# ---------------------------------------------------------------------------
# Persian / Arabic normalization
# ---------------------------------------------------------------------------

# Character folding map (source -> canonical).
_FOLD = {
    'ي': 'ی',  # Arabic Yeh  ي -> Persian Yeh ی
    'ى': 'ی',  # Alef Maksura ى -> Persian Yeh ی
    'ك': 'ک',  # Arabic Kaf  ك -> Persian Kaf ک
    'ڪ': 'ک',  # Swash Kaf   ڪ -> Persian Kaf ک
    'ة': 'ه',  # Teh Marbuta ة -> Heh ه
    'ـ': '',        # Tatweel/kashida ـ -> removed
}

# Digits: Arabic-Indic (U+0660-0669) and Persian (U+06F0-06F9) -> ASCII.
for _i in range(10):
    _FOLD[chr(0x0660 + _i)] = str(_i)
    _FOLD[chr(0x06F0 + _i)] = str(_i)

# Marks to strip entirely: harakat/diacritics, bidi controls, zero-width.
_STRIP = set(
    [chr(c) for c in range(0x064B, 0x0653)]  # harakat
    + [chr(c) for c in range(0x0610, 0x061B)]  # Arabic marks
    + ['​', '‌', '‍', '‎', '‏', '﻿']  # zwsp/zwnj/zwj/lrm/rlm/bom
    + [chr(c) for c in range(0x202A, 0x202F)]  # bidi embeddings/overrides
    + [chr(c) for c in range(0x2066, 0x206A)]  # bidi isolates
)


def normalize_persian(text: str) -> str:
    """Canonicalize Persian/Arabic text for fair comparison.

    Folds Arabic vs Persian letterforms, unifies digit scripts to ASCII,
    removes tatweel/diacritics/bidi/zero-width marks, and collapses
    whitespace to single spaces.
    """
    if not text:
        return ''
    out = []
    for ch in text:
        if ch in _STRIP:
            continue
        out.append(_FOLD.get(ch, ch))
    # Collapse all whitespace runs to a single space.
    return ' '.join(''.join(out).split())


# ---------------------------------------------------------------------------
# Edit distance (Levenshtein) over any sequence
# ---------------------------------------------------------------------------

def levenshtein(a: Sequence, b: Sequence) -> int:
    """Classic Levenshtein edit distance with a two-row buffer.

    Works on strings (char-level) or lists of tokens (word-level).
    """
    if a == b:
        return 0
    n, m = len(a), len(b)
    if n == 0:
        return m
    if m == 0:
        return n
    # Ensure inner loop is over the shorter sequence for less memory.
    if m < n:
        a, b = b, a
        n, m = m, n

    prev = list(range(m + 1))
    cur = [0] * (m + 1)
    for i in range(1, n + 1):
        cur[0] = i
        ai = a[i - 1]
        for j in range(1, m + 1):
            cost = 0 if ai == b[j - 1] else 1
            cur[j] = min(
                prev[j] + 1,        # deletion
                cur[j - 1] + 1,     # insertion
                prev[j - 1] + cost  # substitution
            )
        prev, cur = cur, prev
    return prev[m]


# ---------------------------------------------------------------------------
# Public metrics
# ---------------------------------------------------------------------------

def cer(reference: str, hypothesis: str, *, normalize: bool = True) -> float:
    """Character Error Rate = edit_distance(chars) / len(reference chars).

    Returns 0.0 when both are empty; 1.0 when only the reference is empty but
    the hypothesis is not (pure insertion).
    """
    ref = normalize_persian(reference) if normalize else reference
    hyp = normalize_persian(hypothesis) if normalize else hypothesis
    if not ref:
        return 0.0 if not hyp else 1.0
    return levenshtein(ref, hyp) / len(ref)


def wer(reference: str, hypothesis: str, *, normalize: bool = True) -> float:
    """Word Error Rate = edit_distance(tokens) / len(reference tokens)."""
    ref = (normalize_persian(reference) if normalize else reference).split()
    hyp = (normalize_persian(hypothesis) if normalize else hypothesis).split()
    if not ref:
        return 0.0 if not hyp else 1.0
    return levenshtein(ref, hyp) / len(ref)


def word_recall(reference: str, hypothesis: str, *, normalize: bool = True) -> float:
    """Fraction of reference words that appear anywhere in the hypothesis.

    Order-insensitive recall — robust when the hypothesis legitimately contains
    extra layout text (captions, infobox, references) around a known reference
    passage, as with real document pages. Returns 1.0 for an empty reference.
    """
    ref = (normalize_persian(reference) if normalize else reference).split()
    if not ref:
        return 1.0
    hyp = set((normalize_persian(hypothesis) if normalize else hypothesis).split())
    found = sum(1 for w in ref if w in hyp)
    return found / len(ref)


def parse_markdown_table(md: str) -> "list[list[str]]":
    """Parse the first GFM table found in ``md`` into a matrix of cell strings.

    Skips the `|---|---|` separator row. Returns ``[]`` if no table is present.
    Used by tests/benchmarks to score table fidelity via ``table_cell_accuracy``.
    """
    rows: list[list[str]] = []
    in_table = False
    for line in (md or "").splitlines():
        s = line.strip()
        if not s.startswith("|"):
            if in_table:
                break  # table ended
            continue
        in_table = True
        cells = [c.strip() for c in s.strip("|").split("|")]
        # Separator row: every cell is only dashes/colons.
        if cells and all(set(c) <= set("-:") and c for c in cells):
            continue
        rows.append(cells)
    return rows


def table_cell_accuracy(
    reference: Sequence[Sequence[str]],
    hypothesis: Sequence[Sequence[str]],
    *,
    normalize: bool = True,
) -> float:
    """Fraction of reference table cells exactly recovered in the hypothesis.

    Compares cell [r][c] against the same position. Missing rows/cells count
    as wrong. Denominator is the total number of reference cells.
    """
    total = sum(len(row) for row in reference)
    if total == 0:
        return 1.0

    def norm(v):
        s = '' if v is None else str(v)
        return normalize_persian(s) if normalize else s.strip()

    correct = 0
    for r, ref_row in enumerate(reference):
        hyp_row = hypothesis[r] if r < len(hypothesis) else []
        for c, ref_cell in enumerate(ref_row):
            hyp_cell = hyp_row[c] if c < len(hyp_row) else None
            if norm(ref_cell) == norm(hyp_cell):
                correct += 1
    return correct / total
