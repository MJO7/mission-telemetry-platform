# Kubernetes deployment

Everything needed to run the full platform on a real cluster: manifests
for every service, Helm values for Kafka/Redis, an Ansible playbook
that provisions a bare node into a running k3s cluster, and the GitHub
Actions pipeline that builds/pushes/validates it all. Built out of the
normal phase order (the [build spec](../docs/) has this as Phase 8
territory, after Phase 6/7) at explicit user direction; see the
`k8s-build-progress` memory for the full record if you're picking this
back up.

## What's here

```
k8s/
  base/                  Namespace, ConfigMaps, Secret template, Postgres
                          StatefulSet, 4 app Deployments, HPA, Kustomization
  overlays/ci/           Kustomize overlay: same manifests, images
                          repointed at ghcr.io for the CI validation job
  helm-values/           Redpanda + Redis chart overrides
  loadtest.js            Real k6 script that drives the HPA
  *.log                  Real evidence from the rollout/load-test demos below
ansible/
  playbook.yml           Bare Ubuntu node -> running k3s
.github/workflows/ci.yml Test -> build+push -> validate-deploy
```

## Why 4 Deployments, not 3

The original scope named the Go publisher, FastAPI, and the React
client. `processor` (Python) is in here too, flagged rather than
silently added: without it, nothing ever consumes `telemetry.raw`,
nothing lands in Postgres, and Phase 4's live WebSocket stream has
nothing to fan out. The system doesn't do its job without it running
somewhere.

## Quickstart (local k3d)

```
k3d cluster create mission-telemetry --agents 1 --wait
docker build -t mission-telemetry/api-service:local -f services/api-service/Dockerfile services/api-service
docker build -t mission-telemetry/ingest-service:local -f services/ingest-service/Dockerfile services/ingest-service
docker build -t mission-telemetry/web:local -f web/Dockerfile --build-arg VITE_API_BASE_URL=http://api-service:8000 web
docker build -t mission-telemetry/processor:local -f services/processor/Dockerfile .   # context = repo root, see that Dockerfile
k3d image import mission-telemetry/api-service:local mission-telemetry/ingest-service:local mission-telemetry/web:local mission-telemetry/processor:local -c mission-telemetry

helm repo add redpanda https://charts.redpanda.com
helm repo add bitnami https://charts.bitnami.com/bitnami
kubectl apply -f k8s/base/00-namespace.yaml
helm install redpanda redpanda/redpanda -n mission-telemetry -f k8s/helm-values/redpanda-values.yaml --wait
helm install redis bitnami/redis -n mission-telemetry -f k8s/helm-values/redis-values.yaml --wait

# Real secret -- see k8s/base/02-secret.example.yaml for the exact command
kubectl apply -f k8s/base/secret.yaml
kubectl apply -f k8s/base/01-configmap.yaml
kubectl apply -f k8s/base/10-postgres.yaml
kubectl wait --for=condition=ready pod -l app=postgres -n mission-telemetry --timeout=120s
kubectl apply -f k8s/base/20-api-service.yaml -f k8s/base/30-ingest-service.yaml -f k8s/base/40-web.yaml -f k8s/base/50-processor.yaml

kubectl exec -n mission-telemetry redpanda-0 -c redpanda -- rpk topic create telemetry.raw --partitions 3
kubectl exec -n mission-telemetry redpanda-0 -c redpanda -- rpk topic create telemetry.processed --partitions 3
kubectl exec -n mission-telemetry redpanda-0 -c redpanda -- rpk topic create telemetry.dlq --partitions 1
```

## Quickstart (real bare-node k3s, via Ansible + Multipass)

Superseded its own first draft: see
[`deploy/ansible/README.md`](../deploy/ansible/README.md) for the
current, role-based, genuinely-idempotent (`changed=0` on a second run,
proven not asserted) playbook -- it provisions Kafka/Redis, transfers
the four application images, and applies these exact manifests itself,
in one `ansible-playbook playbook.yml`. That doc also has the full
writeup of five real bugs found only by running the original spec
against an actually-bare node (image transfer was entirely missing,
Kafka/Redis were never provisioned, a stray `kustomization.yaml` broke
a flat `kubectl apply -f`, and two separate idempotency bugs in the
kubeconfig-fetch and manifest-apply steps).

## Real measurements, not guessed numbers

Idle local baseline (`docker stats` / `ps` RSS on the docker-compose
dev stack) vs. actual in-cluster usage (`kubectl top pod`) under real
traffic -- the two disagreed for the two services that hold live
Kafka/Postgres/Redis connections, which an idle process never has:

| Service | Idle local baseline | Real in-cluster (`kubectl top`) | Request set to |
|---|---|---|---|
| api-service | ~48 MB | ~90-110Mi | 128Mi |
| processor | ~10.5 MB | ~97Mi | 128Mi |
| postgres | ~80 MiB | ~126Mi | 192Mi |
| ingest-service | ~9.4 MB | ~4-9Mi | 32Mi |
| web (nginx) | ~9.4 MB | ~8Mi | 32Mi |
| redis | ~10 MiB | ~12Mi | 32Mi |
| redpanda | ~1.1 GiB | ~436Mi | (Helm chart minimum) |

Lesson worth keeping: an idle local measurement is a starting point,
not the answer -- the actually-running number, measured after real
requests exercise the real connection pools, is what the manifests are
sized against.

## The rolling-update demo: `maxUnavailable: 0` was not enough by itself

Ran an in-cluster `curlimages/curl` pod hammering both Services
continuously (not a `kubectl port-forward`, which tunnels to one
specific pod and doesn't exercise the Service's real load-balancing --
learned this when the first port-forward-based attempt died mid-test)
while triggering `kubectl rollout restart` on api-service and
ingest-service.

**First run, no `preStop` hook:** real requests failed (`curl` exit
000, connection refused) during the rollout despite `maxUnavailable: 0`
-- see `rollout-demo-before-fix.log`. Root cause: `maxUnavailable: 0`
only constrains the Deployment controller's own pacing. It does not
close the race between a pod receiving SIGTERM and kube-proxy actually
removing that pod from the Service's Endpoints/iptables rules on every
node -- for a brief window, traffic can still land on a pod that's
already shutting down.

**Fix:** `lifecycle.preStop.sleep.seconds: 5` on both Deployments --
the kubelet-*native* sleep action (K8s 1.29+), not `exec: ["sleep","5"]`,
because ingest-service's image is distroless with no shell at all;
`exec` would fail at runtime with nothing to run. The sleep buys time
for endpoint removal to propagate before the container actually stops
accepting connections.

**Re-ran the identical test: `rollout-demo-after-fix.log`, 200/200
requests succeeded, zero drops.**

## The HPA demo: scaling didn't fix throughput, and that's the real lesson

`k8s/loadtest.js` (real k6, 80 ramping VUs against `/v1/auth/me`
through the Service, run as an in-cluster Job -- see the file for
exact stages) drove the HPA from 2 to 6 replicas in ~20s under real CPU
load. That part worked cleanly on the first try.

**But request success rate didn't improve with more pods** -- roughly
25-30% of requests failed. The actual server logs (not a guess) showed
why: `asyncpg.exceptions.TooManyConnectionsError: sorry, too many
clients already`. SQLAlchemy's default pool (`pool_size=5,
max_overflow=10`) means up to 15 connections *per pod*; 6 pods is up to
90 connections from api-service alone, against Postgres's default
`max_connections=100`.

Applied two real fixes -- explicit, bounded pool sizing
(`app/core/db.py`: `pool_size=5, max_overflow=2, pool_timeout=10`) and
`max_connections=300` on the Postgres StatefulSet -- and the specific
`TooManyConnectionsError` went away. The failure rate didn't fully
clear, though, and a later run produced one request that hung for 26+
minutes before the job could report completion (killed rather than
chased further -- see `hpa-loadtest-summary.log`).

**The honest conclusion is more valuable than a clean pass would have
been:** horizontally scaling api-service cannot fix throughput for a
workload whose real bottleneck is a single, non-scaled Postgres
instance. `/v1/auth/me` deliberately does a real DB read on every call
(see its own docstring in `app/routers/auth.py` -- "never stale
relative to the DB"), so more app pods just means more concurrent
callers competing for the same one database, not more real capacity.
The HPA did exactly what it was configured to do (scale on CPU) while
the actual constraint was a completely different resource. A real fix
(a connection pooler like PgBouncer in front of Postgres, or read
replicas) is out of scope for what this pass built -- noted here, not
silently claimed as solved.

## CI design note

`validate-deploy` in `.github/workflows/ci.yml` applies the manifests
to an ephemeral `kind` cluster the job creates and destroys itself, not
the real Multipass/k3s box from the Ansible section. A GitHub-hosted
runner has no network path to a machine behind a home router, and
handing CI standing credentials to an always-on personal box is a
tradeoff not worth taking for a portfolio project either way. What the
job actually proves: the images just pushed are pullable, and the
manifests + Helm charts bring up a fully working copy of the system
from nothing, on every push to main -- including a real functional
smoke test (register -> ingest -> Kafka -> Postgres -> read back)
through the deployed stack, not just "pods reached Ready."
