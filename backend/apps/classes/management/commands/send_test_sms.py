import json
import os

from django.core.management.base import BaseCommand, CommandError

from apps.classes.services.mediana_sms import send_peer_to_peer_sms


class Command(BaseCommand):
    help = 'Send a test SMS via Mediana (/sms/v1/send/array).'

    def add_arguments(self, parser):
        parser.add_argument('--phone', required=True, help='Recipient phone number (e.g., 0992...)')
        parser.add_argument('--text', default='پیام تست سامانه AI_AMOOZ', help='Message text')
        parser.add_argument(
            '--message-type',
            default='Informational',
            help='Mediana message type (default: Informational)',
        )
        parser.add_argument('--ref-id', default='test', help='Reference id to track this message')

    def handle(self, *args, **options):
        api_key = (os.getenv('MEDIANA_API_KEY') or '').strip()
        if not api_key:
            raise CommandError('MEDIANA_API_KEY is not set in environment')

        phone = (options['phone'] or '').strip()
        text = (options['text'] or '').strip()
        message_type = (options['message_type'] or '').strip() or 'Informational'
        ref_id = str(options['ref_id'] or 'test')

        if not phone:
            raise CommandError('phone is required')
        if not text:
            raise CommandError('text is required')

        payload_requests = [
            {
                'RefId': ref_id,
                'TextMessage': text,
                'Recipients': [phone],
            }
        ]

        try:
            result = send_peer_to_peer_sms(api_key=api_key, requests=payload_requests, message_type=message_type)
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
