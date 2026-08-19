#!/usr/bin/env python
"""Deletes temp upload files older than FILE_RETENTION_HOURS.

Uploaded files are already deleted right after processing in the normal
flow; this script is a safety-net cron job for anything left behind by a
crashed request, per the security requirement to enforce a retention
policy on temporary files.

Intended to run periodically, e.g. via cron:
    0 * * * * python scripts/cleanup_temp_files.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.config import settings  # noqa: E402


def main():
    upload_dir = Path(settings.upload_dir)
    if not upload_dir.exists():
        return
    cutoff = time.time() - settings.file_retention_hours * 3600
    removed = 0
    for path in upload_dir.iterdir():
        if path.is_file() and path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)
            removed += 1
    print(f"Removed {removed} stale temp file(s) from {upload_dir}.")


if __name__ == "__main__":
    main()
