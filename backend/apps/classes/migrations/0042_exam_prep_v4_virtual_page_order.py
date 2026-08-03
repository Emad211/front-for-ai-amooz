import hashlib
import json

from django.db import migrations, models
from django.db.models import F, Q


SOURCE_MAP_SCHEMA_VERSION = 2


def _fingerprint(page_map, page_count):
    payload = {
        'schemaVersion': SOURCE_MAP_SCHEMA_VERSION,
        'pageCount': page_count,
        'pages': page_map,
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
        ).encode('utf-8')
    ).hexdigest()


def _groups(pages):
    groups = []
    for page in pages:
        role = page.teacher_role or page.predicted_role
        if not groups or groups[-1][0] != role:
            groups.append((role, [page]))
        else:
            groups[-1][1].append(page)
    return groups


def backfill_virtual_order_and_fingerprints(apps, schema_editor):
    Page = apps.get_model('classes', 'ExamSourcePage')
    Document = apps.get_model('classes', 'ExamSourceDocument')
    Segment = apps.get_model('classes', 'ExamSourceSegment')

    Page.objects.update(display_order=F('page_number'))

    for document in Document.objects.iterator(chunk_size=200):
        pages = list(
            Page.objects.filter(document_id=document.id)
            .order_by('display_order', 'page_number')
        )
        if not pages or len(pages) != document.page_count:
            continue

        page_numbers = sorted(page.page_number for page in pages)
        if page_numbers != list(range(1, document.page_count + 1)):
            continue

        page_map = [
            {
                'pageNumber': page.page_number,
                'displayOrder': page.display_order,
                'role': page.teacher_role or page.predicted_role,
                'orientation': page.orientation,
            }
            for page in pages
        ]
        fingerprint = _fingerprint(page_map, document.page_count)

        update_fields = ['source_map_fingerprint']
        document.source_map_fingerprint = fingerprint
        if (
            document.teacher_confirmed_revision == document.classification_revision
            and document.teacher_confirmed_fingerprint
        ):
            document.teacher_confirmed_fingerprint = fingerprint
            update_fields.append('teacher_confirmed_fingerprint')
        document.save(update_fields=update_fields)

        current_segments = {
            segment.order: segment
            for segment in Segment.objects.filter(
                document_id=document.id,
                revision=document.classification_revision,
            )
        }
        for order, (role, group) in enumerate(_groups(pages)):
            segment = current_segments.get(order)
            if segment is None:
                continue
            page_sequence = [page.page_number for page in group]
            metadata = dict(segment.metadata or {})
            metadata.update(
                {
                    'pageNumbers': page_sequence,
                    'displayOrderStart': group[0].display_order,
                    'displayOrderEnd': group[-1].display_order,
                    'physicalContiguous': page_sequence
                    == list(range(min(page_sequence), max(page_sequence) + 1)),
                }
            )
            segment.start_page = group[0].page_number
            segment.end_page = group[-1].page_number
            segment.role = role
            segment.fingerprint = fingerprint
            segment.metadata = metadata
            segment.save(
                update_fields=[
                    'start_page',
                    'end_page',
                    'role',
                    'fingerprint',
                    'metadata',
                    'updated_at',
                ]
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('classes', '0041_exam_prep_v4_source_map_confirmation'),
    ]

    operations = [
        migrations.AddField(
            model_name='examsourcepage',
            name='display_order',
            field=models.PositiveIntegerField(null=True),
        ),
        migrations.RunPython(
            backfill_virtual_order_and_fingerprints,
            noop_reverse,
        ),
        migrations.AlterField(
            model_name='examsourcepage',
            name='display_order',
            field=models.PositiveIntegerField(),
        ),
        migrations.AddConstraint(
            model_name='examsourcepage',
            constraint=models.UniqueConstraint(
                fields=('document', 'display_order'),
                name='uniq_exam_v4_document_order',
            ),
        ),
        migrations.AddConstraint(
            model_name='examsourcepage',
            constraint=models.CheckConstraint(
                condition=Q(display_order__gte=1),
                name='exam_v4_display_order_gte_1',
            ),
        ),
        migrations.AddIndex(
            model_name='examsourcepage',
            index=models.Index(
                fields=['document', 'display_order'],
                name='exam_v4_page_order_idx',
            ),
        ),
        migrations.RemoveConstraint(
            model_name='examsourcesegment',
            name='exam_v4_segment_page_range',
        ),
        migrations.AddConstraint(
            model_name='examsourcesegment',
            constraint=models.CheckConstraint(
                condition=Q(end_page__gte=1),
                name='exam_v4_segment_end_gte_1',
            ),
        ),
    ]
