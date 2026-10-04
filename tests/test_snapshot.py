from datetime import UTC, datetime
from pathlib import Path

import pytest

from threat_feeds.snapshot import FeedFile, Snapshot

STARTED_AT = datetime(2026, 10, 3, 6, 56, tzinfo=UTC)


def test_read_returns_the_saved_file_byte_for_byte(tmp_path: Path) -> None:
    body = "0.0.0.0 ads.example.com\r\n# Ünïcode and CRLF stay as they are\n".encode()
    saved = FeedFile(feed="feed_a", url="https://example.test", started_at=STARTED_AT, http_status=200, body=body)
    snapshot = Snapshot.create(tmp_path)

    snapshot.save(saved)

    assert snapshot.read("feed_a") == saved


def test_file_without_a_body_is_saved_as_metadata_only(tmp_path: Path) -> None:
    timed_out = FeedFile(feed="feed_b", url="https://example.test", started_at=STARTED_AT, error="ReadTimeout")
    snapshot = Snapshot.create(tmp_path)

    snapshot.save(timed_out)

    assert [path.name for path in snapshot.folder.iterdir()] == ["feed_b.meta.json"]
    assert snapshot.read("feed_b").body is None


def test_find_all_lists_snapshots_oldest_first(tmp_path: Path) -> None:
    for snapshot_id in ("2026-10-04T060000Z", "2026-10-03T060000Z"):
        (tmp_path / snapshot_id).mkdir()

    assert [snapshot.id for snapshot in Snapshot.find_all(tmp_path)] == ["2026-10-03T060000Z", "2026-10-04T060000Z"]


def test_find_all_refuses_a_folder_not_named_like_a_snapshot(tmp_path: Path) -> None:
    (tmp_path / "2026-10-03T060000Z").mkdir()
    (tmp_path / "notes").mkdir()

    with pytest.raises(ValueError, match="notes"):
        Snapshot.find_all(tmp_path)
