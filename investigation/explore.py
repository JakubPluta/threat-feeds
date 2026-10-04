"""The checks behind investigation/README.md, one function per feed.

Run: uv run python investigation/explore.py investigation/2026-10-03
"""

import re
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

from threat_feeds.feeds import FEEDS

SNAPSHOT = Path(sys.argv[1] if len(sys.argv) > 1 else "investigation/2026-10-03")
FEED = {feed.name: feed for feed in FEEDS}


def main():
    feed_a()
    feed_b()
    feed_c()
    feed_d()
    across_feeds()


def feed_a():
    title("feed_a: StevenBlack hosts")
    text, lines = read("feed_a"), parsed("feed_a")
    print("provider's publish date:", FEED["feed_a"].publish_date(text))
    print("provider's own count:", re.search(r"^# Number of unique domains: (.+)$", text, re.M)[1])
    print("what every line is:", line_kinds(lines))

    print("lines repeating a domain listed earlier in the file:", repeats(lines))

    # The file is 16 upstream lists glued together, each between "# Start <name>" and "# End <name>".
    section_of = section_of_each_rule(text, opens=r"^# Start (.+)$")
    print("rules per upstream section:", dict(Counter(section_of.values()).most_common()))

    # The URLHaus section is the same abuse.ch source feed_b is built from. The pipeline keeps it (see NOTES.md).
    lines_of_file = text.splitlines()
    section_start = lines_of_file.index("# Start URLHaus")
    section_header = lines_of_file[section_start + 3 : section_start + 5]
    print("URLHaus section opens with:", [line.strip(" #") for line in section_header])
    copy, in_feed_b = urlhaus_copy(), accepted_domains("feed_b")
    print(
        f"URLHaus section: {len(copy)}, also in feed_b: {len(copy & in_feed_b)}, not in feed_b: {len(copy - in_feed_b)}"
    )

    # Rules with a comment after the name, e.g. "0.0.0.0 xvtelink.com # ads with redirects".
    print("rules with a trailing comment:", sum(1 for x in text.splitlines() if x.startswith("0.0.0.0 ") and "#" in x))
    print("punycode names:", punycode_names(lines))


def feed_b():
    title("feed_b: URLhaus via malware-filter")
    text, lines = read("feed_b"), parsed("feed_b")
    print("provider's publish date:", FEED["feed_b"].publish_date(text))
    print("declared update cadence:", re.search(r"^! Expires: (.+)$", text, re.M)[1])
    print("declared source:", re.search(r"^! Source: (.+)$", text, re.M)[1])
    print("HTTP Last-Modified:", http_header("feed_b", "last-modified"))
    print("what every line is:", line_kinds(lines))

    # The domains that are left: mostly one tenant on a shared hosting platform, e.g. "abc.r2.dev".
    platforms = Counter(".".join(domain.split(".")[-2:]) for domain in accepted_domains("feed_b"))
    print("most common parent domains:", platforms.most_common(8))
    print("punycode names:", punycode_names(lines))


def feed_c():
    title("feed_c: 1Hosts Lite")
    text, lines = read("feed_c"), parsed("feed_c")
    # Two independent signals of age: the date in the file and the web server's Last-Modified.
    print("provider's publish date:", FEED["feed_c"].publish_date(text))
    print("HTTP Last-Modified:", http_header("feed_c", "last-modified"))
    print("provider's own count:", re.search(r"Count: ([\d,]+)", text)[1])
    print("what every line is:", line_kinds(lines))
    print("punycode names:", punycode_names(lines))


def feed_d():
    title("feed_d: ad-wars hosts")
    text, lines = read("feed_d"), parsed("feed_d")
    print("provider's publish date:", FEED["feed_d"].publish_date(text))
    print("HTTP Last-Modified:", http_header("feed_d", "last-modified"))
    print("what every line is:", line_kinds(lines))

    print("lines repeating a domain listed earlier in the file:", repeats(lines))

    # Sections start with "#pkg=<name>;<description in Chinese>".
    print("sections:", re.findall(r"^#pkg=([^;]+);(.*)$", text, re.M))
    section_of = section_of_each_rule(text, opens=r"^#pkg=([^;]+);")
    print("rules per section:", dict(Counter(section_of.values())))

    # "【提示误伤】选择性不√以下子项" = "collateral damage: you may leave the entries below unticked".
    # Then "下列会影响奖励形式的广告(小程序\小游戏等)" = "the following affect reward ads (mini-programs, mini-games)".
    warning_section = [line.domain for line in lines if section_of.get(line.line_number) == "white.ad.web.com"]
    print("domains in the warning section:", warning_section)
    rules = {line.text: line.text.split("#")[0] for line in lines if line.domain}
    print("rules written with uppercase letters:", [text for text, rule in rules.items() if rule != rule.lower()])


def across_feeds():
    title("across all four feeds")
    domains = {feed: accepted_domains(feed) for feed in FEED}
    for feed, names in domains.items():
        print(f"{feed}: {len(names):,} accepted domains")
    total, distinct = sum(map(len, domains.values())), len(set().union(*domains.values()))
    print(f"sum: {total:,}, distinct: {distinct:,}, repeat listings: {total - distinct:,}")

    for feed, names in domains.items():
        listed_elsewhere = set().union(*(other for name, other in domains.items() if name != feed))
        print(f"{feed}: in no other feed: {len(names - listed_elsewhere):,}")
    # feed_c and feed_d have not changed in years: these names have no fresh source at all.
    only_stale = (domains["feed_c"] | domains["feed_d"]) - domains["feed_a"] - domains["feed_b"]
    print(f"listed only by feed_c/feed_d: {len(only_stale):,} of {distinct:,}")

    for a, b in combinations(FEED, 2):
        print(f"{a} ∩ {b}: {len(domains[a] & domains[b]):,}")
    # feed_a files everything as ads, feed_b as malware: these names get two different categories.
    conflicts = domains["feed_a"] & domains["feed_b"]
    outside_urlhaus = conflicts - urlhaus_copy()
    print(
        f"category conflicts (feed_a ∩ feed_b): {len(conflicts)}, of which outside feed_a's URLHaus section: "
        f"{len(outside_urlhaus)} {sorted(outside_urlhaus)}"
    )

    # "||parent^" in feed_b/feed_c also blocks every subdomain, so these names are already covered.
    covers_subdomains = domains["feed_b"] | domains["feed_c"]
    for feed in ("feed_a", "feed_d"):
        covered = sum(1 for domain in domains[feed] if any(p in covers_subdomains for p in parent_domains(domain)))
        print(f"{feed} names already covered by a parent in feed_b/feed_c: {covered:,}")


def read(feed):
    return (SNAPSHOT / f"{feed}.txt").read_text(encoding="utf-8")


def parsed(feed):
    return FEED[feed].parse(read(feed))


def accepted_domains(feed):
    return {line.domain for line in parsed(feed) if line.dropped_because is None}


def http_header(feed, name):
    headers = (SNAPSHOT / f"{feed}.headers.txt").read_text()
    found = re.search(rf"^{name}: (.+)$", headers, re.M | re.I)
    return found[1].strip() if found else None


def section_of_each_rule(text, opens):
    """{line_number: section} for rules between a section's opening comment and "# End ..." or the next section."""
    section_of, current = {}, None
    for line_number, line in enumerate(text.splitlines(), start=1):
        if found := re.match(opens, line):
            current = found[1].strip()
        elif line.startswith("# End "):
            current = None
        elif current and line.strip() and not line.startswith("#"):
            section_of[line_number] = current
    return section_of


def urlhaus_copy():
    section_of = section_of_each_rule(read("feed_a"), opens=r"^# Start (.+)$")
    return {line.domain for line in parsed("feed_a") if section_of.get(line.line_number) == "URLHaus" and line.domain}


def repeats(lines):
    accepted = [line.domain for line in lines if line.dropped_because is None]
    return len(accepted) - len(set(accepted))


def line_kinds(lines):
    return dict(Counter(str(line.dropped_because or "accepted") for line in lines).most_common())


def punycode_names(lines):
    return sum(1 for line in lines if line.domain and "xn--" in line.domain)


def parent_domains(domain):
    labels = domain.split(".")
    return [".".join(labels[i:]) for i in range(1, len(labels) - 1)]


def title(text):
    print(f"\n=== {text} ===")


if __name__ == "__main__":
    main()
