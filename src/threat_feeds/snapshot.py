"""Bronze: one folder per snapshot with each feed's raw file and response metadata."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Self

from pydantic import BaseModel, Field

SNAPSHOT_ID_FORMAT = "%Y-%m-%dT%H%M%SZ"  # UTC, sorts by time


class FeedFile(BaseModel):
    """One feed's download: the body as received plus what the server sent with it."""

    feed: str
    url: str
    started_at: datetime
    http_status: int | None = None
    headers: dict[str, str] = {}
    error: str | None = None  # set when there was no response
    body: bytes | None = Field(default=None, exclude=True)  # saved to <feed>.txt, not to the JSON

    @property
    def text(self) -> str:
        # invalid UTF-8 becomes U+FFFD, so only that line fails to parse
        if self.body is None:
            return ""
        return self.body.decode("utf-8", errors="replace")

    @property
    def size(self) -> int | None:
        if self.body is None:
            return None
        return len(self.body)

    @property
    def sha256(self) -> str | None:
        if self.body is None:
            return None
        return hashlib.sha256(self.body).hexdigest()

    @property
    def content_type(self) -> str:
        for name, value in self.headers.items():
            if name.lower() == "content-type":
                return value
        return ""


class Snapshot:
    """Folder <snapshot_id>/ with <feed>.txt and <feed>.meta.json for each feed."""

    def __init__(self, folder: Path) -> None:
        datetime.strptime(folder.name, SNAPSHOT_ID_FORMAT)  # ValueError for a folder that isn't a snapshot
        self.folder = folder
        self.id = folder.name

    @classmethod
    def create(cls, snapshots_dir: Path) -> Self:
        snapshot_id = datetime.now(UTC).strftime(SNAPSHOT_ID_FORMAT)
        folder = snapshots_dir / snapshot_id
        folder.mkdir(parents=True)
        return cls(folder)

    @classmethod
    def find_all(cls, snapshots_dir: Path) -> list[Self]:
        """Oldest first."""
        folders = sorted(path for path in snapshots_dir.iterdir() if path.is_dir())
        return [cls(folder) for folder in folders]

    def save(self, feed_file: FeedFile) -> None:
        body_path = self._body_path(feed_file.feed)
        metadata_path = self._metadata_path(feed_file.feed)
        if feed_file.body is not None:
            body_path.write_bytes(feed_file.body)
        metadata = feed_file.model_dump_json(indent=2)
        metadata_path.write_text(metadata)

    def has_file(self, feed_name: str) -> bool:
        metadata_path = self._metadata_path(feed_name)  # written even when the download timed out
        return metadata_path.exists()

    def read(self, feed_name: str) -> FeedFile:
        body_path = self._body_path(feed_name)
        metadata_path = self._metadata_path(feed_name)
        metadata = json.loads(metadata_path.read_text())
        body = body_path.read_bytes() if body_path.exists() else None
        return FeedFile(**metadata, body=body)

    def _body_path(self, feed_name: str) -> Path:
        return self.folder / f"{feed_name}.txt"

    def _metadata_path(self, feed_name: str) -> Path:
        return self.folder / f"{feed_name}.meta.json"
