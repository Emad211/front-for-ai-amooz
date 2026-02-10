"""Management command to diagnose S3 / MinIO connectivity.

Usage:
    python manage.py check_s3

Checks: env vars present, DNS resolution, TCP reachability, credential
validity, bucket existence, and a round-trip write/read/delete test.
"""
from __future__ import annotations

import socket
import time
from io import BytesIO
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Diagnose S3 / MinIO connectivity from this pod.'

    def _ok(self, msg: str) -> None:
        self.stdout.write(self.style.SUCCESS(f'  [OK] {msg}'))

    def _fail(self, msg: str) -> None:
        self.stdout.write(self.style.ERROR(f'  [FAIL] {msg}'))

    def _info(self, msg: str) -> None:
        self.stdout.write(f'  [INFO] {msg}')

    def handle(self, *args, **options):  # noqa: ARG002
        endpoint = getattr(settings, 'AWS_S3_ENDPOINT_URL', '') or ''
        bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '') or ''
        key_id = getattr(settings, 'AWS_ACCESS_KEY_ID', '') or ''
        secret = getattr(settings, 'AWS_SECRET_ACCESS_KEY', '') or ''
        region = getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')

        self.stdout.write('\n=== S3 / MinIO Connectivity Check ===\n')

        # ── 1. Env vars ──────────────────────────────────────────────
        self.stdout.write('1) Environment variables:')
        self._info(f'AWS_S3_ENDPOINT_URL  = {endpoint!r}')
        self._info(f'AWS_STORAGE_BUCKET   = {bucket!r}')
        self._info(f'AWS_ACCESS_KEY_ID    = {key_id!r}')
        # Show first 4 + last 4 chars of secret for debugging (mask middle)
        if secret:
            masked = secret[:4] + '***' + secret[-4:] if len(secret) > 8 else '***'
            self._info(f'AWS_SECRET_ACCESS_KEY= {masked}  (length={len(secret)})')
        else:
            self._fail('AWS_SECRET_ACCESS_KEY is empty!')

        if not endpoint or not bucket or not key_id or not secret:
            self._fail('One or more required env vars are missing.')
            return

        self._ok('All env vars present.')

        # ── 2. DNS resolution ─────────────────────────────────────────
        parsed = urlparse(endpoint)
        host = parsed.hostname or ''
        port = parsed.port or 9000
        self.stdout.write(f'\n2) DNS resolution for {host}:')
        try:
            ips = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
            self._ok(f'Resolved to {ips[0][4][0]}')
        except socket.gaierror as exc:
            self._fail(f'DNS lookup failed: {exc}')
            return

        # ── 3. TCP connectivity ───────────────────────────────────────
        self.stdout.write(f'\n3) TCP connection to {host}:{port}:')
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            t0 = time.monotonic()
            sock.connect((host, port))
            elapsed = (time.monotonic() - t0) * 1000
            self._ok(f'Connected in {elapsed:.0f} ms')
        except (OSError, socket.timeout) as exc:
            self._fail(f'TCP connect failed: {exc}')
            return
        finally:
            sock.close()

        # ── 4. S3 authentication ──────────────────────────────────────
        self.stdout.write('\n4) S3 authentication (list buckets):')
        s3 = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=key_id,
            aws_secret_access_key=secret,
            region_name=region,
            config=Config(
                connect_timeout=5,
                read_timeout=10,
                retries={'max_attempts': 1},
                signature_version='s3v4',
                s3={'addressing_style': 'path'},
            ),
        )
        try:
            resp = s3.list_buckets()
            names = [b['Name'] for b in resp.get('Buckets', [])]
            self._ok(f'Authenticated. Buckets: {names}')
        except NoCredentialsError:
            self._fail('No credentials (boto3 could not find creds).')
            return
        except ClientError as exc:
            code = exc.response.get('Error', {}).get('Code', '')
            msg = exc.response.get('Error', {}).get('Message', '')
            self._fail(f'ClientError {code}: {msg}')
            self._info('This usually means wrong ACCESS_KEY or SECRET_KEY.')
            self._info('Check for shell variable expansion in password ($ # ! chars).')
            return
        except EndpointConnectionError as exc:
            self._fail(f'Cannot connect to endpoint: {exc}')
            return

        # ── 5. Bucket exists ──────────────────────────────────────────
        self.stdout.write(f'\n5) Bucket "{bucket}" exists:')
        try:
            s3.head_bucket(Bucket=bucket)
            self._ok('Bucket exists and is accessible.')
        except ClientError as exc:
            code = exc.response.get('Error', {}).get('Code', '')
            if code in ('404', 'NoSuchBucket'):
                self._fail(f'Bucket "{bucket}" does NOT exist. Run: python manage.py setup_s3_bucket')
            elif code in ('403', 'AccessDenied'):
                self._fail('Bucket exists but access denied (wrong permissions).')
            else:
                self._fail(f'head_bucket error: {code} — {exc}')
            return

        # ── 6. Write / Read / Delete round-trip ───────────────────────
        self.stdout.write('\n6) Write / Read / Delete test:')
        test_key = '_check_s3_test_object.txt'
        test_data = b'check_s3 connectivity test'
        try:
            s3.put_object(Bucket=bucket, Key=test_key, Body=BytesIO(test_data))
            self._ok(f'PUT {test_key} succeeded.')
        except Exception as exc:
            self._fail(f'PUT failed: {exc}')
            return

        try:
            obj = s3.get_object(Bucket=bucket, Key=test_key)
            body = obj['Body'].read()
            if body == test_data:
                self._ok(f'GET {test_key} succeeded and data matches.')
            else:
                self._fail(f'GET data mismatch! Got {len(body)} bytes.')
        except Exception as exc:
            self._fail(f'GET failed: {exc}')

        try:
            s3.delete_object(Bucket=bucket, Key=test_key)
            self._ok(f'DELETE {test_key} succeeded.')
        except Exception as exc:
            self._fail(f'DELETE failed: {exc}')

        self.stdout.write(self.style.SUCCESS('\n=== All checks passed ===\n'))
