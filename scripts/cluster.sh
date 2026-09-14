#!/usr/bin/env bash
# Stamp-out and teardown for the local kind Cluster.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLUSTER_NAME="evt"
KUBECONFIG_PATH="${ROOT}/.kube/config"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    echo "Install Docker, kind, and kubectl, then re-run." >&2
    exit 1
  fi
}

kind_env() {
  mkdir -p "$(dirname "${KUBECONFIG_PATH}")"
  export KUBECONFIG="${KUBECONFIG_PATH}"
}

create_cluster() {
  if kind get clusters 2>/dev/null | grep -qx "${CLUSTER_NAME}"; then
    echo "Cluster ${CLUSTER_NAME} already exists."
  else
    kind create cluster --config "${ROOT}/kind/cluster.yaml" --kubeconfig "${KUBECONFIG_PATH}"
  fi
  kind_env
  kubectl cluster-info --context "kind-${CLUSTER_NAME}"
}

build_and_load() {
  docker build -t evt-backend:local "${ROOT}/apps/backend"
  docker build -t evt-frontend:local "${ROOT}/apps/frontend"
  kind load docker-image evt-backend:local --name "${CLUSTER_NAME}"
  kind load docker-image evt-frontend:local --name "${CLUSTER_NAME}"
}

apply_app() {
  kind_env
  kubectl apply -f "${ROOT}/k8s"
  kubectl --namespace evt rollout status deployment/backend --timeout=90s
  kubectl --namespace evt rollout status deployment/frontend --timeout=90s
}

up() {
  need docker
  need kind
  need kubectl
  create_cluster
  build_and_load
  apply_app
  echo
  echo "Frontend: http://127.0.0.1:8080"
  echo "kubeconfig: ${KUBECONFIG_PATH}"
}

down() {
  need kind
  if kind get clusters 2>/dev/null | grep -qx "${CLUSTER_NAME}"; then
    kind delete cluster --name "${CLUSTER_NAME}"
  else
    echo "Cluster ${CLUSTER_NAME} does not exist."
  fi
  rm -f "${KUBECONFIG_PATH}"
}

status() {
  need kind
  need kubectl
  if ! kind get clusters 2>/dev/null | grep -qx "${CLUSTER_NAME}"; then
    echo "Cluster ${CLUSTER_NAME} is not running."
    exit 1
  fi
  kind_env
  kubectl --namespace evt get pods,svc
}

usage() {
  echo "Usage: $0 <up|down|status>" >&2
  exit 1
}

cmd="${1:-}"
case "${cmd}" in
  up) up ;;
  down) down ;;
  status) status ;;
  *) usage ;;
esac
