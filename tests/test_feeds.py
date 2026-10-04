from datetime import UTC, datetime

import pytest

from threat_feeds.feeds import FEEDS
from threat_feeds.feeds import DropReason as Drop

FEED = {feed.name: feed for feed in FEEDS}


@pytest.mark.parametrize(
    ("feed", "line", "domain", "dropped_because"),
    [
        ("feed_a", "", None, Drop.BLANK),
        ("feed_a", "# Title: StevenBlack/hosts", None, Drop.COMMENT),
        ("feed_b", "! Updated: 2026-10-03T00:09:45Z", None, Drop.COMMENT),
        ("feed_a", "0.0.0.0 ads.example.com", "ads.example.com", None),
        ("feed_d", "127.0.0.1 ads.example.com", "ads.example.com", None),
        ("feed_d", "127.0.0.1 mobile.Banzai.it", "mobile.banzai.it", None),
        ("feed_a", "0.0.0.0 ads.example.com # ads with redirects", "ads.example.com", None),
        ("feed_a", "0.0.0.0 xn--mnchen-3ya.de", "xn--mnchen-3ya.de", None),
        ("feed_a", "0.0.0.0 _dmarc.example.com", "_dmarc.example.com", None),
        ("feed_b", "||evil.example.com^", "evil.example.com", None),
        ("feed_a", "0.0.0.0 a.example.com b.example.com", None, Drop.UNREADABLE_RULE),
        ("feed_a", "1.2.3.4 redirect.example.com", None, Drop.UNREADABLE_RULE),
        ("feed_b", "@@||allowed.example.com^", None, Drop.UNREADABLE_RULE),
        ("feed_a", "0.0.0.0 not_a_hostname", None, Drop.UNREADABLE_RULE),
        ("feed_a", "0.0.0.0 münchen.de", None, Drop.UNREADABLE_RULE),
        ("feed_a", "127.0.0.1 localhost", None, Drop.LOCAL_MACHINE_NAME),
        ("feed_a", "::1 ip6-localhost", None, Drop.LOCAL_MACHINE_NAME),
        ("feed_b", "||1.171.9.127^", None, Drop.IP_ADDRESS),
    ],
)
def test_parse_accepts_a_domain_or_drops_the_line_with_a_reason(
    feed: str, line: str, domain: str | None, dropped_because: Drop | None
) -> None:
    (parsed,) = FEED[feed].parse(line + "\n")
    assert (parsed.domain, parsed.dropped_because) == (domain, dropped_because)


def test_parse_keeps_repeated_domains_and_upstream_sections() -> None:
    lines = FEED["feed_a"].parse("# Start URLHaus\n0.0.0.0 x.com\n# End URLHaus\n0.0.0.0 X.com\n")
    assert [(line.domain, line.dropped_because) for line in lines if line.domain] == [("x.com", None), ("x.com", None)]


def test_parse_accepts_feed_d_rules_its_provider_warns_may_break_apps() -> None:
    warning_section = "#pkg=white.ad.web.com;【提示误伤】选择性不√以下子项\n127.0.0.1 wxsnsdy.wxs.qq.com #-> 微信\n"
    lines = FEED["feed_d"].parse(warning_section)
    assert [(line.domain, line.dropped_because) for line in lines if line.domain] == [("wxsnsdy.wxs.qq.com", None)]


def test_parse_turns_every_line_into_exactly_one_parsed_line() -> None:
    lines = FEED["feed_a"].parse("# header\n\n0.0.0.0 x.com\n0.0.0.0 x.com\n0.0.0.0 1.2.3.4\n")
    assert [line.line_number for line in lines] == [1, 2, 3, 4, 5]


@pytest.mark.parametrize(
    ("feed", "header", "published"),
    [
        ("feed_a", "# Date: 02 October 2026 19:58:39 (UTC)", datetime(2026, 10, 2, 19, 58, 39, tzinfo=UTC)),
        ("feed_b", "! Updated: 2026-10-03T00:09:45Z", datetime(2026, 10, 3, 0, 9, 45, tzinfo=UTC)),
        ("feed_d", "127.0.0.1 x.com", None),
    ],
)
def test_publish_date_is_read_from_the_header_in_utc(feed: str, header: str, published: datetime | None) -> None:
    assert FEED[feed].publish_date(header + "\n") == published
