"""Recompute USD + Toman cost for existing LLMUsageLog rows.

Useful after changing the price table or once the live exchange rate is
available, to (re)populate ``estimated_cost_toman`` (and optionally
``estimated_cost_usd``) from the stored token counts.

NOTE: rows that were logged with zero tokens (e.g. before the token
extraction fix) cannot be recovered — their cost stays zero.

Usage:
    python manage.py recompute_llm_costs            # last 30 days, dry-run summary
    python manage.py recompute_llm_costs --days 0   # all rows
    python manage.py recompute_llm_costs --apply     # actually write
    python manage.py recompute_llm_costs --recompute-usd --apply
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.commons.models import LLMUsageLog, estimate_cost
from apps.commons.exchange_rate import convert_usd_to_toman


class Command(BaseCommand):
    help = 'Recompute estimated_cost_toman (and optionally USD) for LLMUsageLog rows.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30,
                            help='Only rows newer than N days (0 = all rows). Default 30.')
        parser.add_argument('--apply', action='store_true',
                            help='Persist changes. Without it, only reports what would change.')
        parser.add_argument('--recompute-usd', action='store_true',
                            help='Also recompute estimated_cost_usd from the current price table.')
        parser.add_argument('--batch-size', type=int, default=500)

    def handle(self, *args, **opts):
        days = opts['days']
        apply = opts['apply']
        recompute_usd = opts['recompute_usd']
        batch_size = opts['batch_size']

        qs = LLMUsageLog.objects.all().order_by('id')
        if days and days > 0:
            qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=days))

        total = qs.count()
        self.stdout.write(f'Scanning {total} rows (apply={apply}, recompute_usd={recompute_usd})...')

        # Resolve the rate once so all rows in this run share a consistent rate.
        _, rate, rate_err = convert_usd_to_toman(1.0)
        if rate is None:
            self.stderr.write(self.style.ERROR(
                f'No USD→Toman rate available ({rate_err}). Set USDT_TOMAN_FALLBACK or retry.'
            ))
            return
        self.stdout.write(f'Using USD→Toman rate: {rate}')

        updated = 0
        to_update: list[LLMUsageLog] = []
        fields = ['estimated_cost_toman', 'usd_toman_rate']
        if recompute_usd:
            fields.append('estimated_cost_usd')

        for log in qs.iterator(chunk_size=batch_size):
            cost_usd = float(log.estimated_cost_usd or 0)
            if recompute_usd:
                cost_usd = estimate_cost(
                    log.model_name,
                    log.input_tokens,
                    log.output_tokens,
                    provider=log.provider,
                    audio_input_tokens=log.audio_input_tokens,
                    cached_input_tokens=log.cached_input_tokens,
                )
                log.estimated_cost_usd = cost_usd

            log.estimated_cost_toman = round(cost_usd * rate, 2)
            log.usd_toman_rate = rate
            to_update.append(log)
            updated += 1

            if apply and len(to_update) >= batch_size:
                LLMUsageLog.objects.bulk_update(to_update, fields)
                to_update.clear()

        if apply and to_update:
            LLMUsageLog.objects.bulk_update(to_update, fields)

        verb = 'Updated' if apply else 'Would update'
        self.stdout.write(self.style.SUCCESS(f'{verb} {updated} rows.'))
        if not apply:
            self.stdout.write('Dry run — re-run with --apply to persist.')
