"""Resolve the dedicated sandbox runtimes without affecting the backend process."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
READY_MARKER = BACKEND_ROOT / ".sandbox-env-ready"
ENV_NAME = "xbots-sandbox"


def _environment_candidates() -> list[Path]:
    candidates: list[Path] = []
    configured = os.getenv("XBOTS_SANDBOX_ENV_PATH", "").strip()
    if configured:
        candidates.append(Path(configured))
    for envs_root in os.getenv("CONDA_ENVS_PATH", "").split(os.pathsep):
        if envs_root.strip():
            candidates.append(Path(envs_root) / ENV_NAME)
    candidates.extend([
        Path("D:/Conda/conda_envs") / ENV_NAME,
        Path.home() / ".conda" / "envs" / ENV_NAME,
        Path(sys.prefix).parent / ENV_NAME,
    ])
    return candidates


def sandbox_environment() -> Path | None:
    if not READY_MARKER.exists():
        return None
    return next((path for path in _environment_candidates() if path.is_dir()), None)


def _runtime_candidates(root: Path, name: str) -> list[Path]:
    names = {
        "python": [root / "python.exe"],
        "node": [root / "node.exe", root / "Library" / "bin" / "node.exe"],
        "java": [root / "Library" / "bin" / "java.exe", root / "bin" / "java.exe"],
        "javac": [root / "Library" / "bin" / "javac.exe", root / "bin" / "javac.exe"],
        "gcc": [root / "Library" / "mingw-w64" / "bin" / "gcc.exe", root / "Library" / "bin" / "gcc.exe"],
        "g++": [root / "Library" / "mingw-w64" / "bin" / "g++.exe", root / "Library" / "bin" / "g++.exe"],
    }
    return names.get(name, [])


def sandbox_runtime(name: str, fallback: str | None = None) -> str | None:
    root = sandbox_environment()
    if root:
        executable = next((path for path in _runtime_candidates(root, name) if path.is_file()), None)
        if executable:
            return str(executable)
    if fallback == "backend-python":
        return sys.executable
    return shutil.which(fallback or name)


def dedicated_environment_ready() -> bool:
    return sandbox_environment() is not None
