#!/usr/bin/env python3
"""Build (and optionally push) App images to a public registry."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGES = {
    "frontend": ROOT / "apps" / "frontend",
    "backend": ROOT / "apps" / "backend",
}
PLATFORMS = "linux/amd64,linux/arm64"


def run(args: list[str]) -> None:
    subprocess.run(args, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", choices=("frontend", "backend", "all"))
    parser.add_argument(
        "--registry",
        required=True,
        help="Registry prefix, e.g. docker.io/myuser or public.ecr.aws/alias",
    )
    parser.add_argument("--tag", default="latest")
    parser.add_argument(
        "--push",
        action="store_true",
        help="Multi-arch build (amd64+arm64) and push. Requires docker login and buildx.",
    )
    parser.add_argument(
        "--platform",
        default=PLATFORMS,
        help=f"Platforms for --push (default {PLATFORMS})",
    )
    args = parser.parse_args()

    names = list(IMAGES) if args.image == "all" else [args.image]
    registry = args.registry.rstrip("/")
    for name in names:
        local = f"evt-{name}:local"
        remote = f"{registry}/evt-{name}:{args.tag}"
        context = str(IMAGES[name])
        if args.push:
            print(f"Building {remote} for {args.platform} and pushing")
            run(
                [
                    "docker",
                    "buildx",
                    "build",
                    "--platform",
                    args.platform,
                    "-t",
                    remote,
                    "--push",
                    context,
                ]
            )
        else:
            print(f"Building {local} and {remote} for this host architecture")
            run(["docker", "build", "-t", local, "-t", remote, context])
            print(f"Built {remote} (pass --push for linux/amd64,linux/arm64)")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError:
        sys.exit("docker not found on PATH")
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
