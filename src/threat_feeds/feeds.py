"""The four feeds, our category for each, and how to parse their files."""

import ipaddress
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, HttpUrl

Category = Literal["malware", "ads_and_trackers"]
LineFormat = Literal["hosts", "adblock"]  # "0.0.0.0 x.com" blocks x.com; "||x.com^" also blocks its subdomains


class DropReason(StrEnum):
    """Why a line didn't become a domain."""

    BLANK = "blank"
    COMMENT = "comment"  # starts with # or !
    UNREADABLE_RULE = "unreadable_rule"  # anything else we can't parse, e.g. "@@||x.com^" or "1.2.3.4 x.com"
    LOCAL_MACHINE_NAME = "local_machine_name"  # localhost, broadcasthost, ip6-*
    IP_ADDRESS = "ip_address"


class ParsedLine(NamedTuple):
    line_number: int
    text: str  # as in the file
    domain: str | None  # None when dropped
    dropped_because: DropReason | None

    def as_row(self) -> dict[str, object]:
        row = self._asdict()
        row["dropped_because"] = str(self.dropped_because) if self.dropped_because else None  # Spark wants str
        return row


class Feed(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    url: HttpUrl
    category: Category  # ours, not the provider's
    line_format: LineFormat
    publish_date_pattern: str | None = None  # regex, group 1 is the date
    publish_date_format: str | None = None  # strptime format; None means ISO 8601

    def parse(self, text: str) -> list[ParsedLine]:
        """One ParsedLine per line, dropped lines included."""
        parsed = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            domain = None
            match line.strip():
                case "":
                    dropped_because = DropReason.BLANK
                case comment if comment.startswith(COMMENT_MARKERS):
                    dropped_because = DropReason.COMMENT
                case rule:
                    name = name_in_rule(self.line_format, rule)
                    dropped_because = drop_reason(name)
                    if dropped_because is None:
                        domain = name
            parsed.append(ParsedLine(line_number, line, domain, dropped_because))
        return parsed

    def publish_date(self, text: str) -> datetime | None:
        """The provider's publish date from the file header, in UTC. None if there isn't one."""
        if self.publish_date_pattern is None:
            return None
        header_lines = text.splitlines()[:HEADER_LINES]
        header = "\n".join(header_lines)
        found = re.search(self.publish_date_pattern, header, re.M)
        if found is None:
            return None
        date_text = found[1]
        if self.publish_date_format:
            date = datetime.strptime(date_text, self.publish_date_format)
        else:
            date = datetime.fromisoformat(date_text)
        if date.tzinfo is None:  # feed_a's date has no offset, the header says it's UTC
            date = date.replace(tzinfo=UTC)
        return date.astimezone(UTC)

    @property
    def covers_subdomains(self) -> bool:
        return self.line_format == "adblock"

    def as_row(self) -> dict[str, object]:
        """Row of the feed_rules table."""
        return {
            "feed": self.name,
            "category": self.category,
            "covers_subdomains": self.covers_subdomains,
            "severity": SEVERITY[self.category],
            "fresh_for_days": FRESH_FOR_DAYS[self.category],
        }


FEEDS = (
    Feed(
        name="feed_a",
        url="https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts",
        category="ads_and_trackers",
        line_format="hosts",
        publish_date_pattern=r"^# Date: (.+) \(UTC\)$",  # "# Date: 02 October 2026 19:58:39 (UTC)"
        publish_date_format="%d %B %Y %H:%M:%S",
    ),
    Feed(
        name="feed_b",
        url="https://malware-filter.gitlab.io/malware-filter/urlhaus-filter-agh.txt",
        category="malware",
        line_format="adblock",
        publish_date_pattern=r"^! Updated: (\S+)",  # "! Updated: 2026-10-03T00:09:45Z"
    ),
    Feed(
        name="feed_c",
        url="https://badmojr.gitlab.io/1hosts/Lite/adblock.txt",
        category="ads_and_trackers",
        line_format="adblock",
        publish_date_pattern=r"^! Last modified: (\S+)",  # "! Last modified: 2024-05-12T06:39:45.794Z"
    ),
    Feed(
        name="feed_d",
        url="https://raw.githubusercontent.com/jdlingyu/ad-wars/master/hosts",
        category="ads_and_trackers",
        line_format="hosts",
    ),
)

SEVERITY: dict[Category, int] = {"malware": 2, "ads_and_trackers": 1}  # feeds disagree -> higher severity wins
# max age of the provider's publish date for a listing to count as fresh (DECISIONS.md explains the numbers)
FRESH_FOR_DAYS: dict[Category, int] = {"malware": 2, "ads_and_trackers": 30}

COMMENT_MARKERS = ("#", "!")
BLOCKING_ADDRESSES = {"0.0.0.0", "127.0.0.1"}
LOCAL_MACHINE_NAMES = {
    "localhost", "localhost.localdomain", "local", "broadcasthost", "0.0.0.0",
    "ip6-localhost", "ip6-loopback", "ip6-localnet", "ip6-mcastprefix",
    "ip6-allnodes", "ip6-allrouters", "ip6-allhosts",
}  # fmt: skip
ADBLOCK_RULE = re.compile(r"\|\|([^\^/$*|@]+)\^")  # plain ||name^ only
DNS_LABEL = re.compile(r"(?!-)[a-z0-9_-]{1,63}(?<!-)")
HEADER_LINES = 60  # where to look for the publish date


def name_in_rule(line_format: LineFormat, rule: str) -> str | None:
    """Lowercased name the rule blocks, or None if we can't read the rule."""
    rule_without_comment = rule.split("#", 1)[0]
    words = rule_without_comment.split()
    match line_format, words:
        case "hosts", [address, name] if address in BLOCKING_ADDRESSES or name in LOCAL_MACHINE_NAMES:
            return name.lower()
        case "adblock", [adblock_rule] if found := ADBLOCK_RULE.fullmatch(adblock_rule):
            return found[1].lower()
        case _:
            return None


def drop_reason(name: str | None) -> DropReason | None:
    # first match wins, so each line gets exactly one reason
    if name is None:
        return DropReason.UNREADABLE_RULE
    if name in LOCAL_MACHINE_NAMES:
        return DropReason.LOCAL_MACHINE_NAME
    if is_ip_address(name):
        return DropReason.IP_ADDRESS
    if not is_hostname(name):
        return DropReason.UNREADABLE_RULE
    return None


def is_ip_address(name: str) -> bool:
    try:
        ipaddress.ip_address(name)
    except ValueError:
        return False
    return True


def is_hostname(name: str) -> bool:
    # two or more DNS labels; non-ASCII names fail, they aren't converted to punycode
    labels = name.split(".")
    return len(labels) >= 2 and all(DNS_LABEL.fullmatch(label) for label in labels)
