"""Seed the official konkur syllabus tree (درخت بودجه‌بندی) — wave 7 (2026-08-31).

Creates ``SyllabusChapter``/``SyllabusTopic`` rows for the four core konkur
subjects (ریاضی، فیزیک، شیمی، زیست‌شناسی) with their real chapter/topic
structure and approximate konkur question counts (weights are the publicly
known per-section budgets, rounded — they guide allocation, not scoring).

Which Subject rows get a tree: the konkur band is grades 10–12, and a tree
attaches to every catalog row of its subject family in that band — including
major-NULL general rows, because فیزیک ۱/۲/۳ and شیمی ۱/۲/۳ are general
subjects in the national curriculum. The merged ریاضی tree (its chapters ARE
the math-major track: حسابان، جبر و احتمال، هندسه، گسسته) attaches to the
whole math family — ریاضی، حسابان، هندسه، آمار و احتمال، ریاضیات گسسته —
but NOT to the humanities «ریاضی و آمار» track, whose konkur syllabus is a
different, lighter one.

Idempotent by natural keys: chapters key on (subject, title), topics on
(chapter, title). A re-run creates nothing new and never clobbers an admin's
reorder or re-weight — the same contract ``seed_advisory_subjects`` gives the
subject catalog.

Run it with::

    docker compose run --rm backend python manage.py seed_syllabus
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.advisory.models import Subject, SyllabusChapter, SyllabusTopic
from apps.advisory.services.text import normalize_subject_name

# Konkur covers the high-school band; a gradeless row is dead catalog data
# (see the Subject model) and derives for nobody, so it seeds nothing either.
KONKUR_GRADES = ('10', '11', '12')

# (chapter title, [(topic title, approximate konkur question count), …]).
# Chapter/topic names follow the national curriculum textbooks; weights are
# the typical konkur per-section budgets, rounded.
_MATH_TREE = (
    ('حسابان', (
        ('توابع', 4),
        ('حد و پیوستگی', 2),
        ('مشتق', 2),
        ('کاربرد مشتق', 2),
    )),
    ('جبر و احتمال', (
        ('ماتریس و دترمینان', 3),
        ('احتمال', 2),
        ('آمار', 2),
    )),
    ('هندسه', (
        ('هندسه تحلیلی', 2),
        ('مثلثات', 2),
        ('هندسه برداری', 1),
    )),
    ('ریاضیات گسسته', (
        ('لگاریتم', 2),
        ('دنباله‌های عددی', 2),
        ('استقرا و نماد سیگما', 1),
    )),
)

_PHYSICS_TREE = (
    ('حرکت‌شناسی', (
        ('حرکت راست‌خطی', 2),
        ('حرکت پرتابی', 1),
        ('حرکت دایره‌ای', 1),
    )),
    ('دینامیک', (
        ('قوانین نیوتن', 2),
        ('اصطکاک و تعادل', 1),
        ('نیروی گرانشی', 1),
    )),
    ('کار و انرژی', (
        ('کار و توان', 1),
        ('انرژی جنبشی و پتانسیل', 2),
        ('بقای انرژی', 1),
    )),
    ('نوسان و موج', (
        ('حرکت هماهنگ ساده', 2),
        ('موج و صوت', 2),
    )),
    ('الکتریسیته', (
        ('میدان الکتریکی', 2),
        ('پتانسیل الکتریکی', 1),
        ('مدارهای جریان مستقیم', 2),
        ('خازن', 1),
    )),
    ('مغناطیس', (
        ('میدان مغناطیسی', 1),
        ('نیروی مغناطیسی', 1),
        ('القای الکترومغناطیسی', 1),
    )),
    ('اپتیک', (
        ('بازتاب و آینه‌ها', 1),
        ('شکست و عدسی‌ها', 2),
        ('تداخل و پراش', 1),
    )),
    ('فیزیک اتمی', (
        ('مدل بور', 1),
        ('اثر فوتوالکتریک', 1),
        ('هسته و رادیواکتیویته', 1),
    )),
)

_CHEMISTRY_TREE = (
    ('استوکیومتری', (
        ('مفهوم مول', 1),
        ('معادلات و محاسبات شیمیایی', 2),
        ('غلظت محلول‌ها', 1),
    )),
    ('ساختار اتم', (
        ('مدل‌های اتمی', 1),
        ('آرایش الکترونی', 2),
        ('جدول تناوبی', 1),
    )),
    ('پیوند شیمیایی', (
        ('پیوند یونی و کووالانسی', 2),
        ('شکل مولکولی', 1),
        ('نیروهای بین‌مولکولی', 1),
    )),
    ('ترمودینامیک شیمیایی', (
        ('آنتالپی و گرمای واکنش', 1),
        ('قانون هس', 1),
        ('کالریمتری', 1),
    )),
    ('سینتیک شیمیایی', (
        ('سرعت واکنش', 1),
        ('نظریه برخورد و کاتالیزور', 1),
        ('عوامل مؤثر بر سرعت', 1),
    )),
    ('تعادل شیمیایی', (
        ('ثابت تعادل', 2),
        ('اصل لوشاتلیه', 1),
    )),
    ('اسید و باز', (
        ('نظریه‌های اسید و باز', 1),
        ('pH و محاسبات', 2),
        ('تیتراسیون', 1),
    )),
    ('الکتروشیمی', (
        ('سلول گالوانی', 2),
        ('الکترولیز', 1),
        ('خوردگی', 1),
    )),
)

_BIOLOGY_TREE = (
    ('سلول', (
        ('مولکول‌های زیستی', 2),
        ('غشای سلولی و انتقال مواد', 2),
        ('اندامک‌های سلولی', 2),
        ('متابولیسم سلولی', 2),
    )),
    ('بافت‌شناسی', (
        ('بافت‌های پوششی و پیوندی', 1),
        ('بافت عضلانی و عصبی', 1),
        ('بافت‌های گیاهی', 1),
    )),
    ('شناخت گیاهان', (
        ('ساختار ریشه و ساقه', 2),
        ('برگ و فتوسنتز', 2),
        ('تولیدمثل گیاهی', 1),
        ('رشد و تنظیم گیاهی', 1),
    )),
    ('شناخت جانوران', (
        ('دستگاه گوارش', 1),
        ('تنفس و گردش خون', 2),
        ('دفع و تنظیم اسمزی', 1),
        ('سیستم عصبی و هورمونی', 2),
        ('دستگاه ایمنی', 1),
    )),
    ('ژنتیک', (
        ('تقسیم سلولی', 2),
        ('قوانین مندل', 2),
        ('DNA و همانندسازی', 2),
        ('رونویسی و ترجمه', 2),
        ('جهش و بیوتکنولوژی', 1),
    )),
    ('تکامل', (
        ('شواهد تکامل', 1),
        ('نیروهای تکاملی', 1),
        ('گونه‌زایی', 1),
    )),
    ('بوم‌شناسی', (
        ('اکوسیستم و چرخه‌های مادی', 1),
        ('جمعیت و جامعه', 1),
        ('تنوع زیستی و حفاظت', 1),
    )),
)


def _norm_keys(*keys: str) -> tuple[str, ...]:
    return tuple(normalize_subject_name(key) for key in keys)


# One entry per konkur subject family. ``keys``/``excludes`` are matched as
# normalized-name prefixes; ``majors`` includes None wherever the family's
# catalog rows are general (shared across majors) rather than track-specific.
KONKUR_TREES = (
    {
        'name': 'ریاضی',
        'keys': _norm_keys('ریاضی', 'حسابان', 'هندسه', 'گسسته', 'آمار'),
        'excludes': _norm_keys('ریاضی و آمار'),
        'majors': (None, 'math', 'science'),
        'chapters': _MATH_TREE,
    },
    {
        'name': 'فیزیک',
        'keys': _norm_keys('فیزیک'),
        'excludes': (),
        'majors': (None, 'math', 'science'),
        'chapters': _PHYSICS_TREE,
    },
    {
        'name': 'شیمی',
        'keys': _norm_keys('شیمی'),
        'excludes': (),
        'majors': (None, 'math', 'science'),
        'chapters': _CHEMISTRY_TREE,
    },
    {
        'name': 'زیست‌شناسی',
        'keys': _norm_keys('زیست'),
        'excludes': (),
        'majors': (None, 'science'),
        'chapters': _BIOLOGY_TREE,
    },
)


def _tree_for(subject: Subject):
    """The konkur tree this subject row belongs to, or ``None``.

    Matching rides the catalog's own normalized key, so «فیزیک ۱»، «فیزیک۱»
    and «فیزیك ۱» (Arabic ك) all find the physics tree.
    """
    for tree in KONKUR_TREES:
        if subject.major not in tree['majors']:
            continue
        if tree['excludes'] and subject.normalized_name.startswith(tree['excludes']):
            continue
        if subject.normalized_name.startswith(tree['keys']):
            return tree
    return None


class Command(BaseCommand):
    help = (
        'Seed the official konkur syllabus tree (SyllabusChapter/SyllabusTopic) '
        'for the core konkur subjects (ریاضی، فیزیک، شیمی، زیست‌شناسی) in grades '
        '10-12. Idempotent; safe to re-run.'
    )

    @transaction.atomic
    def handle(self, *args, **options):
        subjects = Subject.objects.filter(grade__in=KONKUR_GRADES).order_by('id')

        matched = 0
        chapters_created = chapters_existing = 0
        topics_created = topics_existing = 0

        for subject in subjects:
            tree = _tree_for(subject)
            if tree is None:
                continue
            matched += 1
            for chapter_order, (chapter_title, topics) in enumerate(tree['chapters'], start=1):
                _chapter, created = SyllabusChapter.objects.get_or_create(
                    subject=subject,
                    title=chapter_title,
                    defaults={'order': chapter_order},
                )
                if created:
                    chapters_created += 1
                else:
                    chapters_existing += 1

                for topic_order, (topic_title, weight) in enumerate(topics, start=1):
                    _topic, created = SyllabusTopic.objects.get_or_create(
                        chapter=_chapter,
                        title=topic_title,
                        defaults={'order': topic_order, 'konkur_weight': weight},
                    )
                    if created:
                        topics_created += 1
                    else:
                        topics_existing += 1

        if matched == 0:
            self.stdout.write(self.style.NOTICE(
                'No konkur subjects (ریاضی/فیزیک/شیمی/زیست‌شناسی in grades 10-12) '
                'found in the catalog — nothing to seed. Run '
                'seed_advisory_subjects first.'
            ))
            return

        self.stdout.write(self.style.SUCCESS(
            f'Done. {matched} subjects seeded '
            f'({chapters_created} chapters created, {chapters_existing} already '
            f'present; {topics_created} topics created, {topics_existing} '
            f'already present).'
        ))
