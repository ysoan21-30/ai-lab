"""Secure temporary file handling for uploads.

Files are written to a dedicated upload directory with randomly generated
names (no user-controlled path components) and deleted immediately after
processing, mitigating path traversal and stale-data risks.
"""
from __future__ import annotations

import os
import uuid

from app.core.config import settings

os.makedirs(settings.upload_dir, exist_ok=True)


def safe_temp_path(suffix: str = "") -> str:
    safe_suffix = "".join(c for c in suffix if c.isalnum() or c in (".", "_", "-"))[:20]
    filename = f"{uuid.uuid4().hex}{safe_suffix}"
    return os.path.join(settings.upload_dir, filename)


def cleanup_file(path: str) -> None:
    try:
        if path and os.path.exists(path) and os.path.commonpath([path, settings.upload_dir]) == settings.upload_dir:
            os.remove(path)
    except (OSError, ValueError):
        pass
