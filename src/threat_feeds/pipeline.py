"""One run: load the snapshots into silver, rebuild gold, create the checks view."""

from pyspark.sql import SparkSession

from threat_feeds.checks import create_feed_file_checks
from threat_feeds.domains import build_gold
from threat_feeds.downloader import FeedDownloader
from threat_feeds.settings import Settings
from threat_feeds.snapshot import Snapshot
from threat_feeds.tables import FeedTables


def run(spark: SparkSession, settings: Settings) -> None:
    tables = FeedTables(spark, settings)
    tables.create_if_missing()
    match settings.mode:
        case "live":
            snapshots = [FeedDownloader(settings).download_snapshot(settings.volume_path)]
        case "replay":
            tables.truncate()  # rebuild from the committed snapshots only
            snapshots = Snapshot.find_all(settings.snapshots_dir)
    for snapshot in snapshots:
        tables.load(snapshot)
    build_gold(spark)
    create_feed_file_checks(spark)
