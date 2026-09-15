# EVT Kubernetes assessment

Creates a local Kubernetes cluster with **kind**, install a small Frontend and Backend, and tear it all down again.

## Prerequisites

**Pre-install:** Python 3.9+, Docker with its service or engine running and Helm if wanting to split cluster and application deployments. Linux users should ensure membership in the `docker` group so that sudo is not necessary for execution (can add your user to `docker` group with: sudo usermod -aG docker "$USER"). Running with sudo should be avoided so that kubeconfig is updated in your `.kube` directory and not in root.

**Deployment can install:** [kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installation) `v0.33.0` and [kubectl](https://kubernetes.io/docs/tasks/tools/) `v1.36.1` into `.tools/` if they are not already on `PATH` and network is available. Linux, macOS, and Windows binaries are selected automatically.

On Windows, ensure virtualization is properly enabled along with WSL2, have Docker Desktop installed with engine running and run the same commands from PowerShell, cmd, or WSL.

## Quick-Start

```bash
python3 scripts/cluster.py up
```

Windows: 
```bash
py scripts\cluster.py up
```

That will:

1. Check Docker; download kind and kubectl into `.tools/` if missing
2. Create a kind Cluster named `evt` (or reuse it if it already exists)
3. Apply the App manifests; the node **pulls** the public Hub images
4. Print `http://127.0.0.1:8080` (HTTP) and `https://127.0.0.1:8443` (HTTPS, self-signed)

Open the HTTP URL for the easy path. HTTPS uses a **self-signed** cert generated in the Frontend Pod at start (no private key in git or the image). Browsers warning on the self-signed cert for `https://127.0.0.1:8443` is expected. Backend status is filled in by nginx (SSI) with an HTTP GET to `http://backend/` in-cluster — not a browser `fetch`, which fails on some browsers against a self-signed origin.

kubeconfig is merged into the default file (`~/.kube/config`) as context `kind-evt` automatically during an `up`:

```bash
kubectl --context kind-evt apply -f k8s
```

Status of the cluster can be checked with:

```bash
python3 scripts/cluster.py status
```

Windows: 
```bash
py scripts\cluster.py status
```

## Teardown

```bash
python3 scripts/cluster.py down
```

Windows: 
```bash
py scripts\cluster.py down
```

Deletes the app containers, kind Cluster and its kubeconfig context.

## Additional Install Options

A quick-start `up` uses the k8s YAML manifests for cluster and app install. Helm (`helm/evt-app`) is available as well when doing an initial `cluster-only` deploy to allow app only install and teardown.

Cluster only (no App), then Helm on top:

```bash
python3 scripts/cluster.py up --cluster-only
python3 scripts/cluster.py helm        # install / upgrade release evt
python3 scripts/cluster.py helm-down   # uninstall App; Cluster stays
python3 scripts/cluster.py down        # delete the kind Cluster
```

Deploy Cluster + YAML in one step:

```bash
python3 scripts/cluster.py up
```

Deploy Cluster + Helm in one step:

```bash
python3 scripts/cluster.py up --helm
```

On an existing Cluster:

```bash
python3 scripts/cluster.py apply   # YAML
python3 scripts/cluster.py helm    # Helm release "evt"
```

Or by hand: `helm upgrade --install evt ./helm/evt-app --wait`

Frontend and Backend set CPU/memory **requests** (25m / 32Mi) and **limits** (100m / 64Mi).

## What is included

kind brings a working Cluster with its defaults. This repo does **not** install extra addons.

| Component | Purpose |
| --- | --- |
| **kindnet** | CNI so Pods can reach Services (including `backend`) |
| **kube-proxy** | Service ClusterIP / NodePort |
| **CoreDNS** | In-cluster DNS (`backend.evt.svc.cluster.local`) |
| **kind-control-plane** | Single node (control plane + workloads) |

The Frontend Service is a NodePort (`30080` → host `8080` HTTP, `30443` → host `8443` HTTPS) in `kind/cluster.yaml`.

## Security considerations

| Control | Why |
| --- | --- |
| **Non-root (`nginx-unprivileged`, uid 101)** | Containers do not run as root; listen on 8080/8443 instead of privileged 80. |
| **Dropped capabilities, no privilege escalation, RuntimeDefault seccomp** | Shrink the container kernel attack surface. |
| **Read-only root filesystem + emptyDir for `/tmp`, cache, run** | The image cannot write its own layers; TLS certs and nginx scratch space go in emptyDir. |
| **HTTPS on the Frontend** | TLS in nginx with a cert created at Pod start. No cert-manager/Let’s Encrypt: kind has no public DNS. |
| **HTTP kept on 8080** | Reviewers can still use the site without clicking through a certificate warning. |
| **No extra Cluster addons** | NetworkPolicy would need Calico (kindnet does not enforce it). Ingress/cert-manager would be more moving parts than this App needs. |

`server_tokens off` is set in nginx so the version is not advertised.

## Website and Backend images (brief items 2–3)

Custom nginx images, public on Docker Hub:

- [pixelpenguin31/evt-frontend](https://hub.docker.com/r/pixelpenguin31/evt-frontend) (`latest`)
- [pixelpenguin31/evt-backend](https://hub.docker.com/r/pixelpenguin31/evt-backend) (`latest`)

Anyone can pull them without logging in:

```bash
docker pull docker.io/pixelpenguin31/evt-frontend:latest
docker pull docker.io/pixelpenguin31/evt-backend:latest
```

Deploy applies those images (`imagePullPolicy: Always`). Kind pulls from Hub; it does not `kind load` a local build. The node needs network to Docker Hub.

Tooling to publish own images for use with this package is available with:

```bash
python3 scripts/publish.py all --registry docker.io/USERNAME --push
```
Substitue USERNAME with your own Docker Hub user

## Layout

```
apps/frontend   Website image (nginx + template; proxies `/api/backend` to the Backend)
apps/backend    Backend image (nginx; `GET /` returns "The backend is up")
k8s/            YAML manifests (Namespace, Deployments, Services)
helm/evt-app    Optional Helm chart (same App)
kind/           kind Cluster config
scripts/        Stamp-out (`cluster.py`) and Publish (`publish.py`)
```

Images in YAML/Helm are `docker.io/pixelpenguin31/evt-frontend:latest` and `docker.io/pixelpenguin31/evt-backend:latest` (`imagePullPolicy: Always`). `scripts/publish.py` rebuilds and pushes those tags.

## Repeatability

`up` is safe to run more than once: existing Cluster is reused, images are rebuilt and reloaded, manifests are applied. `down` then `up` is a clean stamp-out from scratch.
