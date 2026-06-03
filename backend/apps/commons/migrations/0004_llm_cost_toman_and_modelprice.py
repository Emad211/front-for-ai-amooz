"""Add Toman cost snapshot fields, per-user×per-task index, and the
admin-editable ModelPrice table (seeded from the hardcoded MODEL_PRICING)."""

from django.db import migrations, models
import django.utils.timezone


# Starting-point USD-per-1M-token rates (mirrors MODEL_PRICING at creation
# time).  Seeded with a blank provider so they apply to any provider until
# an admin adds provider-specific (e.g. Avalai) rows in the panel.
_SEED_PRICES = [
    # model_name, input, output, audio_input, cached_input
    ('gemini-2.5-flash', '0.30', '2.50', '1.00', '0.03'),
    ('gemini-2.0-flash', '0.10', '0.40', None, None),
    ('gemini-2.0-flash-lite', '0.075', '0.30', None, None),
    ('gemini-1.5-flash', '0.075', '0.30', None, None),
    ('gemini-1.5-pro', '1.25', '5.00', None, None),
]


def seed_model_prices(apps, schema_editor):
    ModelPrice = apps.get_model('commons', 'ModelPrice')
    now = django.utils.timezone.now()
    for model_name, inp, out, audio, cached in _SEED_PRICES:
        ModelPrice.objects.get_or_create(
            provider='',
            model_name=model_name,
            effective_from=now,
            defaults={
                'input_usd_per_1m': inp,
                'output_usd_per_1m': out,
                'audio_input_usd_per_1m': audio,
                'cached_input_usd_per_1m': cached,
                'is_active': True,
                'note': 'Seed from MODEL_PRICING — adjust to real Avalai rates.',
            },
        )


def unseed_model_prices(apps, schema_editor):
    ModelPrice = apps.get_model('commons', 'ModelPrice')
    ModelPrice.objects.filter(
        note='Seed from MODEL_PRICING — adjust to real Avalai rates.'
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('commons', '0003_add_token_type_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='llmusagelog',
            name='feature',
            field=models.CharField(
                choices=[
                    ('transcription', 'Transcription'),
                    ('structure', 'Structure'),
                    ('prereq_extract', 'Prerequisite Extraction'),
                    ('prereq_teach', 'Prerequisite Teaching'),
                    ('recap', 'Recap Generation'),
                    ('exam_prep_structure', 'Exam Prep Structure'),
                    ('quiz_generation', 'Quiz Generation'),
                    ('quiz_grading', 'Quiz Grading'),
                    ('final_exam_generation', 'Final Exam Generation'),
                    ('hint_generation', 'Hint Generation'),
                    ('chat_course', 'Course Chat'),
                    ('chat_exam_prep', 'Exam Prep Chat'),
                    ('chat_intent', 'Chat Intent Classifier'),
                    ('chat_widget', 'Chat Widget'),
                    ('chat_vision', 'Chat Vision'),
                    ('chat_system_prompt', 'Chat System Prompt'),
                    ('memory_summary', 'Memory Summarization'),
                    ('flash_cards', 'Flash Cards'),
                    ('fetch_quizzes', 'Quiz Widget'),
                    ('match_games', 'Match Game'),
                    ('practice_tests', 'Practice Test'),
                    ('meril', 'Merrill Content'),
                    ('notes_ai', 'AI Notes'),
                    ('image_plan', 'Image Plan'),
                    ('exam_prep_handwriting_vision', 'Exam Prep Handwriting Vision'),
                    ('json_repair', 'JSON Repair'),
                    ('other', 'Other'),
                ],
                db_index=True,
                default='other',
                max_length=40,
            ),
        ),
        migrations.AddField(
            model_name='llmusagelog',
            name='estimated_cost_toman',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Cost in Toman, computed at call time from the live USD rate.',
                max_digits=14,
            ),
        ),
        migrations.AddField(
            model_name='llmusagelog',
            name='usd_toman_rate',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='USDT→Toman rate applied when this row was written.',
                max_digits=12,
            ),
        ),
        migrations.AddIndex(
            model_name='llmusagelog',
            index=models.Index(
                fields=['user', 'feature', 'created_at'],
                name='idx_llm_user_feat_created',
            ),
        ),
        migrations.CreateModel(
            name='ModelPrice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(blank=True, default='', help_text="Provider key (e.g. 'avalai', 'gapgpt', 'gemini'). Blank = any provider.", max_length=32)),
                ('model_name', models.CharField(help_text="Model name without the 'models/' prefix, e.g. 'gemini-2.5-flash'.", max_length=100)),
                ('input_usd_per_1m', models.DecimalField(decimal_places=6, default=0, max_digits=12)),
                ('output_usd_per_1m', models.DecimalField(decimal_places=6, default=0, max_digits=12)),
                ('audio_input_usd_per_1m', models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True)),
                ('cached_input_usd_per_1m', models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('effective_from', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('note', models.CharField(blank=True, default='', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['provider', 'model_name', '-effective_from'],
            },
        ),
        migrations.AddConstraint(
            model_name='modelprice',
            constraint=models.UniqueConstraint(
                fields=['provider', 'model_name', 'effective_from'],
                name='uniq_model_price_provider_model_effective',
            ),
        ),
        migrations.RunPython(seed_model_prices, unseed_model_prices),
    ]
