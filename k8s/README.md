# Kubernetes / Darkube Manifests for AI_AMOOZ Backend

## Apply order

1. `cors-middleware.yaml`
2. `upload-limit-middleware.yaml`
3. `ingress.yaml` (or update via Darkube panel)
4. `celery-worker-deployment.yaml`
5. `celery-interactive-worker-deployment.yaml`
6. `celery-beat-deployment.yaml`

All resources live in namespace: `ai-products-ai-amooz`
