from django.db import migrations


BATCH_SIZE = 500


def backfill_asset_ids(apps, schema_editor):  # noqa: ARG001
    Attempt = apps.get_model('classes', 'StudentExerciseAttempt')
    Source = apps.get_model('classes', 'StudentExerciseAnswerSource')
    Asset = apps.get_model('classes', 'StudentExerciseAnswerAsset')

    cursor = 0
    while True:
        attempts = list(
            Attempt.objects.filter(id__gt=cursor)
            .only('id', 'submission_id', 'grader_metadata')
            .order_by('id')[:BATCH_SIZE]
        )
        if not attempts:
            break
        cursor = attempts[-1].id
        expected_by_source = {}
        for attempt in attempts:
            refs = (
                attempt.grader_metadata.get('answerSources', [])
                if isinstance(attempt.grader_metadata, dict) else []
            )
            for ref in refs:
                if (
                    isinstance(ref, dict)
                    and 'assetIds' not in ref
                    and isinstance(ref.get('sourceId'), int)
                    and isinstance(ref.get('revision'), int)
                ):
                    expected_by_source.setdefault(ref['sourceId'], set()).add(
                        (attempt.submission_id, ref['revision'])
                    )
        sources = Source.objects.filter(id__in=expected_by_source).in_bulk()
        eligible_ids = {
            source_id for source_id, source in sources.items()
            if (source.submission_id, source.revision) in expected_by_source[source_id]
        }
        assets_by_source = {}
        for source_id, asset_id in Asset.objects.filter(
            source_id__in=eligible_ids, is_active=True,
        ).order_by('source_id', 'order', 'id').values_list('source_id', 'id'):
            assets_by_source.setdefault(source_id, []).append(asset_id)

        changed = []
        for attempt in attempts:
            metadata = attempt.grader_metadata
            if not isinstance(metadata, dict):
                continue
            refs = metadata.get('answerSources')
            if not isinstance(refs, list):
                continue
            next_refs = []
            did_change = False
            for ref in refs:
                next_ref = dict(ref) if isinstance(ref, dict) else ref
                if isinstance(next_ref, dict) and 'assetIds' not in next_ref:
                    source = sources.get(next_ref.get('sourceId'))
                    asset_ids = assets_by_source.get(next_ref.get('sourceId'))
                    if (
                        source is not None
                        and source.submission_id == attempt.submission_id
                        and source.revision == next_ref.get('revision')
                        and asset_ids
                    ):
                        next_ref['assetIds'] = asset_ids
                        did_change = True
                next_refs.append(next_ref)
            if did_change:
                attempt.grader_metadata = {**metadata, 'answerSources': next_refs}
                changed.append(attempt)
        if changed:
            Attempt.objects.bulk_update(changed, ['grader_metadata'], batch_size=BATCH_SIZE)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('classes', '0035_answer_asset_deactivated_at'),
    ]

    operations = [
        migrations.RunPython(backfill_asset_ids, migrations.RunPython.noop),
    ]
