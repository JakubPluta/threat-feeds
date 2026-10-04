"""Gold: views and tables built from silver on every run."""

from pyspark.sql import DataFrame, SparkSession

from threat_feeds.feeds import FEEDS
from threat_feeds.tables import read_sql_file

GOLD_VIEWS = ("feed_file_in_use", "domain_listings", "domain_answers_by_snapshot")  # sql/<name>.sql, in this order
GOLD_TABLES = ("domain_history", "domain_current")  # domain_current reads domain_history, so history goes first


def build_gold(spark: SparkSession) -> None:
    write_feed_rules(spark)
    for view in GOLD_VIEWS:
        create_view = read_sql_file(f"{view}.sql")
        spark.sql(create_view)
    for table in GOLD_TABLES:
        select = read_sql_file(f"{table}.sql")
        spark.sql(select).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)


def lookup_domain(spark: SparkSession, domain: str) -> DataFrame:
    """Latest answer for any name, including subdomains no feed lists but a ||parent^ rule covers."""
    query = read_sql_file("domain_lookup.sql")
    return spark.sql(query, args={"domain": domain})


def write_feed_rules(spark: SparkSession) -> None:
    # the gold SQL needs the rules from feeds.py, so they go into a table
    create_table = read_sql_file("feed_rules.sql")
    spark.sql(create_table)
    feed_rows = [feed.as_row() for feed in FEEDS]
    table_schema = spark.table("feed_rules").schema
    spark.createDataFrame(feed_rows, table_schema).write.mode("overwrite").saveAsTable("feed_rules")
