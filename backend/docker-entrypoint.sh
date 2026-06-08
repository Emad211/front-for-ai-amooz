#!/bin/sh
# Container entrypoint for the AI-Amooz backend image (shared by the web and
# Celery worker containers).
#
# DB migrations and static collection are gated behind env flags so they do NOT
# run on every pod start. In a multi-replica deployment, several pods starting
# at once would each run `migrate`, racing on the schema and slowing rollouts;
# `collectstatic` on every start is likewise wasteful and can race on a shared
# volume. Run them ONCE per release via a dedicated step/Job (see
# k8s/migrate-job.yaml) and set RUN_MIGRATIONS=false / RUN_COLLECTSTATIC=false
# on the long-running Deployments.
#
# Defaults are "true" so single-instance setups (docker-compose) keep working
# with no extra configuration.
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "[entrypoint] applying database migrations..."
  python manage.py migrate --noinput
fi

if [ "${RUN_COLLECTSTATIC:-true}" = "true" ]; then
  echo "[entrypoint] collecting static files..."
  python manage.py collectstatic --noinput
fi

exec "$@"
