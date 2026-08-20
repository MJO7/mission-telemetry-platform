# Ansible Provisioning

Takes a bare Ubuntu 24.04 host to a running k3s single-node cluster with
the Mission Telemetry Platform deployed and its rollouts verified.

The playbook is idempotent: **a second run reports `changed=0`** — not
asserted, actually run twice back-to-back against a real VM and
confirmed. Provisioning is code, not a wiki page.

This directory implements the original spec closely, but not
literally everywhere: five real problems below were only found by
actually running it, twice, against a genuinely bare node — not by
reading the YAML. Each is fixed and explained where it lives in the
task files, and summarized here.

---

## Requirements

**Control machine**

```bash
pip install --user ansible
ansible-galaxy collection install ansible.posix
```

**Target host**

- Ubuntu 24.04, 4 CPU / 8 GB RAM / 40 GB disk minimum
- SSH key access for a user with passwordless `sudo`

A local VM is fine for testing:

```bash
multipass launch --name mtp-node --cpus 4 --memory 8G --disk 40G 24.04
multipass info mtp-node          # note the IPv4 address

# Multipass gives you a VM, not SSH access to it -- generate a
# dedicated key (don't reuse a personal one for a throwaway demo box)
# and inject it yourself:
ssh-keygen -t ed25519 -f mtp_key -N "" -C "mtp-ansible"
multipass exec mtp-node -- bash -c \
  "mkdir -p ~/.ssh && echo '$(cat mtp_key.pub)' >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
```

Also required before running the playbook: `docker build` the four
service images (`api-service`, `ingest-service`, `web`, `processor`)
locally, tagged exactly as `mission-telemetry/<service>:local` — see
the root [`k8s/README.md`](../../k8s/README.md#quickstart-local-k3d)
quickstart for the exact build commands. Provisioning infrastructure is
this playbook's job; building application code isn't.

---

## Layout

```
deploy/ansible/
├── ansible.cfg
├── inventory.ini
├── playbook.yml
├── group_vars/
│   └── all.yml
└── roles/
    ├── base/tasks/main.yml      # packages, swap
    ├── k3s/tasks/main.yml       # install k3s, fetch kubeconfig
    └── app/tasks/main.yml       # Kafka/Redis, images, manifests, rollout
```

---

## Usage

```bash
cd deploy/ansible

ansible-inventory --list                 # verify inventory parses
ansible all -m ping                      # verify SSH + sudo
ansible-playbook playbook.yml --check    # dry run
ansible-playbook playbook.yml            # provision
ansible-playbook playbook.yml            # run again: changed=0
```

Then, from the control machine:

```bash
export KUBECONFIG=$PWD/kubeconfig
kubectl get pods -n mission-telemetry
```

---

## The five real problems, found by running it

**1. `ansible.cfg`'s `stdout_callback = yaml` doesn't start.**
`community.general`'s standalone `yaml` callback plugin was removed in
that collection's 12.0.0 — confirmed against the actual installed
version here (13.3.0), which refuses to launch with it set. Fixed with
the documented replacement: `stdout_callback = default` plus
`result_format = yaml` under `[callback_default]` — same readable
per-task YAML output, different (current) syntax.

**2. `--check` mode fails on a first-ever run.**
`k3s : Fetch kubeconfig to control machine` correctly never runs in
check mode (it would be a real write to the control machine) — but the
very next task then tries to rewrite a local file that, on a first dry
run, was never fetched. Fixed with `ignore_errors: "{{ ansible_check_mode }}"`
on that one task: a real run still fails hard on a genuine error; check
mode just accepts it has nothing to dry-run yet.

**3. `app` role never gets the four application images onto the node.**
Verified live: every app Deployment sat in `ImagePullBackOff` and every
"wait for rollout" item burned its full 180-second timeout, because
`mission-telemetry/*:local` isn't a real, pullable registry image —
nothing in the original role ever puts it on the node. Added: check
whether each image is already present in the node's containerd
(`k3s ctr images ls -q`), and only `docker save` → `synchronize` →
`k3s ctr images import` when at least one is missing.

**4. `app` role never provisions Kafka or Redis at all.**
Without them, `ingest-service`'s readiness probe (a real Kafka dial,
not a liveness stub) can never pass — the "wait for rollouts" step
cannot succeed no matter how long it waits. Added Redpanda + Redis via
their own Helm charts (same charts and values as the rest of this
project — see [`k8s/helm-values/`](../../k8s/helm-values)), run from
the control machine against the fetched kubeconfig, guarded by a
`helm status` check for the same idempotency policy as everything else
here. Also added the Kafka topics themselves and the `api-secrets`
Secret (openssl-generated, idempotent, never committed anywhere) —
neither of which the original role touched, and neither of which the
platform can start without. Two smaller, structural fixes needed for
these to actually work:
   - `k3s kubectl apply -f /opt/mtp/k8s/ -n ns` (flat, non-recursive)
     cannot apply this project's actual manifest layout: the real
     manifests live one level down in `k8s/base/`, and that directory
     also holds a `kustomization.yaml` and a secret *template* that
     `-f` would try to apply as raw resources and fail outright
     (verified: `no matches for kind "Kustomization"`). Changed to
     `-k /opt/mtp/k8s/base` (Kustomize mode), which reads that
     `kustomization.yaml` as the control file it is and applies
     exactly the 7 manifests it lists.
   - rsync (`ansible.posix.synchronize`) will not create a destination
     whose *parent* doesn't exist — verified on an actually bare node
     with no `/opt/mtp` at all. Added a plain `ansible.builtin.file`
     task to create it first.

**5. The given `changed_when` for `kubectl apply` produces false
positives, forever.**
`deployment.apps/api-service` and `statefulset.apps/postgres` report
`configured` on *every single run*, including two back-to-back runs
with nothing else touching the cluster in between — while `kubectl diff`
on the identical apply reports zero difference. Root cause: kubectl's
client-side apply computes its three-way-merge patch by comparing raw
strings, and this project's `resources.limits.cpu: 1000m` gets
normalized and stored by the API server as `"1"` — same value,
different string, which kubectl's patch logic treats as a real change
even though nothing observable differs. This is a documented upstream
kubectl quirk, not a mistake in the manifest. Fixed by keying
`changed_when` on `kubectl diff`'s exit code (0 = no real difference,
1 = real difference) instead of trusting `apply`'s own stdout text —
confirmed this actually resolves to `changed=0` on a clean second run.

Also fixed along the way, smaller: the given k3s role's
`fetch` + `replace`-in-place pattern breaks its own idempotency by
construction — fetching into the same file that then gets rewritten
means the *next* run's fetch compares the remote source (still
`127.0.0.1`) against a local file that's already been rewritten to the
real IP, so it always sees a "difference" and reports changed forever.
Split into `kubeconfig.raw` (what fetch touches, and only fetch) and
`kubeconfig` (written once, deterministically, from the raw file — a
`copy` task that only reports changed when its actual content differs).
The given spec also fetched to `../kubeconfig` while its own Usage
section reads back `$PWD/kubeconfig` from the same directory — an
internal inconsistency, fixed to the path that's actually documented
and actually used.

---

## Idempotency

Common causes of drift, and how this playbook avoids each one:

| Cause | How it's avoided here |
|---|---|
| `command`/`shell` tasks always report changed | Every one is guarded with a `stat`/`get`/`status` check + `when`, or explicit `changed_when` |
| `kubectl apply` output varies run to run | `changed_when` keyed on `kubectl diff`'s exit code, not apply's stdout text (see problem #5 above) |
| `become: true` on a localhost task | Dropped on every `delegate_to: localhost` task (kubeconfig rewrite, Helm repo/install) |
| `fetch` into a path something else then mutates | Split into a raw fetch target and a separately-written final file (see problem #5) |

---

## Teardown

```bash
ansible telemetry -m command -a /usr/local/bin/k3s-uninstall.sh --become
```

Or destroy the VM: `multipass delete mtp-node --purge`

---

## Troubleshooting

**`kubectl` can't reach the cluster from the control machine**
The fetched kubeconfig points at `127.0.0.1` until the rewrite task
runs. Confirm `server:` in `deploy/ansible/kubeconfig` (not
`kubeconfig.raw`, which is deliberately left untouched) matches
`ansible_host`.

**Rollout wait times out**
Two real causes hit during this build, in order of likelihood: (1) the
four application images were never actually `docker build`'t locally
under the exact `mission-telemetry/<service>:local` tags this playbook
looks for -- check `docker images | grep mission-telemetry`; (2)
Deployment names in `roles/app` must match your manifests -- check with
`kubectl get deploy -n mission-telemetry`.

**`synchronize` fails**
Requires `rsync` on both ends: `sudo apt install rsync`. Also requires
its destination's *parent* directory to already exist -- this playbook
creates `/opt/mtp` itself for exactly that reason (see problem #4).

**`ansible-playbook` can't authenticate**
This inventory points at a dedicated key
(`ansible_ssh_private_key_file=./mtp_key`), not your personal
`~/.ssh/id_rsa` -- make sure that key's public half actually landed in
the target's `~/.ssh/authorized_keys` (see Requirements above).

---

## Deliberately not done (optional hardening, per the original spec)

- **`ansible-lint` in CI** — not wired up. Would catch `command`-instead-
  of-module patterns going forward; everything here was hand-verified
  live instead, which is a real but non-repeating check.
- **`ansible-vault`** — not used, on purpose rather than by omission:
  the `api-secrets` Secret is generated at runtime with `openssl rand`
  and only ever exists in the target cluster and its own etcd, never as
  a value anyone had to choose or store anywhere, encrypted or not.
  Vault is the right tool when a secret's *value* needs to be decided
  ahead of time and shared; generating it fresh on the node removes
  that need entirely for this one.
- **A CI job running `--check --diff` against a container** — the
  strongest available proof of the idempotency claim (continuous, not
  a one-time demonstration), genuinely worth doing, not done in this
  pass.
