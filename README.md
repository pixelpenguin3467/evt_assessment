# EVT Kubernetes assessment

Stamp out a local Kubernetes Cluster with **kind**, install a small Frontend and Backend, and tear it all down again.

kind is a Kubernetes SIGs CLI that creates a Cluster in Docker when you run the script. It is not Rancher Desktop (a desktop product that bundles a Cluster). k3s is also acceptable per the brief; we used kind so create/destroy stays a pair of commands. If the reviewers prefer k3s, the App manifests do not need to change.

## Prerequisites

- Docker (daemon running)
- [kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installation)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)

## Stamp-out

```bash
./scripts/cluster.sh up
```

That will:

1. Create a kind Cluster named `evt` (or reuse it if it already exists)
2. Build the Frontend and Backend images and load them into the Cluster
3. Apply the App manifests
4. Print `http://127.0.0.1:8080` for the Frontend

Open that URL. The page is the Frontend; the status line is an HTTP GET from the Frontend container to `http://backend/` (the in-cluster DNS name of the Backend Service).

kubeconfig is written to `.kube/config` (gitignored).

```bash
export KUBECONFIG="$PWD/.kube/config"
./scripts/cluster.sh status
```

## Teardown

```bash
./scripts/cluster.sh down
```

Deletes the kind Cluster and the local kubeconfig file.

## What got installed (addons)

kind brings a working Cluster with its defaults. This repo does **not** install extra addons.

| Component | Why it is there |
| --- | --- |
| **kindnet** | CNI so Pods can reach Services (including `backend`) |
| **kube-proxy** | Service ClusterIP / NodePort |
| **CoreDNS** | In-cluster DNS (`backend.evt.svc.cluster.local`) |
| **kind-control-plane** | Single node (control plane + workloads) |

The Frontend Service is a NodePort (`30080`) mapped to host port `8080` in `kind/cluster.yaml` so you can use a browser without `kubectl port-forward`.

## Layout

```
apps/frontend   Frontend image (nginx + site; proxies `/api/backend` to the Backend)
apps/backend    Backend image (nginx; `GET /` returns "The backend is up")
k8s/            Namespace, Deployments, Services
kind/           kind Cluster config
scripts/        Stamp-out / teardown
```

Images are tagged `evt-frontend:local` and `evt-backend:local` and loaded into kind (`imagePullPolicy: Never`). Publishing to Docker Hub or public ECR is still required by the brief and is not done in this first pass.

## Repeatability

`up` is safe to run more than once: existing Cluster is reused, images are rebuilt and reloaded, manifests are applied. `down` then `up` is a clean stamp-out from scratch.
