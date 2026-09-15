# EVT Kubernetes assessment

Stamp out a local Kubernetes Cluster with **kind**, install a small Frontend and Backend, and tear it all down again.

kind is a Kubernetes SIGs CLI that creates a Cluster in Docker when you run the stamp-out. It is not Rancher Desktop (a desktop product that bundles a Cluster). k3s is also acceptable per the brief; we used kind so create/destroy stays a pair of commands. If the reviewers prefer k3s, the App manifests do not need to change.

## Prerequisites

**You install:** Python 3.9+ and Docker Engine (daemon running). Your user must be able to run `docker info` **without sudo** (membership in the `docker` group). kind nodes are containers; the stamp-out will not install a container engine. Do not run stamp-out or kubectl with sudo: kubeconfig would land in `/root/.kube` and your user kubectl would not see the Cluster. Podman is detected only so we can say it is not used.

**The stamp-out can install:** [kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installation) `v0.33.0` and [kubectl](https://kubernetes.io/docs/tasks/tools/) `v1.36.1` into `.tools/` if they are not already on `PATH`. That needs network. Existing binaries are left alone. Linux, macOS, and Windows binaries are selected automatically.

On Windows, use Docker Desktop (WSL2 backend is fine) and run the same commands from PowerShell, cmd, or WSL.

## Stamp-out

```bash
python3 scripts/cluster.py up
```

Windows: `py -3 scripts\cluster.py up`

That will:

1. Check Docker; download kind and kubectl into `.tools/` if missing
2. Create a kind Cluster named `evt` (or reuse it if it already exists)
3. Apply the App manifests; the node **pulls** the public Hub images
4. Print `http://127.0.0.1:8080` (HTTP) and `https://127.0.0.1:8443` (HTTPS, self-signed)

Open the HTTP URL for the easy path. HTTPS uses a **self-signed** cert generated in the Frontend Pod at start (no private key in git or the image). Browsers will warn; `curl -k https://127.0.0.1:8443` is expected. Backend status is filled in by nginx (SSI) with an HTTP GET to `http://backend/` in-cluster — not a browser `fetch`, which fails on some browsers against a self-signed origin.

If the Cluster already existed before HTTPS port mapping was added, `down` then `up` so kind picks up host port 8443.

kubeconfig is merged into the default file (`~/.kube/config`) as context `kind-evt`. After `up`:

```bash
kubectl --context kind-evt apply -f k8s
python3 scripts/cluster.py status
```

`kubectl apply -f k8s` with no Cluster (or no kubeconfig) talks to **http://localhost:8080**, kubectl’s leftover default API address. That is not this App, and `--validate=false` will not create an API server. Stamp out first (`python3 scripts/cluster.py up`). Host port 8080 on a running Cluster is the Frontend website, not the Kubernetes API.

## Teardown

```bash
python3 scripts/cluster.py down
```

Deletes the kind Cluster and its kubeconfig context.

## What got installed (addons)

kind brings a working Cluster with its defaults. This repo does **not** install extra addons.

| Component | Why it is there |
| --- | --- |
| **kindnet** | CNI so Pods can reach Services (including `backend`) |
| **kube-proxy** | Service ClusterIP / NodePort |
| **CoreDNS** | In-cluster DNS (`backend.evt.svc.cluster.local`) |
| **kind-control-plane** | Single node (control plane + workloads) |

The Frontend Service is a NodePort (`30080` → host `8080` HTTP, `30443` → host `8443` HTTPS) in `kind/cluster.yaml`.

## Security choices

These are meant to show intent on a local kind Cluster, not a production PKI.

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

Stamp-out applies those images (`imagePullPolicy: Always`). Kind pulls from Hub; it does not `kind load` a local build. The node needs network to Docker Hub.

To republish after image changes (`docker login` first):

```bash
python3 scripts/publish.py all --registry docker.io/pixelpenguin31 --push
```

## Manifests (brief item 4)

YAML (`k8s/`) is the default App install. Helm (`helm/evt-app`) is the extra path. **Use one or the other**, not both, on the same Cluster.

Cluster only (no App), then Helm on top:

```bash
python3 scripts/cluster.py up --cluster-only
python3 scripts/cluster.py helm        # install / upgrade release evt
python3 scripts/cluster.py helm-down   # uninstall App; Cluster stays
python3 scripts/cluster.py down        # delete the kind Cluster
```

Stamp-out Cluster + YAML in one step:

```bash
python3 scripts/cluster.py up
```

Stamp-out Cluster + Helm in one step:

```bash
python3 scripts/cluster.py up --helm
```

On an existing Cluster:

```bash
python3 scripts/cluster.py apply   # YAML
python3 scripts/cluster.py helm    # Helm release "evt"
```

Or by hand: `helm upgrade --install evt ./helm/evt-app --wait`

Frontend and Backend set CPU/memory **requests** (25m / 32Mi) and **limits** (100m / 64Mi). Chart values match `k8s/`. `helm lint ./helm/evt-app` is clean. `helm uninstall evt` removes the App; `python3 scripts/cluster.py down` removes the Cluster.

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
