"""Downloads the four feeds into a new snapshot folder."""

import logging
from datetime import UTC, datetime
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from threat_feeds.feeds import FEEDS, Feed
from threat_feeds.settings import Settings
from threat_feeds.snapshot import FeedFile, Snapshot

logger = logging.getLogger(__name__)

RETRY_ON_STATUS = (429, 500, 502, 503, 504)  # temporary; a 403 or 404 won't go away by retrying


class FeedDownloader:
    def __init__(self, settings: Settings, session: requests.Session | None = None) -> None:
        self.session = session or create_session(settings)
        self.timeout = (settings.connect_timeout_s, settings.read_timeout_s)

    def download_snapshot(self, snapshots_dir: Path) -> Snapshot:
        snapshot = Snapshot.create(snapshots_dir)
        for feed in FEEDS:
            feed_file = self.download(feed)
            snapshot.save(feed_file)
            logger.info("%s: HTTP %s, error=%s", feed.name, feed_file.http_status, feed_file.error)
        return snapshot

    def download(self, feed: Feed) -> FeedFile:
        """Doesn't raise. Error pages are kept as they are; with no response at all, `error` says why."""
        url = str(feed.url)
        started_at = datetime.now(UTC)
        try:
            response = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as error:
            reason = f"{type(error).__name__}: {error}"
            return FeedFile(feed=feed.name, url=url, started_at=started_at, error=reason)
        return FeedFile(
            feed=feed.name,
            url=url,
            started_at=started_at,
            http_status=response.status_code,
            headers=dict(response.headers),
            body=response.content,
        )


def create_session(settings: Settings) -> requests.Session:
    # retries connection errors and RETRY_ON_STATUS with backoff; a body cut off mid-download is not retried
    retry = Retry(
        total=settings.retries,
        backoff_factor=settings.backoff_factor,
        status_forcelist=RETRY_ON_STATUS,
        allowed_methods=["GET"],
        raise_on_status=False,  # return the last error response instead of raising, so it gets saved
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = settings.user_agent
    return session


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = Settings()
    snapshot = FeedDownloader(settings).download_snapshot(settings.snapshots_dir)
    logger.info("snapshot: %s", snapshot.folder)
