import threading
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app.indexer import index_catalogue


class _CatalogueHandler(FileSystemEventHandler):
    def __init__(self, photos_dir: Path, conn_factory: Callable, debounce: float = 1.0):
        self._photos_dir = photos_dir
        self._conn_factory = conn_factory
        self._debounce = debounce
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def on_any_event(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        try:
            rel = path.relative_to(self._photos_dir)
        except ValueError:
            return
        if not rel.parts:
            return
        slug = rel.parts[0]
        catalogue_dir = self._photos_dir / slug

        with self._lock:
            if slug in self._timers:
                self._timers[slug].cancel()
            timer = threading.Timer(self._debounce, self._reindex, args=[slug, catalogue_dir])
            self._timers[slug] = timer
            timer.start()

    def _reindex(self, slug: str, catalogue_dir: Path) -> None:
        with self._lock:
            self._timers.pop(slug, None)
        conn = self._conn_factory()
        try:
            index_catalogue(catalogue_dir, conn)
        finally:
            conn.close()


def start_watcher(photos_dir: Path, conn_factory: Callable) -> Observer:
    handler = _CatalogueHandler(photos_dir, conn_factory)
    observer = Observer()
    observer.schedule(handler, str(photos_dir), recursive=True)
    observer.start()
    return observer
