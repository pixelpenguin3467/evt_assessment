#!/usr/bin/env python3
"""Stamp-out and teardown for the local kind Cluster."""
from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / ".tools"
LEGACY_KUBECONFIG = ROOT / ".kube" / "config"
CLUSTER = "evt"
KUBE_CONTEXT = f"kind-{CLUSTER}"
KIND_VERSION = "v0.33.0"
KUBECTL_VERSION = "v1.36.1"


def die(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def os_arch() -> tuple[str, str]:
    system = platform.system()
    machine = platform.machine().lower()
    os_name = {"Linux": "linux", "Darwin": "darwin", "Windows": "windows"}.get(system)
    arch = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }.get(machine)
    if not os_name or not arch:
        die(f"Unsupported platform: {system} {machine}")
    return os_name, arch


OS_NAME, ARCH = os_arch()
os.environ["PATH"] = str(TOOLS) + os.pathsep + os.environ.get("PATH", "")


def tool_file(name: str) -> str:
    return f"{name}.exe" if OS_NAME == "windows" else name


def run(args: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=True, text=True, **kwargs)


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url}")
    tmp = dest.with_name(dest.name + ".tmp")
    with urllib.request.urlopen(url) as src, open(tmp, "wb") as out:
        shutil.copyfileobj(src, out)
    if OS_NAME != "windows":
        tmp.chmod(tmp.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    tmp.replace(dest)


def ensure_cli(name: str, url: str) -> None:
    if shutil.which(name):
        return
    print(f"{name} not found; installing into {TOOLS}")
    download(url, TOOLS / tool_file(name))
    if not shutil.which(name):
        die(f"Installed {name} to {TOOLS} but it is not on PATH")


def ensure_kind() -> None:
    ensure_cli(
        "kind",
        f"https://kind.sigs.k8s.io/dl/{KIND_VERSION}/kind-{OS_NAME}-{ARCH}",
    )


def ensure_kubectl() -> None:
    ensure_cli(
        "kubectl",
        f"https://dl.k8s.io/release/{KUBECTL_VERSION}/bin/{OS_NAME}/{ARCH}/{tool_file('kubectl')}",
    )


def docker_permission_hint() -> str:
    """Advise how to get socket access. Group membership is a Linux Engine thing."""
    lines = [
        "Docker is running but this user cannot use the daemon socket.",
        "Do not use sudo for stamp-out or kubectl — that writes kubeconfig as root.",
    ]
    if OS_NAME == "linux":
        try:
            import grp

            docker_grp = grp.getgrnam("docker")
        except KeyError:
            lines.append(
                "There is no 'docker' group. Install Docker Engine for this distro, "
                "then add your user to the group it documents."
            )
        except Exception:
            lines.append(
                'Add your user to the docker group, then re-login: sudo usermod -aG docker "$USER"'
            )
        else:
            if docker_grp.gr_gid in os.getgroups():
                lines.append(
                    "This user is already in the docker group, but this session does not "
                    "have it yet. Log out and back in, or run: newgrp docker"
                )
            else:
                lines.extend(
                    [
                        "Once, then log out and back in (or: newgrp docker):",
                        '  sudo usermod -aG docker "$USER"',
                    ]
                )
    elif OS_NAME == "darwin":
        lines.append(
            "On macOS, start Docker Desktop and wait until it is running. "
            "There is usually no docker group to join."
        )
    else:
        lines.append(
            "On Windows, start Docker Desktop and run this script as your user "
            "(not an elevated shell), unless Docker Desktop itself requires that."
        )
    return "\n".join(lines)


def ensure_engine() -> None:
    if not shutil.which("docker"):
        extra = ""
        if shutil.which("podman"):
            extra = (
                " Podman is on PATH, but this script does not use it. "
                "Install Docker Engine, or start dockerd if you use a Podman docker shim."
            )
        die(
            "Docker is required (kind runs Cluster nodes as containers)."
            + extra
            + "\nInstall Docker Engine: https://docs.docker.com/engine/install/"
            + "\nThis script will not install a container engine (needs root and a running daemon)."
        )
    probe = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode == 0:
        return
    err = (probe.stderr or probe.stdout or "").lower()
    if "permission denied" in err or "access is denied" in err:
        die(docker_permission_hint())
    die(
        "Docker is installed but the daemon is not reachable. Start it and re-run.\n"
        f"{probe.stderr or probe.stdout}"
    )


def kubectl(args: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return run(["kubectl", "--context", KUBE_CONTEXT, *args], **kwargs)


def export_kubeconfig() -> None:
    """Merge this Cluster into the default kubeconfig so plain kubectl works."""
    run(["kind", "export", "kubeconfig", "--name", CLUSTER])


def kind_clusters() -> list[str]:
    result = subprocess.run(
        ["kind", "get", "clusters"],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def require_cluster() -> None:
    if CLUSTER not in kind_clusters():
        die(
            f"Cluster {CLUSTER} is not running.\n"
            "kubectl defaulting to http://localhost:8080 means there is no kubeconfig "
            "(no API server). --validate=false cannot help.\n"
            "Stamp out first: python3 scripts/cluster.py up"
        )


def create_cluster() -> None:
    if CLUSTER in kind_clusters():
        print(f"Cluster {CLUSTER} already exists.")
    else:
        run(
            [
                "kind",
                "create",
                "cluster",
                "--config",
                str(ROOT / "kind" / "cluster.yaml"),
            ]
        )
    export_kubeconfig()
    kubectl(["cluster-info"])


def build_and_load() -> None:
    run(["docker", "build", "-t", "evt-backend:local", str(ROOT / "apps" / "backend")])
    run(["docker", "build", "-t", "evt-frontend:local", str(ROOT / "apps" / "frontend")])
    run(["kind", "load", "docker-image", "evt-backend:local", "--name", CLUSTER])
    run(["kind", "load", "docker-image", "evt-frontend:local", "--name", CLUSTER])


def apply_app() -> None:
    kubectl(["apply", "-f", str(ROOT / "k8s")])
    kubectl(
        [
            "--namespace",
            "evt",
            "rollout",
            "status",
            "deployment/backend",
            "--timeout=90s",
        ]
    )
    kubectl(
        [
            "--namespace",
            "evt",
            "rollout",
            "status",
            "deployment/frontend",
            "--timeout=90s",
        ]
    )


def up() -> None:
    ensure_engine()
    ensure_kind()
    ensure_kubectl()
    create_cluster()
    build_and_load()
    apply_app()
    print()
    print("Frontend: http://127.0.0.1:8080")
    print(f"kubectl context: {KUBE_CONTEXT}")
    print(f"Re-apply manifests: kubectl --context {KUBE_CONTEXT} apply -f k8s")


def down() -> None:
    ensure_kind()
    if CLUSTER in kind_clusters():
        run(["kind", "delete", "cluster", "--name", CLUSTER])
    else:
        print(f"Cluster {CLUSTER} does not exist.")
    LEGACY_KUBECONFIG.unlink(missing_ok=True)


def status() -> None:
    ensure_kind()
    ensure_kubectl()
    require_cluster()
    export_kubeconfig()
    kubectl(["--namespace", "evt", "get", "pods,svc"])


def apply() -> None:
    ensure_kind()
    ensure_kubectl()
    require_cluster()
    export_kubeconfig()
    apply_app()


def main() -> None:
    cmds = {"up": up, "down": down, "status": status, "apply": apply}
    if len(sys.argv) != 2 or sys.argv[1] not in cmds:
        die(f"Usage: {sys.argv[0]} <up|down|status|apply>")
    cmds[sys.argv[1]]()


if __name__ == "__main__":
    main()
