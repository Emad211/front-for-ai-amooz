"""Create the application media bucket and keep it private.

Usage (from any pod with S3 env vars):
    python manage.py setup_s3_bucket

This is idempotent — safe to run multiple times.
"""
from __future__ import annotations

import logging

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create the private application media bucket.'

    def handle(self, *args, **options):  # noqa: ARG002
        bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '')
        endpoint = getattr(settings, 'AWS_S3_ENDPOINT_URL', '')
        if not bucket or not endpoint:
            raise CommandError(
                'AWS_STORAGE_BUCKET_NAME and AWS_S3_ENDPOINT_URL must be set.'
            )

        s3 = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', ''),
            aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', ''),
            region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1'),
        )

        try:
            s3.create_bucket(Bucket=bucket)
            self.stdout.write(self.style.SUCCESS(f'Bucket "{bucket}" created.'))
        except ClientError as exc:
            code = exc.response.get('Error', {}).get('Code', '')
            if code in ('BucketAlreadyOwnedByYou', 'BucketAlreadyExists'):
                self.stdout.write(f'Bucket "{bucket}" already exists.')
            else:
                raise CommandError(f'Failed to create bucket: {exc}') from exc

        # All media is served by the authenticated/public Django proxy. Keeping
        # one private bucket avoids exposing student originals through S3 URLs.
        try:
            s3.delete_bucket_policy(Bucket=bucket)
        except ClientError as exc:
            code = exc.response.get('Error', {}).get('Code', '')
            if code not in ('NoSuchBucketPolicy', 'NoSuchPolicy'):
                raise CommandError(f'Failed to enforce private policy: {exc}') from exc
        self.stdout.write(self.style.SUCCESS(
            f'Private policy enforced for "{bucket}".'
        ))

        self.stdout.write(self.style.SUCCESS('S3 bucket setup complete.'))
