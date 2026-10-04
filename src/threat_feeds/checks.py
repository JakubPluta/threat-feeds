"""Checks after each run: per-file line counts, reconciliation, and whether the job passes."""

from pyspark.sql import DataFrame, Row, SparkSession

from threat_feeds.tables import read_sql_file

IS_LATEST_SNAPSHOT = "snapshot_id = (SELECT max(snapshot_id) FROM feed_files)"


class ChecksFailed(Exception):
    pass


def create_feed_file_checks(spark: SparkSession) -> None:
    create_view = read_sql_file("feed_file_checks.sql")
    spark.sql(create_view)


def reconciliation_counts(spark: SparkSession) -> Row:
    query = read_sql_file("reconciliation.sql")
    return spark.sql(query).first()


def domain_changes(spark: SparkSession) -> DataFrame:
    query = read_sql_file("domain_changes.sql")
    return spark.sql(query)


def check_latest_snapshot(spark: SparkSession) -> None:
    """Raises if a file of the latest snapshot was rejected or the counts don't match.

    Runs after the gold tables are written, so a failure marks the job red but doesn't hold back the data.
    """
    latest_files = spark.table("feed_file_checks").where(IS_LATEST_SNAPSHOT)
    failed_files = latest_files.where("rejected_because IS NOT NULL OR NOT lines_add_up").collect()
    problems = [f"{row.feed}: {row.rejected_because or 'lines do not add up'}" for row in failed_files]
    counts = reconciliation_counts(spark)
    if not counts.adds_up:
        problems.append(f"domain_current does not add up: {counts.asDict()}")
    if problems:
        raise ChecksFailed("; ".join(problems))
