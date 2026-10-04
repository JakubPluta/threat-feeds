from pathlib import Path

import requests

from threat_feeds.downloader import FeedDownloader
from threat_feeds.feeds import FEEDS
from threat_feeds.settings import Settings


class FakeSession:
    """Returns the same response to every request, or raises the same error."""

    def __init__(self, outcome: requests.Response | Exception) -> None:
        self.outcome = outcome

    def get(self, url: str, timeout: tuple[float, float]) -> requests.Response:
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def response(status: int, body: bytes, content_type: str) -> requests.Response:
    canned = requests.Response()
    canned.status_code, canned._content = status, body
    canned.headers["Content-Type"] = content_type
    return canned


def test_download_keeps_an_error_page_as_evidence() -> None:
    error_page = response(503, b"<html>Service Unavailable</html>", "text/html")

    feed_file = FeedDownloader(Settings(), session=FakeSession(error_page)).download(FEEDS[0])

    assert (feed_file.http_status, feed_file.content_type) == (503, "text/html")
    assert feed_file.body == b"<html>Service Unavailable</html>"


def test_download_without_a_response_records_the_error() -> None:
    no_route = requests.ConnectionError("Name or service not known")

    feed_file = FeedDownloader(Settings(), session=FakeSession(no_route)).download(FEEDS[0])

    assert (feed_file.http_status, feed_file.body) == (None, None)
    assert feed_file.error == "ConnectionError: Name or service not known"


def test_download_snapshot_saves_every_feed_into_a_new_snapshot(tmp_path: Path) -> None:
    ok = response(200, b"0.0.0.0 ads.example.com\n", "text/plain")

    snapshot = FeedDownloader(Settings(), session=FakeSession(ok)).download_snapshot(tmp_path)

    assert [snapshot.read(feed.name).http_status for feed in FEEDS] == [200, 200, 200, 200]
    assert len(list(snapshot.folder.iterdir())) == 2 * len(FEEDS)  # <feed>.txt and <feed>.meta.json each
