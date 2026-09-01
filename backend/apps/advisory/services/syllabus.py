"""Read door for the official syllabus tree (درخت بودجه‌بندی) — wave 7 (2026-08-31).

The tree is national catalog data — chapters and topics of the konkur syllabus,
seeded platform-wide by ``seed_syllabus`` and hanging off ``Subject`` exactly
like the subject catalog itself. It carries no student data and no engagement
tenancy, which is why its models sit in ``test_import_boundaries``' unscoped
set beside ``Subject`` and this module shapes the browse payload in one place:
the response contract (camelCase keys, ordered chapters, ordered topics) is
written once here rather than re-derived by every future reader.

The write counterpart — linking a ``TopicProgress`` row to a tree leaf — lives
in ``services/topics.py``, the coverage write door, not here.
"""

from __future__ import annotations

from django.db.models import Prefetch

from ..models import SyllabusChapter, SyllabusTopic


def list_syllabus(subject) -> dict:
    """The shaped browse payload for one subject's tree.

    Chapters come out ordered (``order`` then ``title``), each with its topics
    ordered the same way. An unseeded subject answers an empty ``chapters``
    list, not an error — «هیچ فصلی ثبت نشده» is a state the picker renders,
    while a missing subject is the view's 404 to answer.
    """
    chapters = (
        SyllabusChapter.objects.filter(subject=subject)
        .prefetch_related(
            Prefetch(
                'syllabus_topics',
                queryset=SyllabusTopic.objects.order_by('order', 'title'),
            )
        )
        .order_by('order', 'title')
    )
    return {
        'subject': {'id': subject.id, 'name': subject.name},
        'chapters': [
            {
                'id': chapter.id,
                'title': chapter.title,
                'order': chapter.order,
                'topics': [
                    {
                        'id': topic.id,
                        'title': topic.title,
                        'order': topic.order,
                        'konkurWeight': topic.konkur_weight,
                    }
                    for topic in chapter.syllabus_topics.all()
                ],
            }
            for chapter in chapters
        ],
    }
