from collections.abc import Callable

import pytest
from pyspark.sql import SparkSession

from threat_feeds.checks import (
    ChecksFailed,
    check_latest_snapshot,
    create_feed_file_checks,
    domain_changes,
    reconciliation_counts,
)
from threat_feeds.domains import build_gold

FIRST, SECOND = "2026-10-03T060000Z", "2026-10-04T060000Z"
LISTED = {"feed_a": ["x.com", "x.com", "y.com"], "feed_b": ["x.com"], "feed_c": ["z.com"], "feed_d": ["z.com"]}


def build(spark: SparkSession) -> None:
    build_gold(spark)
    create_feed_file_checks(spark)


def test_checks_pass_when_every_line_and_listed_name_adds_up(spark: SparkSession, load_snapshot: Callable):
    load_snapshot(FIRST, LISTED)
    build(spark)

    feed_a = spark.sql("SELECT * FROM feed_file_checks WHERE feed = 'feed_a'").first()
    line_arithmetic = (feed_a.line_count, feed_a.accepted_lines, feed_a.distinct_domains, feed_a.dropped_lines)
    assert line_arithmetic == (4, 3, 2, {"comment": 1})
    expected = {
        "listings": 5,
        "listed_names": 3,
        "domain_current_rows": 3,
        "domain_current_domains": 3,
        "adds_up": True,
    }
    assert reconciliation_counts(spark).asDict() == expected
    check_latest_snapshot(spark)


def test_checks_fail_when_a_file_is_rejected_and_show_the_file_still_in_use(
    spark: SparkSession, load_snapshot: Callable
):
    load_snapshot(FIRST, LISTED)
    load_snapshot(SECOND, LISTED, timed_out="feed_b")
    build(spark)

    feed_b = spark.sql(f"SELECT * FROM feed_file_checks WHERE feed = 'feed_b' AND snapshot_id = '{SECOND}'").first()
    assert (feed_b.rejected_because, feed_b.used_file_snapshot_id) == ("no_response", FIRST)
    with pytest.raises(ChecksFailed, match="feed_b: no_response"):
        check_latest_snapshot(spark)


def test_checks_fail_when_lines_are_stored_twice(spark: SparkSession, load_snapshot: Callable):
    load_snapshot(FIRST, LISTED)
    spark.sql("INSERT INTO feed_lines SELECT * FROM feed_lines WHERE feed = 'feed_c'")
    build(spark)

    with pytest.raises(ChecksFailed, match="feed_c: lines do not add up"):
        check_latest_snapshot(spark)


def test_domain_changes_counts_each_domain_once_by_kind_of_change(spark: SparkSession, load_snapshot: Callable):
    load_snapshot(FIRST, {"feed_a": ["kept.com", "gone.com", "x.com"]})
    load_snapshot(SECOND, {"feed_a": ["kept.com", "x.com", "new.com"], "feed_b": ["x.com"]})
    build(spark)

    changes = {row.change: row.domains for row in domain_changes(spark).collect()}

    # new.com added, gone.com removed, x.com now also in feed_b (malware)
    assert changes == {"added": 1, "removed": 1, "category_changed": 1}
