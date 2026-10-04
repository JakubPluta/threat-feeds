from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pyspark.sql import SparkSession

from threat_feeds.feeds import FEEDS
from threat_feeds.settings import Settings
from threat_feeds.snapshot import FeedFile, Snapshot
from threat_feeds.tables import FeedTables, reject_reason, snapshot_rows
from threat_feeds.tables import RejectReason as Reject

FEED = {feed.name: feed for feed in FEEDS}
STARTED_AT = datetime(2026, 10, 3, 6, 56, tzinfo=UTC)
PLAIN_TEXT = {"content-type": "text/plain; charset=utf-8"}


def feed_file(body: bytes | None, status: int | None = 200, headers: dict[str, str] = PLAIN_TEXT) -> FeedFile:
    return FeedFile(
        feed="feed_a", url="https://example.test", started_at=STARTED_AT, http_status=status, headers=headers, body=body
    )


def hosts_file(domains: int, extra: str = "") -> bytes:
    return ("# header\n" + "".join(f"0.0.0.0 d{i}.example.com\n" for i in range(domains)) + extra).encode()


@pytest.mark.parametrize(
    ("file", "previous_accepted_lines", "rejected_because"),
    [
        pytest.param(feed_file(None, status=None), 100, Reject.NO_RESPONSE, id="no response"),
        pytest.param(feed_file(b"<html>Service Unavailable</html>", status=503), 100, Reject.HTTP_ERROR, id="http 503"),
        pytest.param(
            feed_file(hosts_file(100), headers={"Content-Type": "text/html"}), 100, Reject.NOT_A_TEXT_LIST,
            id="html content type",
        ),
        pytest.param(
            feed_file(b"<!DOCTYPE html><html><body>Rate limited</body></html>"), 100, Reject.FORMAT_CHANGED,
            id="html page served as text/plain",
        ),
        pytest.param(
            feed_file(hosts_file(100) + b"0.0.0.0 caf\xe9.example.com\n"), 100, None,
            id="one line not in utf-8 is dropped, the file is still accepted",
        ),
        pytest.param(
            feed_file(hosts_file(90, "0.0.0.0 a.example.com b.example.com\n" * 10)), 90, Reject.FORMAT_CHANGED,
            id="10% unreadable rules",
        ),
        pytest.param(feed_file(hosts_file(79)), 100, Reject.TOO_FEW_DOMAINS, id="cut off: 79 of 100 domains"),
        pytest.param(feed_file(b"# header only\n"), None, Reject.TOO_FEW_DOMAINS, id="empty list"),
        pytest.param(feed_file(hosts_file(80)), 100, None, id="80 of 100 domains still accepted"),
        pytest.param(feed_file(hosts_file(5)), None, None, id="first snapshot has nothing to compare to"),
    ],
)  # fmt: skip
def test_reject_reason_names_the_reason_or_none_for_a_good_file(
    file: FeedFile, previous_accepted_lines: int | None, rejected_because: Reject | None
) -> None:
    line_counts = Counter(line.dropped_because for line in FEED["feed_a"].parse(file.text))
    assert reject_reason(file, line_counts, previous_accepted_lines) == rejected_because


def test_snapshot_rows_have_one_line_row_per_line_and_rejects_the_feed_that_timed_out(tmp_path: Path) -> None:
    bodies = {
        "feed_a": hosts_file(3),
        "feed_c": b"! Title\n||ads.example.com^\n",
        "feed_d": b"127.0.0.1 x.com\n127.0.0.1 x.com\n",
    }
    snapshot = Snapshot.create(tmp_path)
    for feed in FEEDS:
        answered = feed.name in bodies
        snapshot.save(
            FeedFile(
                feed=feed.name,
                url=str(feed.url),
                started_at=STARTED_AT,
                http_status=200 if answered else None,
                headers=PLAIN_TEXT if answered else {},
                error=None if answered else "ReadTimeout",
                body=bodies.get(feed.name),
            )
        )

    file_rows, line_rows = snapshot_rows(snapshot, previous_accepted_lines={})

    summary = {row["feed"]: (row["line_count"], row["accepted_lines"], row["rejected_because"]) for row in file_rows}
    assert summary == {
        "feed_a": (4, 3, None),
        "feed_b": (0, 0, "no_response"),
        "feed_c": (2, 1, None),
        "feed_d": (2, 2, None),
    }
    assert {line["dropped_because"] for line in line_rows} == {None, "comment"}  # str, not DropReason


def test_previous_accepted_lines_skips_rejected_files(spark: SparkSession, load_snapshot: Callable):
    load_snapshot("2026-10-03T060000Z", {"feed_a": ["a.com", "b.com"]})
    load_snapshot("2026-10-04T060000Z", {"feed_a": ["a.com", "b.com", "c.com"]}, timed_out="feed_a")

    previous = FeedTables(spark, Settings()).previous_accepted_lines(before_snapshot_id="2026-10-05T060000Z")

    assert previous == {"feed_a": 2}  # the timed-out file is skipped


def test_snapshot_rows_skips_a_feed_added_after_the_snapshot(tmp_path: Path) -> None:
    snapshot = Snapshot.create(tmp_path)
    for feed in FEEDS[:3]:
        snapshot.save(feed_file(hosts_file(3)).model_copy(update={"feed": feed.name}))

    file_rows, _ = snapshot_rows(snapshot, previous_accepted_lines={})

    assert [row["feed"] for row in file_rows] == ["feed_a", "feed_b", "feed_c"]
