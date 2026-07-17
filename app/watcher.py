"""Watches vault/inbox/ and normalizes anything dropped there (docs/03-
engineering-build-spec.md §6.1). Two modes:

    python3 -m app.watcher --once     # process what's there now, exit (good for cron)
    python3 -m app.watcher            # stay running, process as things land (Syncthing target)

Failures never lose the input: a file that fails to normalize is moved to
inbox/_failed/ with the error logged, not deleted.
"""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from app.normalizer import process_drop

logger = logging.getLogger(__name__)

IGNORED_NAMES = {".gitkeep"}


def _should_process(path: Path) -> bool:
    return path.is_file() and path.name not in IGNORED_NAMES and not path.name.startswith(".")


def _safe_process(vault_path: Path, path: Path, db) -> None:
    try:
        process_drop(vault_path, path, db=db)
    except Exception as exc:  # noqa: BLE001 - deliberately broad, see module docstring
        failed_dir = vault_path / "inbox" / "_failed"
        failed_dir.mkdir(parents=True, exist_ok=True)
        try:
            path.replace(failed_dir / path.name)
        except OSError:
            pass  # already moved / gone — don't crash the watcher over cleanup
        logger.error("failed to normalize '%s': %s (moved to inbox/_failed/)", path.name, exc)


def process_existing(vault_path: Path, db=None) -> int:
    inbox = vault_path / "inbox"
    count = 0
    for path in sorted(inbox.iterdir()):
        if _should_process(path):
            _safe_process(vault_path, path, db)
            count += 1
    return count


def watch(vault_path: Path, db=None) -> None:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    class InboxHandler(FileSystemEventHandler):
        def on_created(self, event):
            if event.is_directory:
                return
            path = Path(event.src_path)
            if not _should_process(path):
                return
            time.sleep(1)  # let the write/sync finish before reading it
            _safe_process(vault_path, path, db)

    inbox = vault_path / "inbox"
    observer = Observer()
    observer.schedule(InboxHandler(), str(inbox), recursive=False)
    observer.start()
    logger.info("watching %s ... (Ctrl+C to stop)", inbox)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default="vault")
    parser.add_argument("--once", action="store_true", help="process existing files once, then exit")
    parser.add_argument("--no-db", action="store_true", help="skip embedding writes (no .env yet)")
    args = parser.parse_args()

    db = None
    if not args.no_db:
        from app.common.db import DB

        db = DB()

    vault_path = Path(args.path)
    if args.once:
        n = process_existing(vault_path, db=db)
        print(f"processed {n} item(s).")
    else:
        watch(vault_path, db=db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
