import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


pytestmark = pytest.mark.django_db(transaction=True)


MIGRATE_FROM = [('classes', '0041_exam_prep_v4_source_map_confirmation')]
MIGRATE_TO = [('classes', '0042_exam_prep_v4_virtual_page_order')]


def test_virtual_order_migration_backfills_and_preserves_confirmation():
    executor = MigrationExecutor(connection)
    executor.migrate(MIGRATE_FROM)
    old_apps = executor.loader.project_state(MIGRATE_FROM).apps

    User = old_apps.get_model('accounts', 'User')
    Project = old_apps.get_model('classes', 'ExamProject')
    Document = old_apps.get_model('classes', 'ExamSourceDocument')
    Page = old_apps.get_model('classes', 'ExamSourcePage')
    Segment = old_apps.get_model('classes', 'ExamSourceSegment')

    teacher = User.objects.create(
        username='v4-order-migration-teacher',
        email='v4-order-migration@example.com',
        role='TEACHER',
        is_freelancer=True,
    )
    project = Project.objects.create(
        teacher_id=teacher.id,
        title='Migration fixture',
        status='segmenting',
    )
    document = Document.objects.create(
        project_id=project.id,
        original_name='private.pdf',
        page_count=3,
        status='confirmed',
        classification_revision=2,
        source_map_fingerprint='1' * 64,
        teacher_confirmed_revision=2,
        teacher_confirmed_fingerprint='1' * 64,
        teacher_confirmed_by_id=teacher.id,
    )
    roles = ['cover', 'questions', 'questions']
    for page_number, role in enumerate(roles, start=1):
        Page.objects.create(
            document_id=document.id,
            page_number=page_number,
            predicted_role=role,
            predicted_confidence='0.9000',
        )
    Segment.objects.create(
        document_id=document.id,
        revision=2,
        order=0,
        start_page=1,
        end_page=1,
        role='cover',
        predicted_role='cover',
        predicted_confidence='0.9000',
        teacher_confirmed=True,
        status='confirmed',
    )
    Segment.objects.create(
        document_id=document.id,
        revision=2,
        order=1,
        start_page=2,
        end_page=3,
        role='questions',
        predicted_role='questions',
        predicted_confidence='0.9000',
        teacher_confirmed=True,
        status='confirmed',
    )

    executor = MigrationExecutor(connection)
    executor.migrate(MIGRATE_TO)
    apps = executor.loader.project_state(MIGRATE_TO).apps

    NewDocument = apps.get_model('classes', 'ExamSourceDocument')
    NewPage = apps.get_model('classes', 'ExamSourcePage')
    NewSegment = apps.get_model('classes', 'ExamSourceSegment')

    migrated_document = NewDocument.objects.get(id=document.id)
    pages = list(
        NewPage.objects.filter(document_id=document.id).order_by('page_number')
    )
    segments = list(
        NewSegment.objects.filter(
            document_id=document.id,
            revision=2,
        ).order_by('order')
    )

    assert [page.display_order for page in pages] == [1, 2, 3]
    assert len(migrated_document.source_map_fingerprint) == 64
    assert migrated_document.source_map_fingerprint != '1' * 64
    assert (
        migrated_document.teacher_confirmed_fingerprint
        == migrated_document.source_map_fingerprint
    )
    assert migrated_document.teacher_confirmed_revision == 2
    assert [segment.metadata['pageNumbers'] for segment in segments] == [
        [1],
        [2, 3],
    ]
    assert [segment.metadata['displayOrderStart'] for segment in segments] == [1, 2]
    assert [segment.metadata['displayOrderEnd'] for segment in segments] == [1, 3]
    assert all(
        segment.fingerprint == migrated_document.source_map_fingerprint
        for segment in segments
    )
