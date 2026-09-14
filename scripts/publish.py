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
    parser.add_argument("--tag", default="v1")
    parser.add_argument(
        "--push",
        action="store_true",
        help="docker push after build. Requires docker login.",
    )
    args = parser.parse_args()

    names = list(IMAGES) if args.image == "all" else [args.image]
    registry = args.registry.rstrip("/")
    for name in names:
        local = f"evt-{name}:local"
        remote = f"{registry}/evt-{name}:{args.tag}"
        context = IMAGES[name]
        print(f"Building {remote} from {context}")
        run(["docker", "build", "-t", local, "-t", remote, str(context)])
        if args.push:
            print(f"Pushing {remote}")
            run(["docker", "push", remote])
        else:
            print(f"Built {remote} (pass --push to publish)")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError:
        sys.exit("docker not found on PATH")
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
