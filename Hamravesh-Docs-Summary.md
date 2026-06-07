# Hamravesh Documentation — Concise Developer Reference (English)

> **Source:** https://docs.hamravesh.com/ (Persian). This is a condensed, accurate English summary — exact hostnames, commands, env vars, ports, and limits are kept verbatim. Verify current values on the live docs/console, as plans and limits change.
> **Compiled:** June 2026.

---

## 1. Overview

**Hamravesh** is an Iranian cloud provider. Its flagship is **Darkube**, a Kubernetes-based **PaaS** that lets you build, deploy, scale, and operate apps (plus managed databases, brokers, and one-click apps) without managing the cluster. Around it sit several standalone services.

**Products:** Darkube (PaaS) · Container Registry "Hamdocker" · Hamgit (hosted GitLab) · GitLab Runner · S3 Object Storage · Log Aggregation · Monitoring · Backup · Managed Kubernetes/Database · Load Balancer · Network (exclusive outbound IP) · Sentry · Cloud Marketplace.

**Key consoles & hosts**

| Purpose | URL / host |
|---|---|
| Main console | `https://console.hamravesh.com` |
| Container registry mgmt | `https://console.hamravesh.com/container-registry` |
| Object storage mgmt | `https://console.hamravesh.com/storage` |
| Docker Hub **mirror/proxy** (pull base images) | `hub.hamdocker.ir` |
| **Private** container registry (push/pull your images) | `registry.hamdocker.ir` |
| Public Hamravesh images (e.g. CLI) | `hamravesh.hamdocker.ir/public` |
| Default app subdomain | `*.darkube.app` |
| Default DB external host | `*.hsvc.ir` |
| Default object-storage domain | `*.hs3.ir` |
| Hosted GitLab | `hamgit.ir` |
| Deploy webhook API | `https://api.console.hamravesh.ir/api/v1/darkube/apps/update_from_cli/` |

---

## 2. Core Concepts

- **Organization** — top-level account/tenant; its name prefixes all namespaces. **Max 2 orgs/account.** Owner has all permissions; other members get **roles**.
- **Cluster / Datacenter** — physical location. Each namespace lives in exactly one datacenter.
- **Namespace** — Kubernetes isolation unit (e.g. `staging`, `production`, or per-microservice). Each datacenter has a default namespace named after the org. **Max 10 namespaces/org.** App names can repeat across namespaces.
- **App** — a deployed workload, managed under the console's **Darkube** tab.
- **Plan** — RAM + CPU allocation (predefined or custom).

---

## 3. Darkube — Creating Apps

Create via **Create App (ساخت اپ)**. App source types:

- **Git repo** — repo contains a `Dockerfile`; Darkube builds & deploys. Pick repo + branch. Supports **GitHub** and **Hamgit**.
  - GitHub: install the Darkube GitHub app once (approve permissions, select repos) → repos/branches listed.
  - **Auto-deploy on push** toggle; **Dockerfile path** (default repo root, e.g. `./Dockerfile`); **Build Context** (default root).
  - No-Dockerfile option: **Heroku Buildpacks** standard image for the chosen stack.
- **Docker image** — image address (`nginx`, or `registry.hamdocker.ir/<user>/img` for private) + **tag**. Public images, or connect a private/3rd-party registry.
- **docker-compose.yml** — paste compose (**v≥3.0**); each service is converted into a separate Darkube app. Supported keys include `image, command, entrypoint, ports, environment, volumes, depends_on`.
- **File upload** — deploy Dockerized code without a Git repo.
- **One-click / ready apps** — curated **Helm** charts: pick name + subdomain + plan.
- **Popular apps** — guided stack/tool docs.

**One-click apps (documented):** Grafana, Prometheus, Kibana, Metabase, Jira, Confluence, Rocket.Chat, Nextcloud, Keycloak, Nginx, RabbitMQ, Kafka, Pyroscope, GitLab Runner.
**Popular/stack docs:** OpenSSH Server, SonarQube, React.js, Python, Node.js, PHP, Ruby, Go, Java, .NET, EFK stack, WordPress.

**Example Dockerfiles (verbatim):**

```dockerfile
# Django app, port 8000 (uses hub.hamdocker.ir mirror)
FROM hub.hamdocker.ir/library/python:3.8
WORKDIR /django_app/
ADD ./requirements.txt ./
RUN pip install -r ./requirements.txt
ADD ./ ./
ENTRYPOINT ["/bin/sh","-c","python manage.py migrate && gunicorn --bind 0.0.0.0:8000 django_app.wsgi"]
```

> ⚠️ Apps must bind to **`0.0.0.0`**, not `127.0.0.1`.

---

## 4. App Settings

- **Ports** — main service port; multi-port supported. If a domain is attached, one port must be named **`http`** or **`main`**. Named ports are reachable in-cluster by name.
- **Domain address** — free `*.darkube.app` subdomain and/or custom domain; options: **SSL cert generation**, **HTTP→HTTPS redirect (301)**, **HTTP basic auth**.
- **Environment variables** — per-app, plus **shared variables** reusable across apps.
- **Plan / Cluster / Zone / Namespace** — pick RAM+CPU plan (or custom), cluster, region, namespace → Save.

---

## 5. Managed Databases & Message Brokers

**Databases (Create App → Databases):** Redis, PostgreSQL, MySQL, MariaDB, MongoDB, MsSQL, Elasticsearch, MinIO.
**Message brokers (Create App → ready apps):** RabbitMQ, Kafka.

**Common pattern:** pick type → name → optional **Internet access** toggle → cluster/namespace/plan → Create (~1 min). Credentials + internal/external addresses are in the **General Information** tab. External host = `SUB_DOMAIN.hsvc.ir` + an assigned **PORT**. Internal host = app name. Managed DBs do **not** auto-inject `DB_*` env vars — read host/port/password from the panel and set your app's env vars manually.

| Service | Default user | Internal port | Config file | Data path |
|---|---|---|---|---|
| Redis | (password only) | 6379 | overrides redis.conf | needs added disk (ephemeral otherwise; `appendonly` needs disk) |
| PostgreSQL | `postgres` | 5432 | `/etc/postgresql/postgresql.conf` | `/var/lib/postgresql/data` |
| MySQL | `root` | 3306 | `/opt/bitnami/mysql/conf/bitnami/my_custom.cnf` | `/bitnami/mysql` |
| MariaDB | `root` | 3306 | `/opt/bitnami/mariadb/conf/bitnami/my_custom.cnf` | `/bitnami/mariadb` |
| MongoDB | `root` | 27017 | `/etc/mongo/mongodb.conf` | `/data` |
| MsSQL | `sa` | 1433 | — | — |
| Elasticsearch | `elastic` | 9200 | `/usr/share/elasticsearch/config/elasticsearch.yml` | `/usr/share/elasticsearch/data` |
| MinIO | env `ACCESSKEY`/`SECRETKEY` | — | — | — |
| Kafka | — | 9092 | — | — |

Connection examples (external): `redis-cli -u redis://SUB.hsvc.ir:PORT --askpass` · `psql -U postgres -h SUB.hsvc.ir -p PORT` · `mysql -h SUB.hsvc.ir -P PORT -u root -p` · `mongosh --host SUB.hsvc.ir --port PORT -u root -p`. Redis only lets you pick image **version** at creation; PostgreSQL enables extensions via `CREATE EXTENSION <name>`.

---

## 6. Managing & Operating Apps

App page tabs: **Logs**, **Resource consumption** (CPU/RAM/Disk graphs), **Resource Management** (resources, replicas, scaling), **Terminal**, **Builds**, **Ports**, **Domain address**, **CustomConfig**, **General info**.

- **Logs** — live pod stdout (e.g. `print`).
- **Terminal** — shell into the container (migrations, debugging) — no SSH on apps; alternatively `kubectl exec`.
- **Builds** — history with branch/commit/log; "Build & deploy last commit" button.
- **Disks (persistence)** — container FS is **ephemeral**; add a **Disk** with capacity + mount path for durability. Increasing capacity = support ticket. Disk billed even when app stopped. Non-root images may need `chown`/`fsGroup` on the mount.
- **Autoscaling (HPA)** — *Resource Management → Scaling*: set **min/max replicas** + target CPU/RAM %. Replicas **min 1, max 20**; HPA min ≥ fixed replica count.
- **Health probes (CustomConfig YAML)** — `livenessProbe` (restart on fail) and `readinessProbe` (stop routing traffic; required for zero-downtime — missing it causes **503** on deploy). Methods: exec / HTTP GET / TCP / gRPC. Fields: `periodSeconds, initialDelaySeconds, timeoutSeconds, successThreshold, failureThreshold`.
- **Deployment strategy (CustomConfig)** — **RollingUpdate** (default, zero-downtime; tune `maxSurge`/`maxUnavailable`) or **Recreate** (downtime, all-at-once).
- **CustomConfig extras** — `configmap` (mount read-only files, optional `subPath`), `hostAliases`, `hostname`, lifecycle hooks `postStart`/`preStop`.

**Build limits & common errors:** build memory cap **2 GB** (OOM → exit `137`); **builds >2h killed**; **100 free build-hours/month** per org. `ImagePullBackoff` = image missing; `Readiness probe failed`/503 = no ready pod; 404 right after deploy = SSL/DNS still provisioning. Prefer exact tags over `latest`.

---

## 7. Custom Domains & TLS

1. In DNS, add a **CNAME** (or ANAME/A) record: key = your domain; value = your `*.darkube.app` subdomain (or the cluster target shown in the **Domain address** tab).
2. Enable **SSL** → certificate auto-issued (a few minutes; 404 until ready).
3. Enable **HTTP→HTTPS redirect** → HTTP returns **301**.

App stays reachable on both the custom domain and the `*.darkube.app` address. Read real client IP from the **`X-Real-Ip`** header. Static outbound (egress) IP per cluster is shown via the "i" next to the cluster name (for whitelisting).

---

## 8. CI/CD

**Mechanism:** pipeline (a) builds + pushes image to `registry.hamdocker.ir`, then (b) deploys with the **`darkube` CLI** (disable app auto-deploy so the pipeline controls deploys).

- **CLI image:** `hamravesh.hamdocker.ir/public/darkube-cli:v1.1`
- **Deploy command:**
  ```sh
  darkube deploy --ref <branch> --token ${DARKUBE_DEPLOY_TOKEN} \
    --app-id ${DARKUBE_APP_ID} --image-tag "<tag>" --job-id "<run id>" --stateless-app true
  ```
- **Build command (CLI):**
  ```sh
  darkube build --push -t $IMAGE:$SHA -t $IMAGE:$REF --file Dockerfile --build-context . --build-arg ENV=...
  ```
- **Values:** `DARKUBE_DEPLOY_TOKEN` and `DARKUBE_APP_ID` from the **app details/edit page** (top-right → "copy app id"); `REGISTRY`/`REGISTRY_USER`/`REGISTRY_PASSWORD` from the console Container Registry section.
- **Webhook alternative (curl):**
  ```
  PUT https://api.console.hamravesh.ir/api/v1/darkube/apps/update_from_cli/
  { "trigger_deploy_token": <token>, "app_id": <id>, "image_tag": <tag> }
  ```
  Custom webhooks receive Hamravesh's token in the **`X-Hamravesh-Token`** header.

**GitHub Actions** (`.github/workflows/main.yaml`):

```yaml
name: CI/CD Pipeline
on: { push: { branches: [master] } }
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: |
          docker login $REGISTRY -u $REGISTRY_USER -p $REGISTRY_PASSWORD
          docker build -t "$IMAGE:${GITHUB_SHA:0:7}" .
          docker push "$IMAGE:${GITHUB_SHA:0:7}"
        env:
          REGISTRY: ${{ vars.REGISTRY }}
          REGISTRY_USER: ${{ vars.REGISTRY_USER }}
          REGISTRY_PASSWORD: ${{ vars.REGISTRY_PASSWORD }}
          IMAGE: ${{ vars.REGISTRY }}/${{ vars.APP_NAME }}
  darkube_deploy:
    needs: build
    runs-on: ubuntu-latest
    container: hamravesh.hamdocker.ir/public/darkube-cli:v1.1
    steps:
      - run: darkube deploy --ref master --token ${DARKUBE_DEPLOY_TOKEN} --app-id ${DARKUBE_APP_ID} --image-tag "${GITHUB_SHA:0:7}" --job-id "$GITHUB_RUN_ID" --stateless-app true
        env:
          DARKUBE_DEPLOY_TOKEN: ${{ vars.DARKUBE_DEPLOY_TOKEN }}
          DARKUBE_APP_ID: ${{ vars.DARKUBE_APP_ID }}
```

**GitLab CI** (`.gitlab-ci.yml`):

```yaml
stages: [build, deploy]
variables: { IMAGE: "$REGISTRY/$APP_NAME" }
build:
  stage: build
  image: docker:latest
  services: [docker:dind]
  script:
    - docker login $REGISTRY -u $REGISTRY_USER -p $REGISTRY_PASSWORD
    - docker build -t "$IMAGE:$CI_COMMIT_SHORT_SHA" .
    - docker push "$IMAGE:$CI_COMMIT_SHORT_SHA"
  only: [prod]
darkube_deploy:
  stage: deploy
  image: hamravesh.hamdocker.ir/public/darkube-cli:v1.1
  script:
    - darkube deploy --ref prod --token $DARKUBE_DEPLOY_TOKEN --app-id $DARKUBE_APP_ID --image-tag "$CI_COMMIT_SHORT_SHA" --job-id "$CI_JOB_ID" --stateless-app true
  only: [prod]
```

CI variable `REGISTRY` = `registry.hamdocker.ir/<USERNAME>`. Other tools: **SonarQube** (CI vars `SONAR_TOKEN`, `SONAR_HOST_URL`).

---

## 9. hamctl (CLI)

- **Install:** `sudo npm i -g hamctl` (or download a binary). Config in `~/.hamctlconfig`.
- **Auth:** `hamctl login [-u <user> -p <pass>]` · `hamctl logout` (or API key).
- **Orgs:** `hamctl organizations list|switch`
- **Namespaces:** `hamctl namespaces list|create`
- **Apps:**
  ```sh
  hamctl apps list
  hamctl apps create --name <n> --namespace <ns> --cluster <c> --type <type>
  hamctl apps details <app>
  hamctl apps set-image <app> --image <img> --tag <tag>
  hamctl apps start|stop <app> --namespace <ns> --cluster <c>
  hamctl apps delete <app> --namespace <ns> --cluster <c>
  ```
  `--type`: `docker-image, github-repo, hamgit-repo`; DBs `redis postgresql minio mysql mariadb mongodb elasticsearch mssql`; popular `jira metabase grafana rabbitmq prometheus wordpress confluence rocketchat gitlab_runner kibana nextcloud`; stacks `static nodejs python php ruby go java dotnet`.

---

## 10. kubectl Access (scoped/OIDC)

Scoped to debugging/app-management commands. Setup: install `kubectl` (client **≥ 1.24**), `krew`, then `kubectl krew install oidc-login`. Download **kubeconfig** from console → "kubectl config" (apps list); set `~/.kube/config` or `export KUBECONFIG=/path/config.yaml`. First command opens a browser for **OIDC login** (console email + password). Use `-n <namespace>` when needed.

Common: `kubectl get pods -o wide` · `logs -f POD` · `describe pod POD` · `exec -it POD -- bash` · `port-forward pod/POD L:R` · `cp` · `get svc`. Auth cache fix: `rm -rf ~/.kube/cache/oidc-login/` (keep local port 8000 free).

---

## 11. Container Registry (Hamdocker)

Every org gets a private registry; build outputs auto-push there.

- **Hosts:** private `registry.hamdocker.ir/<org>/<image>`; public `hamravesh.hamdocker.ir/public/...`; Docker Hub mirror `hub.hamdocker.ir` (use `library/` prefix for official images, e.g. `docker pull library/python`).
- **Login / push / pull:**
  ```sh
  docker login registry.hamdocker.ir   # username/password from console
  docker push registry.hamdocker.ir/<org>/<image>:<tag>
  ```
- Images stored **compressed** (stored < pushed size). Manage/delete images, tags, digests at `console.hamravesh.com/container-registry`. Can also connect external/3rd-party registries for build/deploy.

---

## 12. Hamgit & GitLab Runner

- **Hamgit** (`hamgit.ir`) — free hosted GitLab for Iranian users (a GitLab alternative after sanctions). Sign in via **"Sign in with Hamravesh"** (OAuth through the console). Create/import projects.
- **GitLab Runner** — deploy a dedicated runner from the console (Create App → ready app → GitLab Runner): in repo/group **Settings → CI/CD → Runners** copy URL + token (group-level recommended), paste into the app, pick plan → create. CI vars in **Settings → CI/CD → Variables**, used as `$VAR`. Works with Hamgit or any GitLab. Common CI errors: `137` (OOM), `403` (sanctions → ticket), timeouts (`retry: 2`).

---

## 13. S3 Object Storage

S3-compatible: organize into **buckets**, access via **keys**, optional custom domains. Console: `console.hamravesh.com/storage`.

- **Buckets:** name + storage class. **Limit 3 buckets/org** (public service). Soft-delete (purged after hours; still counts during window); ≥1 day billing minimum.
- **Public URL pattern:** `https://<storage>.hs3.ir/<bucket>/path/file` (bucket in the path).
- **Keys (Keys tab):** name + access level (**Read / Write / List**) + which buckets. **Secret shown once — save it.**
- **Endpoint:** no fixed regional endpoint — it's your **storage domain** (default `*.hs3.ir` or your custom domain), shown in storage "General Info". S3 compat = generic `provider = Other`.
- **rclone config:**
  ```ini
  [hamravesh]
  type = s3
  provider = Other
  access_key_id = <ACCESS_KEY>
  secret_access_key = <SECRET_KEY>
  endpoint = https://<storage-domain>
  ```
  ```sh
  rclone sync source:/<bucket> hamravesh:/<bucket> --progress
  ```
- **Custom domain + TLS:** Settings → Manage domains → Add domain → create the shown **CNAME/A** record in DNS, then the requested **TXT** record for the SSL cert → Re-check. A default domain covering all buckets is auto-created with your first bucket. Public buckets + a domain = static hosting over HTTPS.

---

## 14. Log Aggregation & Monitoring

- **Log Aggregation** — collect app logs (from defined files + pod stdout) into a **Loki** datasource; view/query in **Grafana** with the provided credentials. Optional **pipeline** to store logs in **MinIO** or **Elasticsearch**.
- **Monitoring** — expose app metrics in **Prometheus** format (scraped every few seconds) plus cluster/namespace metrics (CPU/RAM/disk/status); receive a **Datasource** (address + user + password) connectable to Grafana.

---

## 15. Backup

- **Automatic & scheduled:** hourly / daily / monthly; snapshot-based (no downtime). ~**99.9%** disk-backup success.
- **Off-site:** each backup stored in a **different datacenter**.
- **Retention:** configurable; **default keeps the 2 most recent** backups.
- **Scope:** disk-bearing Darkube apps + managed DBs (PostgreSQL, MySQL, MongoDB, MinIO). Currently **Hamravesh Kubernetes infra only**, **BTRFS filesystem only**.
- **Restore:** panel restore to main disk; "Create App from backup" clones an app preloaded with backup data; restorable to another cluster for DR.
- **Download:** **Filebrowser** (open in browser) or **WebDAV** (read-only address + creds); use **rclone** for large/fast downloads. Backup storage is read-only to users.

---

## 16. Limits & Quotas (consolidated)

| Limit | Value |
|---|---|
| Organizations per account | 2 |
| Namespaces per org | 10 |
| App replicas | 1–20 |
| Build memory | 2 GB (OOM → exit 137) |
| Build duration | killed after 2h |
| Free build hours | 100 / month / org |
| S3 buckets per org | 3 (public service) |
| DB backups retained (default) | 2 |
| docker-compose version | ≥ 3.0 |
| kubectl client | ≥ 1.24 |

---

## 17. FAQ — Developer Highlights

- Bind services to **`0.0.0.0`** + correct port (else connection timeout).
- Pull official Docker Hub images with **`library/`** prefix (Hub proxy).
- In-cluster service-to-service: `SVC_NAME.NS.svc` (Darkube app: SVC_NAME = app name); or use the app's internal-address env var.
- Disk permission (non-root): initContainer `chown -R UID:GID /mount` or `securityContext.fsGroup`.
- Avoid `latest`; use exact tags/digests or `Major.Minor`.
- **No SSH** to apps; use `kubectl exec` or the Terminal tab; `privileged`/`--cap-add` not allowed on public clusters.
- Container FS is ephemeral → use a **Disk** for persistence.
- Static egress IP per cluster (for bank/SMS whitelisting); real client IP via `X-Real-Ip`.
- Set timezone via Dockerfile `ENV TZ` + symlink `/etc/localtime`.
- **No mail server** on the cloud platform (shared IPs, fixed ports not exposable).

---

## 18. Source Pages (representative)

Darkube: `/darkube/` · `/darkube/first-app/` · `/darkube/next-step/` · `/darkube/apps/git-repo/` · `/darkube/create/git-repo/settings/{general,domain-address}/` · `/darkube/create/docker-image/intro/` · `/darkube/create/docker-compose/` · `/darkube/create/1click/{intro,nginx,Kafka,RabbitMQ}/` · `/darkube/create/popular/{openssh-server,sonarqube,react-app,efk-stack}/` · `/darkube/create/databases/{intro,redis,postgresql,mysql,mariadb,mongodb,mssql,elasticsearch,minio}/` · `/darkube/getting-started/database/`
Manage: `/darkube/manage/{intro,terminal,monitoring,log-aggregation,domain-address,hpa,hamctl,general,ports,custom-config,troubleshooting}/`
CI/CD & access: `/darkube/ci-cd/{intro,github-actions}/` · `/darkube/general-features/{organization,org-members-management,namespaces,kubectl}/`
Products: `/container-registry/introduction/` · `/hamgit/{intro,start}/` · `/gitlab-runner/intro/` · `/s3/{quick-start,keys,domains}/` · `/products/s3/migration/` · `/log_aggregation/introduction/` · `/monitoring/introduction/` · `/backup/{intro,download}/` · `/faq/`

> ⚠️ **Accuracy note:** Several index pages are client-rendered; their content was recovered via search extracts, and some details (e.g. RabbitMQ ports) are standard defaults rather than doc-verbatim. Treat the live docs and console as authoritative.
