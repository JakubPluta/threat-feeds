from collections.abc import Callable

from pyspark.sql import SparkSession

from threat_feeds.domains import build_gold, lookup_domain

FIRST, SECOND, THIRD = "2026-10-03T060000Z", "2026-10-04T060000Z", "2026-10-05T060000Z"
MONTH_LATER = "2026-11-05T060000Z"  # feed_a's header date, 2026-10-02, is then more than 30 days old


def current(spark: SparkSession) -> dict[str, tuple]:
    rows = spark.sql("SELECT domain, category, sources, fresh_sources, trust FROM domain_current").collect()
    return {row.domain: (row.category, row.sources, row.fresh_sources, row.trust) for row in rows}


def history(spark: SparkSession, domain: str) -> list[tuple]:
    query = (
        "SELECT category, sources, trust, CAST(valid_from AS STRING) AS valid_from, "
        "CAST(valid_to AS STRING) AS valid_to FROM domain_history WHERE domain = :domain ORDER BY valid_from"
    )
    rows = spark.sql(query, args={"domain": domain}).collect()
    return [(row.category, row.sources, row.trust, row.valid_from, row.valid_to) for row in rows]


def test_domain_current_has_one_row_per_domain_with_the_most_harmful_category_and_its_trust(
    spark: SparkSession, load_snapshot: Callable
):
    listed = {"feed_a": ["x.com", "only-a.com"], "feed_b": ["x.com"], "feed_c": ["old.com"], "feed_d": ["old.com"]}
    load_snapshot(FIRST, listed)

    build_gold(spark)

    assert current(spark) == {
        "x.com": ("malware", ["feed_a", "feed_b"], ["feed_a", "feed_b"], "high"),
        "only-a.com": ("ads_and_trackers", ["feed_a"], ["feed_a"], "medium"),
        "old.com": ("ads_and_trackers", ["feed_c", "feed_d"], [], "low"),
    }


def test_history_of_a_domain_unknown_then_ads_then_malware(spark: SparkSession, load_snapshot: Callable):
    load_snapshot(FIRST, {"feed_a": ["other.com"]})
    load_snapshot(SECOND, {"feed_a": ["other.com", "x.com"]})
    load_snapshot(THIRD, {"feed_a": ["other.com", "x.com"], "feed_b": ["x.com"]})

    build_gold(spark)

    assert history(spark, "x.com") == [
        ("ads_and_trackers", ["feed_a"], "medium", "2026-10-04 06:00:00", "2026-10-05 06:00:00"),
        ("malware", ["feed_a", "feed_b"], "medium", "2026-10-05 06:00:00", None),  # feed_b's file is 2+ days old
    ]


def test_history_adds_no_version_when_nothing_changed(spark: SparkSession, load_snapshot: Callable):
    listed = {"feed_a": ["x.com"], "feed_b": ["x.com"]}
    load_snapshot(FIRST, listed)
    load_snapshot(SECOND, listed)

    build_gold(spark)

    assert history(spark, "x.com") == [("malware", ["feed_a", "feed_b"], "high", "2026-10-03 06:00:00", None)]


def test_history_adds_a_version_for_every_change_including_a_change_back(spark: SparkSession, load_snapshot: Callable):
    load_snapshot(FIRST, {"feed_a": ["x.com"]})
    load_snapshot(SECOND, {"feed_a": ["x.com"], "feed_b": ["x.com"]})
    load_snapshot(THIRD, {"feed_a": ["x.com"], "feed_b": ["other.com"]})

    build_gold(spark)

    assert history(spark, "x.com") == [
        ("ads_and_trackers", ["feed_a"], "medium", "2026-10-03 06:00:00", "2026-10-04 06:00:00"),
        ("malware", ["feed_a", "feed_b"], "high", "2026-10-04 06:00:00", "2026-10-05 06:00:00"),
        ("ads_and_trackers", ["feed_a"], "medium", "2026-10-05 06:00:00", None),
    ]


def test_trust_drops_to_low_when_the_only_source_gets_stale(spark: SparkSession, load_snapshot: Callable):
    load_snapshot(FIRST, {"feed_a": ["x.com"]})
    load_snapshot(MONTH_LATER, {"feed_a": ["x.com"]})  # the same file, still dated 2026-10-02

    build_gold(spark)

    assert history(spark, "x.com") == [
        ("ads_and_trackers", ["feed_a"], "medium", "2026-10-03 06:00:00", "2026-11-05 06:00:00"),
        ("ads_and_trackers", ["feed_a"], "low", "2026-11-05 06:00:00", None),
    ]


def test_trust_is_high_only_when_two_fresh_feeds_list_the_domain(spark: SparkSession, load_snapshot: Callable):
    listed = {
        "feed_a": ["two-fresh.com", "fresh-and-stale.com"],
        "feed_b": ["two-fresh.com"],
        "feed_c": ["fresh-and-stale.com"],
    }
    load_snapshot(FIRST, listed)

    build_gold(spark)

    trust = {domain: answer[3] for domain, answer in current(spark).items()}
    assert trust == {"two-fresh.com": "high", "fresh-and-stale.com": "medium"}


def test_rejected_file_is_replaced_by_the_feeds_last_accepted_file(spark: SparkSession, load_snapshot: Callable):
    listed = {"feed_a": ["x.com"], "feed_b": ["x.com"]}
    load_snapshot(FIRST, listed)
    load_snapshot(SECOND, listed, timed_out="feed_b")

    build_gold(spark)

    assert current(spark)["x.com"] == ("malware", ["feed_a", "feed_b"], ["feed_a", "feed_b"], "high")
    assert history(spark, "x.com") == [("malware", ["feed_a", "feed_b"], "high", "2026-10-03 06:00:00", None)]


def test_domain_no_longer_listed_leaves_domain_current_and_its_history_version_closes(
    spark: SparkSession, load_snapshot: Callable
):
    load_snapshot(FIRST, {"feed_a": ["kept.com", "gone.com"]})
    load_snapshot(SECOND, {"feed_a": ["kept.com"]})

    build_gold(spark)

    assert history(spark, "gone.com") == [
        ("ads_and_trackers", ["feed_a"], "medium", "2026-10-03 06:00:00", "2026-10-04 06:00:00")
    ]
    assert set(current(spark)) == {"kept.com"}


def test_adblock_rule_for_a_parent_covers_subdomains_but_hosts_line_does_not(
    spark: SparkSession, load_snapshot: Callable
):
    load_snapshot(FIRST, {"feed_a": ["stats.ads.com", "tracker.com"], "feed_c": ["ads.com"]})

    build_gold(spark)

    assert current(spark)["stats.ads.com"] == ("ads_and_trackers", ["feed_a", "feed_c"], ["feed_a"], "medium")
    not_listed = lookup_domain(spark, "Deep.X.Ads.com").first()
    answer = (not_listed.harmful, not_listed.sources, not_listed.trust, not_listed.listed_as)
    assert answer == (True, ["feed_c"], "low", ["ads.com"])
    assert lookup_domain(spark, "x.tracker.com").first().harmful is False


def test_lookup_domain_gives_the_same_answer_as_domain_current(spark: SparkSession, load_snapshot: Callable):
    listed = {"feed_a": ["x.com", "stats.ads.com"], "feed_b": ["x.com"], "feed_c": ["ads.com"], "feed_d": ["x.com"]}
    load_snapshot(FIRST, listed)

    build_gold(spark)

    for domain, row_in_domain_current in current(spark).items():
        answer = lookup_domain(spark, domain).first()
        assert (answer.category, answer.sources, answer.fresh_sources, answer.trust) == row_in_domain_current
