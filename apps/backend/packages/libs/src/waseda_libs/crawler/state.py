"""Checkpoint state for resuming interrupted crawls."""

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

SAVE_INTERVAL = 100  # save every N completed pKeys


class CrawlState:
    """Tracks completed pKeys and persists state to a JSON file."""

    def __init__(self, checkpoint_path: Path) -> None:
        self.checkpoint_path = checkpoint_path
        self.completed: set[str] = self._load()
        self._unsaved_count = 0

    def _load(self) -> set[str]:
        if self.checkpoint_path.exists():
            try:
                data = json.loads(self.checkpoint_path.read_text())
                completed = set(data.get("completed", []))
                log.info(
                    f"Loaded checkpoint from {self.checkpoint_path}: "
                    f"{len(completed)} completed pKeys"
                )
                return completed
            except Exception as e:
                log.warning(f"Failed to load checkpoint: {e}")
        return set()

    def save(self) -> None:
        try:
            self.checkpoint_path.write_text(
                json.dumps({"completed": list(self.completed)}, indent=2)
            )
            self._unsaved_count = 0
        except Exception as e:
            log.error(f"Failed to save checkpoint: {e}")

    def mark_done(self, pkey: str) -> None:
        self.completed.add(pkey)
        self._unsaved_count += 1
        if self._unsaved_count >= SAVE_INTERVAL:
            self.save()

    def is_done(self, pkey: str) -> bool:
        return pkey in self.completed
