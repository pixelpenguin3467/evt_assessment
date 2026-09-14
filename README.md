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
3. Build the Frontend and Backend images and load them into the Cluster
4. Apply the App manifests
5. Print `http://127.0.0.1:8080` for the Frontend

Open that URL. The page is the Frontend; the status line is an HTTP GET from the Frontend container to `http://backend/` (the in-cluster DNS name of the Backend Service).

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

The Frontend Service is a NodePort (`30080`) mapped to host port `8080` in `kind/cluster.yaml` so you can use a browser without `kubectl port-forward`.

## Website image (brief item 2)

`apps/frontend` is a custom nginx image: static template (`html/`) plus a reverse proxy to the Backend. Stamp-out builds it as `evt-frontend:local` and loads it into kind.

To publish to Docker Hub (daemon running, `docker login` already done):

```bash
python3 scripts/publish.py frontend --registry docker.io/<your-dockerhub-user> --tag v1 --push
```

That does not change stamp-out. Kind still uses the local tag until the YAML image fields are pointed at the public name.

## Manifests (brief item 4)

Stamp-out applies raw YAML in `k8s/` (`kubectl apply -f k8s`). That is the supported install path. Frontend and Backend containers set CPU/memory **requests** (25m / 32Mi) and **limits** (100m / 64Mi) so a noisy neighbor cannot eat the kind node. The Helm chart uses the same values.

Optional extra — same App as a Helm chart:

```bash
helm upgrade --install evt helm/evt-app
```

Default values match the local kind tags (`pullPolicy: Never`). After Publish, override images, for example:

```bash
helm upgrade --install evt helm/evt-app \
  --set frontend.image=docker.io/<user>/evt-frontend \
  --set frontend.tag=v1 \
  --set frontend.pullPolicy=IfNotPresent \
  --set backend.image=docker.io/<user>/evt-backend \
  --set backend.tag=v1 \
  --set backend.pullPolicy=IfNotPresent
```

Do not Helm-install on top of a Cluster that already has the YAML objects unless you are replacing that install.

## Layout

```
apps/frontend   Website image (nginx + template; proxies `/api/backend` to the Backend)
apps/backend    Backend image (nginx; `GET /` returns "The backend is up")
k8s/            YAML manifests (Namespace, Deployments, Services)
helm/evt-app    Optional Helm chart (same App)
kind/           kind Cluster config
scripts/        Stamp-out (`cluster.py`) and Publish (`publish.py`)
```

Images used by stamp-out are `evt-frontend:local` and `evt-backend:local` (`imagePullPolicy: Never`). Public registry publish is `scripts/publish.py` (needs Docker Hub user and `docker login`).

## Repeatability

`up` is safe to run more than once: existing Cluster is reused, images are rebuilt and reloaded, manifests are applied. `down` then `up` is a clean stamp-out from scratch.
