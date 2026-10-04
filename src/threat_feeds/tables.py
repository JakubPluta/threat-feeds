"""Silver: feed_files (one row per downloaded file) and feed_lines (one row per line)."""

from collections import Counter
from enum import StrEnum
from importlib.resources import files

from pyspark.sql import SparkSession

from threat_feeds.feeds import FEEDS, DropReason
from threat_feeds.settings import Settings
from threat_feeds.snapshot import FeedFile, Snapshot


class RejectReason(StrEnum):
    """Why a downloaded file isn't used. It's still stored; the feed keeps using its last accepted file."""

    NO_RESPONSE = "no_response"  # timeout, DNS error, connection refused
    HTTP_ERROR = "http_error"  # status other than 200
    NOT_A_TEXT_LIST = "not_a_text_list"  # content type isn't text/plain, e.g. an HTML error page
    FORMAT_CHANGED = "format_changed"  # too many rules we can't parse
    TOO_FEW_DOMAINS = "too_few_domains"  # none, or a lot fewer than last time (probably cut off)


MIN_SHARE_OF_PREVIOUS_DOMAINS = 0.8  # else too_few_domains
MAX_SHARE_OF_UNREADABLE_RULES = 0.05  # else format_changed

TABLES = ("feed_files", "feed_lines")  # DDL in sql/<table>.sql


class FeedTables:
    def __init__(self, spark: SparkSession, settings: Settings) -> None:
        self.spark = spark
        self.settings = settings

    def create_if_missing(self) -> None:
        schema = f"{self.settings.catalog}.{self.settings.schema_name}"
        volume = f"{schema}.{self.settings.volume}"
        self.spark.conf.set("spark.sql.session.timeZone", "UTC")
        self.spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        self.spark.sql(f"CREATE VOLUME IF NOT EXISTS {volume}")
        self.spark.sql(f"USE {schema}")
        for table in TABLES:
            create_table = read_sql_file(f"{table}.sql")
            self.spark.sql(create_table)

    def truncate(self) -> None:
        for table in TABLES:
            self.spark.sql(f"TRUNCATE TABLE {table}")

    def load(self, snapshot: Snapshot) -> None:
        """Writes the snapshot's rows to both tables. Loading the same snapshot again replaces them."""
        previous_accepted_lines = self.previous_accepted_lines(before_snapshot_id=snapshot.id)
        file_rows, line_rows = snapshot_rows(snapshot, previous_accepted_lines)
        this_snapshot_only = f"snapshot_id = '{snapshot.id}'"
        for table, rows in (("feed_files", file_rows), ("feed_lines", line_rows)):
            table_schema = self.spark.table(table).schema
            (
                self.spark.createDataFrame(rows, table_schema)
                .write.mode("overwrite")
                .option("replaceWhere", this_snapshot_only)
                .saveAsTable(table)
            )

    def previous_accepted_lines(self, before_snapshot_id: str) -> dict[str, int]:
        """accepted_lines of each feed's last accepted file before the given snapshot."""
        query = (
            "SELECT feed, max_by(accepted_lines, snapshot_id) AS accepted_lines FROM feed_files "
            "WHERE snapshot_id < :before_snapshot_id AND rejected_because IS NULL GROUP BY feed"
        )
        rows = self.spark.sql(query, args={"before_snapshot_id": before_snapshot_id}).collect()
        return {row.feed: row.accepted_lines for row in rows}


def snapshot_rows(snapshot: Snapshot, previous_accepted_lines: dict[str, int]) -> tuple[list[dict], list[dict]]:
    """(feed_files rows, feed_lines rows). No Spark here, so it's easy to test."""
    file_rows, line_rows = [], []
    for feed in FEEDS:
        if not snapshot.has_file(feed.name):  # feed added after this snapshot was taken
            continue
        feed_file = snapshot.read(feed.name)
        lines = feed.parse(feed_file.text)
        line_counts = Counter(line.dropped_because for line in lines)  # key None = accepted
        previous = previous_accepted_lines.get(feed.name)
        rejected_because = reject_reason(feed_file, line_counts, previous)
        file_rows.append(
            {
                "snapshot_id": snapshot.id,
                "feed": feed.name,
                "url": feed_file.url,
                "started_at": feed_file.started_at,
                "http_status": feed_file.http_status,
                "content_type": feed_file.content_type,
                "error": feed_file.error,
                "bytes": feed_file.size,
                "sha256": feed_file.sha256,
                "line_count": len(lines),
                "accepted_lines": line_counts[None],
                "provider_published_at": feed.publish_date(feed_file.text),
                "previous_accepted_lines": previous,
                "rejected_because": str(rejected_because) if rejected_because else None,
            }
        )
        line_rows += [{"snapshot_id": snapshot.id, "feed": feed.name, **line.as_row()} for line in lines]
    return file_rows, line_rows


def reject_reason(
    feed_file: FeedFile, line_counts: Counter[DropReason | None], previous_accepted_lines: int | None
) -> RejectReason | None:
    accepted = line_counts[None]
    unreadable = line_counts[DropReason.UNREADABLE_RULE]
    rules = line_counts.total() - line_counts[DropReason.BLANK] - line_counts[DropReason.COMMENT]
    is_first_file = previous_accepted_lines is None
    looks_cut_off = not is_first_file and accepted < MIN_SHARE_OF_PREVIOUS_DOMAINS * previous_accepted_lines

    if feed_file.body is None:
        return RejectReason.NO_RESPONSE
    if feed_file.http_status != 200:
        return RejectReason.HTTP_ERROR
    if not feed_file.content_type.startswith("text/plain"):
        return RejectReason.NOT_A_TEXT_LIST
    if unreadable > MAX_SHARE_OF_UNREADABLE_RULES * rules:
        return RejectReason.FORMAT_CHANGED
    if accepted == 0 or looks_cut_off:
        return RejectReason.TOO_FEW_DOMAINS
    return None


def read_sql_file(name: str) -> str:
    # the SQL files are package data, so this works wherever the package is installed
    sql_folder = files("threat_feeds") / "sql"
    sql_path = sql_folder / name
    return sql_path.read_text()
