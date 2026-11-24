"""Append-only storage of confirmed booking requests in bookings.csv."""

from __future__ import annotations

import csv
import threading
from datetime import UTC, datetime
from pathlib import Path

CSV_FIELDS = ["intent", "date", "time", "guests", "name", "phone", "code", "created_at"]


class CsvFormatError(RuntimeError):
    """The existing file has an unexpected header; we refuse to write into it."""


class BookingsCsv:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def _check_or_create(self) -> None:
        if not self.path.exists() or self.path.stat().st_size == 0:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # utf-8-sig: Excel opens Cyrillic correctly
            with self.path.open("w", encoding="utf-8-sig", newline="") as f:
                csv.DictWriter(f, fieldnames=CSV_FIELDS).writeheader()
            return
        with self.path.open("r", encoding="utf-8-sig", newline="") as f:
            header = next(csv.reader(f), [])
        if header != CSV_FIELDS:
            raise CsvFormatError(f"{self.path.name} has an unexpected header: {header}")

    def append(self, row: dict) -> dict:
        record = {k: row.get(k, "") for k in CSV_FIELDS}
        record["intent"] = record["intent"] or "booking"
        record["created_at"] = record["created_at"] or datetime.now(UTC).isoformat(timespec="seconds")
        # csv.DictWriter quotes commas, quotes and line breaks, so a value can't break the row structure
        with self._lock:
            self._check_or_create()
            # append mode never rewrites existing rows
            with self.path.open("a", encoding="utf-8", newline="") as f:
                csv.DictWriter(f, fieldnames=CSV_FIELDS).writerow(record)
        return record

    def read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
