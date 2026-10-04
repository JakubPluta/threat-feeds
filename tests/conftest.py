import os
import sys
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pyspark.sql import SparkSession

from threat_feeds.feeds import FEEDS
from threat_feeds.snapshot import SNAPSHOT_ID_FORMAT, FeedFile, Snapshot
from threat_feeds.tables import TABLES, read_sql_file, snapshot_rows

HEADER = {
    "feed_a": "# Date: 02 October 2026 19:58:39 (UTC)\n",  # fresh on 2026-10-03, stale a month later
    "feed_b": "! Updated: 2026-10-03T00:09:45Z\n",
    "feed_c": "! Last modified: 2024-05-12T06:39:45.794Z\n",  # stale
    "feed_d": "",  # undated
}
RULE = {"feed_a": "0.0.0.0 {}", "feed_b": "||{}^", "feed_c": "||{}^", "feed_d": "127.0.0.1 {}"}
PLAIN_TEXT = {"content-type": "text/plain; charset=utf-8"}


@pytest.fixture(scope="session")
def local_spark(tmp_path_factory: pytest.TempPathFactory) -> Iterator[SparkSession]:
    """Shared by all Spark tests; they are skipped if Spark can't start (e.g. no Java)."""
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)  # workers must run the same Python as the driver
    warehouse: Path = tmp_path_factory.mktemp("warehouse")
    builder = (
        SparkSession.builder.master("local[1]")
        .config("spark.sql.warehouse.dir", str(warehouse))
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.ui.enabled", "false")
        .config("spark.driver.host", "127.0.0.1")  # the default address breaks on VPN
        .config("spark.driver.bindAddress", "127.0.0.1")
    )
    try:
        spark = builder.getOrCreate()
    except Exception as error:
        pytest.skip(f"no local Spark: {error}")
    yield spark
    spark.stop()


@pytest.fixture
def spark(local_spark: SparkSession) -> SparkSession:
    """Each test gets its own schema with empty feed_files and feed_lines."""
    schema = f"test_{uuid4().hex}"
    local_spark.sql(f"CREATE SCHEMA {schema}")
    local_spark.sql(f"USE {schema}")
    for table in TABLES:
        create_table = read_sql_file(f"{table}.sql")
        local_spark.sql(create_table)
    return local_spark


@pytest.fixture
def load_snapshot(spark: SparkSession, tmp_path: Path) -> Callable[..., None]:
    """load(snapshot_id, {feed: [domains]}, timed_out=feed) writes a snapshot and loads it into silver.

    A feed that lists nothing is rejected as too_few_domains.
    """

    def load(snapshot_id: str, listed: dict[str, list[str]], timed_out: str | None = None) -> None:
        snapshot = Snapshot(tmp_path / snapshot_id)
        snapshot.folder.mkdir()
        started_at = datetime.strptime(snapshot_id, SNAPSHOT_ID_FORMAT).replace(tzinfo=UTC)
        for feed in FEEDS:
            rules = [RULE[feed.name].format(domain) for domain in listed.get(feed.name, [])]
            body = (HEADER[feed.name] + "\n".join(rules) + "\n").encode()
            if feed.name == timed_out:
                feed_file = FeedFile(feed=feed.name, url=str(feed.url), started_at=started_at, error="ReadTimeout")
            else:
                feed_file = FeedFile(
                    feed=feed.name,
                    url=str(feed.url),
                    started_at=started_at,
                    http_status=200,
                    headers=PLAIN_TEXT,
                    body=body,
                )
            snapshot.save(feed_file)

        file_rows, line_rows = snapshot_rows(snapshot, previous_accepted_lines={})
        for table, rows in (("feed_files", file_rows), ("feed_lines", line_rows)):
            table_schema = spark.table(table).schema
            spark.createDataFrame(rows, table_schema).write.mode("append").saveAsTable(table)

    return load
