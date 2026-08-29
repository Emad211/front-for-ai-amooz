"""The write door for exam scores and exam analyses (restart steps 5 + 6).

``StudyExamScore`` / ``StudyExamAnalysis`` (+ their child rows) are
tenancy-bearing, so every mutation goes through this one module after the view
has resolved ownership via ``scope.advisor_engagement`` — exactly like
``intake.py`` for the intake form. The exact Persian validation messages are
this module's contract; serializers stay shape-only so the wire errors never
drift from here.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db.models import F
from django.db import transaction

from ..models import (
    ADVISOR_RATING_CHOICES,
    EXAM_KIND_CHOICES,
    StudyExamAnalysis,
    StudyExamAnalysisNote,
    StudyExamAnalysisRow,
    StudyExamScore,
    Subject,
)

# The paper table (PDF ص۴۲) is one month's worth of exams; the plan grants a
# per-engagement ceiling of 40 rows. A service rule, not a constraint — a DB
# check cannot count sibling rows.
MAX_EXAM_SCORES = 40

PERCENT_MIN = Decimal('0')
PERCENT_MAX = Decimal('100')

# Restart step 6 (PDF ص۴۳-۴۴ answer sheet): question numbers are 1..300.
MAX_ANALYSIS_QUESTION_NUMBER = 300

MSG_SCORE_CAP = 'سقف ثبت نمرات پر شده است.'
MSG_PERCENT = 'درصد باید بین ۰ تا ۱۰۰ باشد.'
MSG_EXAM_KIND = 'نوع آزمون نامعتبر است.'
MSG_RATING = 'ارزیابی نامعتبر است.'
MSG_SUBJECT = 'درس انتخابی معتبر نیست.'
MSG_TITLE = 'عنوان آزمون الزامی است.'
MSG_TARA = 'تراز نامعتبر است.'

MSG_GRADE_BAND = 'بازهٔ پایه نامعتبر است.'
MSG_DOUBTFUL = 'آمار سؤالات شک‌دار نامعتبر است.'
MSG_ROW_COUNTS = 'آمار ردیف درس نامعتبر است.'
MSG_QUESTION_NUMBER = 'شمارهٔ سؤال باید بین ۱ تا ۳۰۰ باشد.'
MSG_ROW_SUBJECT = 'نام درسِ ردیف الزامی است.'

_EXAM_KIND_CODES = {code for code, _label in EXAM_KIND_CHOICES}
_RATING_CODES = {code for code, _label in ADVISOR_RATING_CHOICES}
_GRADE_BAND_CODES = {'G10', 'G11', 'G12S1', 'G12S2'}


class ExamRecordError(Exception):
    """400-family validation error; ``str(exc)`` is the Persian wire message."""


def _fail(message: str) -> None:
    raise ExamRecordError(message)


def list_exam_scores(engagement):
    """Every score row of this engagement, newest exam first.

    Takes a resolved engagement (the caller proved ownership via
    ``scope.advisor_engagement`` or ``student_active_engagement``), so it does
    no scoping of its own.
    """
    return (
        StudyExamScore.objects.filter(engagement=engagement)
        .select_related('subject')
        .order_by('-exam_date', '-id')
    )


def get_exam_score(engagement, score_id) -> StudyExamScore | None:
    """One score row of *this* engagement, or ``None`` — never another's."""
    return (
        StudyExamScore.objects.filter(engagement=engagement, pk=score_id)
        .select_related('subject')
        .first()
    )


def _clean_score_fields(payload: dict) -> dict:
    """Validate a (possibly partial) score payload into storable column values.

    Only keys present in ``payload`` are touched — that is what makes PATCH
    partial: an absent key means «unchanged», a present key overwrites (even
    back to null/empty). Values arrive serializer-parsed, so dates are ``date``
    objects and percents are numeric; this pass owns the domain rules and their
    pinned Persian messages.
    """
    cleaned: dict = {}

    if 'title' in payload:
        title = (payload['title'] or '').strip()
        if not title:
            _fail(MSG_TITLE)
        cleaned['title'] = title

    if 'exam_kind' in payload:
        kind = payload['exam_kind']
        if kind not in _EXAM_KIND_CODES:
            _fail(MSG_EXAM_KIND)
        cleaned['exam_kind'] = kind

    if 'exam_date' in payload:
        # Only reachable as an explicit null on PATCH; POST requires the field
        # at the serializer level.
        if payload['exam_date'] is None:
            _fail('تاریخ آزمون الزامی است.')
        cleaned['exam_date'] = payload['exam_date']

    if 'score_percent' in payload:
        raw = payload['score_percent']
        try:
            percent = Decimal(str(raw))
        except (InvalidOperation, TypeError, ValueError):
            _fail(MSG_PERCENT)
        if not (PERCENT_MIN <= percent <= PERCENT_MAX):
            _fail(MSG_PERCENT)
        cleaned['score_percent'] = percent.quantize(Decimal('0.01'))

    if 'tara' in payload:
        tara = payload['tara']
        # ``bool`` is an ``int`` subclass in Python; True/False are not a تراز.
        if tara is not None and (isinstance(tara, bool) or not isinstance(tara, int)):
            _fail(MSG_TARA)
        cleaned['tara'] = tara

    if 'advisor_rating' in payload:
        rating = payload['advisor_rating']
        if rating in ('', None):
            rating = None
        elif rating not in _RATING_CODES:
            _fail(MSG_RATING)
        cleaned['advisor_rating'] = rating

    if 'advisor_note' in payload:
        cleaned['advisor_note'] = payload['advisor_note'] or ''

    if 'subject_id' in payload:
        subject_id = payload['subject_id']
        if subject_id is None:
            cleaned['subject'] = None
        else:
            # Existence only: the wire pins «nonexistent ⇒ 400», nothing about
            # catalog visibility — an advisor may link any real catalog row.
            subject = Subject.objects.filter(pk=subject_id).first()
            if subject is None:
                _fail(MSG_SUBJECT)
            cleaned['subject'] = subject

    return cleaned


def create_exam_score(engagement, payload: dict, actor) -> StudyExamScore:
    """Create one score row under the engagement's 40-row ceiling."""
    cleaned = _clean_score_fields(payload)
    if engagement.exam_scores.count() >= MAX_EXAM_SCORES:
        _fail(MSG_SCORE_CAP)
    return StudyExamScore.objects.create(
        engagement=engagement,
        created_by=actor if getattr(actor, 'pk', None) else None,
        **cleaned,
    )


def update_exam_score(score: StudyExamScore, payload: dict) -> StudyExamScore:
    """Apply only the provided keys of a PATCH body onto a stored row."""
    cleaned = _clean_score_fields(payload)
    for field, value in cleaned.items():
        setattr(score, field, value)
    score.save()
    return score


def delete_exam_score(score: StudyExamScore) -> None:
    """Remove one score row outright — a correction, not history to keep."""
    score.delete()


# ── step 6: exam analyses ────────────────────────────────────────────────────

def list_exam_analyses(engagement):
    """Every analysis of this engagement, newest exam first, nulls last.

    ``nulls_last`` is explicit because PostgreSQL's DESC default is NULLS
    FIRST — and a never-dated analysis is the least interesting row on both
    readers, not the first one.
    """
    return (
        StudyExamAnalysis.objects.filter(engagement=engagement)
        .prefetch_related('rows', 'notes')
        .order_by(F('exam_date').desc(nulls_last=True), '-id')
    )


def get_analysis(engagement, analysis_id) -> StudyExamAnalysis | None:
    """One analysis of *this* engagement, or ``None`` — never another's."""
    return (
        StudyExamAnalysis.objects.filter(engagement=engagement, pk=analysis_id)
        .prefetch_related('rows', 'notes')
        .first()
    )


def _clean_optional_int(value, message: str):
    """``None | int`` with bools rejected — shared by every nullable metric."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(message)
    return value


def _clean_percent(value) -> Decimal | None:
    if value is None:
        return None
    try:
        percent = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        _fail(MSG_PERCENT)
    if not (PERCENT_MIN <= percent <= PERCENT_MAX):
        _fail(MSG_PERCENT)
    return percent.quantize(Decimal('0.01'))


def _clean_rows(rows) -> list[dict]:
    """Validate the per-subject rows of one analysis payload."""
    cleaned = []
    for row in rows:
        counts = {}
        for key in (
            'wrong_count',
            'skipped_count',
            'doubtful_total',
            'doubtful_wrong',
            'doubtful_skipped',
            'doubtful_correct',
        ):
            value = row.get(key)
            if value is None:
                value = 0
            # Defensive beyond the wire: the columns are PositiveIntegerField,
            # so letting a negative through would surface as a 500.
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                _fail(MSG_ROW_COUNTS)
            counts[key] = value

        # Each doubtful sub-counter can never exceed what was doubted at all;
        # anything else would make the کارنامه self-contradictory.
        total = counts['doubtful_total']
        if any(
            counts[key] > total
            for key in ('doubtful_wrong', 'doubtful_skipped', 'doubtful_correct')
        ):
            _fail(MSG_DOUBTFUL)

        subject_name = (row.get('subject_name') or '').strip()
        if not subject_name:
            _fail(MSG_ROW_SUBJECT)

        cleaned.append({
            'subject_name': subject_name,
            **counts,
            'cause_note': row.get('cause_note') or '',
        })
    return cleaned


def _clean_notes(notes) -> list[dict]:
    """Validate the per-question notes; duplicates are reported by number."""
    seen: set[int] = set()
    cleaned = []
    for note in notes:
        number = note.get('question_number')
        if (
            isinstance(number, bool)
            or not isinstance(number, int)
            or not (1 <= number <= MAX_ANALYSIS_QUESTION_NUMBER)
        ):
            _fail(MSG_QUESTION_NUMBER)
        if number in seen:
            _fail(f'برای سؤال {number} دو یادداشت ثبت شده است.')
        seen.add(number)

        subject_name = (note.get('subject_name') or '').strip()
        if not subject_name:
            _fail(MSG_ROW_SUBJECT)

        cleaned.append({
            'question_number': number,
            'subject_name': subject_name,
            'note': note.get('note') or '',
        })
    cleaned.sort(key=lambda item: item['question_number'])
    return cleaned


def _clean_analysis_fields(payload: dict) -> dict:
    """Validate one full analysis payload into storable scalars + children."""
    grade_band = payload.get('grade_band')
    if grade_band in ('', None):
        grade_band = None
    elif grade_band not in _GRADE_BAND_CODES:
        _fail(MSG_GRADE_BAND)

    exam_number = payload.get('exam_number')
    if exam_number is not None:
        # Defensive beyond the wire: PositiveSmallIntegerField would 500 on a
        # negative, so it is caught here as an actionable 400 instead.
        if (
            isinstance(exam_number, bool)
            or not isinstance(exam_number, int)
            or exam_number < 0
        ):
            _fail('شمارهٔ آزمون نامعتبر است.')

    return {
        'scalars': {
            'exam_number': exam_number,
            'exam_date': payload.get('exam_date'),
            'grade_band': grade_band,
            'total_tara': _clean_optional_int(payload.get('total_tara'), MSG_TARA),
            'national_rank': _clean_optional_int(
                payload.get('national_rank'), 'رتبهٔ کشوری نامعتبر است.',
            ),
            'region_rank': _clean_optional_int(
                payload.get('region_rank'), 'رتبهٔ منطقه نامعتبر است.',
            ),
            'city_rank': _clean_optional_int(
                payload.get('city_rank'), 'رتبهٔ شهر نامعتبر است.',
            ),
            'highest_percent': _clean_percent(payload.get('highest_percent')),
            'lowest_percent': _clean_percent(payload.get('lowest_percent')),
            'tara_delta': _clean_optional_int(
                payload.get('tara_delta'), 'تغییر تراز نامعتبر است.',
            ),
            'advisor_report': payload.get('advisor_report') or '',
        },
        'rows': _clean_rows(payload.get('rows') or []),
        'notes': _clean_notes(payload.get('notes') or []),
    }


def _rebuild_children(analysis: StudyExamAnalysis, rows: list[dict], notes: list[dict]) -> None:
    """Make the stored rows/notes equal exactly what was sent (set-replace).

    Hard delete + bulk re-create inside the caller's transaction: like the
    intake timetable, these tables describe the *current* reading of one exam,
    so there is no row history worth preserving.
    """
    StudyExamAnalysisRow.objects.filter(analysis=analysis).delete()
    StudyExamAnalysisNote.objects.filter(analysis=analysis).delete()
    StudyExamAnalysisRow.objects.bulk_create([
        StudyExamAnalysisRow(analysis=analysis, **row) for row in rows
    ])
    StudyExamAnalysisNote.objects.bulk_create([
        StudyExamAnalysisNote(analysis=analysis, **note) for note in notes
    ])


def create_analysis(engagement, payload: dict) -> StudyExamAnalysis:
    """Create one analysis together with its full rows+notes payload."""
    cleaned = _clean_analysis_fields(payload)
    with transaction.atomic():
        analysis = StudyExamAnalysis.objects.create(
            engagement=engagement, **cleaned['scalars'],
        )
        _rebuild_children(analysis, cleaned['rows'], cleaned['notes'])
    return get_analysis(engagement, analysis.pk)


def replace_analysis(analysis: StudyExamAnalysis, payload: dict) -> StudyExamAnalysis:
    """Set-replace the whole analysis — scalars overwritten, rows+notes rebuilt.

    An omitted/empty ``rows``/``notes`` clears them: the endpoint replaces the
    document wholesale, like every advisory PUT. One transaction covers scalar
    save and child rebuild so a failed validation can never leave half a
    document behind.
    """
    cleaned = _clean_analysis_fields(payload)
    with transaction.atomic():
        for field, value in cleaned['scalars'].items():
            setattr(analysis, field, value)
        analysis.save()
        _rebuild_children(analysis, cleaned['rows'], cleaned['notes'])
    return get_analysis(analysis.engagement, analysis.pk)


def delete_analysis(analysis: StudyExamAnalysis) -> None:
    """Remove one analysis; its rows and notes go with it (CASCADE)."""
    analysis.delete()
