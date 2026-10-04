# Decisions

Numbers are from the 2026-10-03 download, see [investigation/README.md](investigation/README.md). A *snapshot* is one
download of all four feeds; *dropped* is a line that isn't a domain, *rejected* is a whole file that isn't used.

## Things in the data worth knowing

- feed_c hasn't changed since 2024-05-12 and feed_d has no date at all, but both return 200 every day. 52% of the
  domains (83,013 of 158,150) are listed only by these two.
- feed_a bundles URLhaus, which is also feed_b's source. 338 of the 341 category conflicts come from that.
- `||x.com^` (feed_b, feed_c) also blocks subdomains, a hosts line (feed_a, feed_d) doesn't.
- 14,555 of feed_b's 17,806 lines are IP addresses.
- Many feed_b domains are subdomains on shared hosting (`r2.dev`, `workers.dev`), so names can't be cut down to the
  registrable domain.

## Layers

Bronze is the snapshot folders (raw bodies plus status and headers). Silver is `feed_files` (one row per file) and
`feed_lines` (one row per line, dropped ones included). Gold is rebuilt from silver on every run. No DLT or dbt: too
much setup for four files a day, and DLT would tie the tests to Databricks.

## Freshness

A listing is fresh if the provider's publish date in the file header is at most 2 days old for malware and 30 for
ads_and_trackers. No date means not fresh. The download date would make feed_c look fresh every day, and GitHub raw
(feed_a, feed_d) doesn't send `Last-Modified`.

2 days because feed_b expires every 12 hours. 30 is a guess; anything from about 7 to 400 gives the same result
today.

## Trust

- `high`: two or more fresh feeds
- `medium`: one fresh feed
- `low`: no fresh feed

Stale feeds are still listed in `sources` but don't raise trust. At first `high` only needed one of the feeds to be
fresh, which gave 20,560 ad domains `high` because feed_c, untouched since 2024, also listed them. With one fresh ads
feed, no ads domain is `high` today.

No weighted score: there's nothing to fit weights against. Known problem: most of the 382 malware domains at `high`
are the URLhaus copy in feed_a, so really one source.

## One category per domain

When feeds disagree, malware wins. Majority vote would let three ad lists outvote the only malware list.

## Low trust is still published

Everything a feed lists is in `domain_current`, `low` included; the consumer picks which trust levels to block on.
Dropping `low` would remove 52% of the domains.

## Rejected files

A file is rejected when there's no response, the status isn't 200, the content type isn't `text/plain`, more than 5%
of its rules can't be parsed, or it has fewer than 80% of the domains of the feed's previous accepted file.

The feed then keeps using its last accepted file. Leaving it out instead would mean one feed_a timeout removes 72k
domains for a day and adds them back the next, with both showing up in the history. The 80% is a guess that the
first few weeks of runs should check.

## Parsing

Only syntax that's actually in the files is handled. Anything else is dropped as `unreadable_rule` and counted, so
it shows up instead of being guessed at.

## History

`domain_history` is recomputed from all snapshots on every run (gaps and islands), not updated with `MERGE`. Same
snapshots, same history, and a failed run can't leave it half-written. A new version starts when the category,
sources or trust change; the publish date is left out, or every feed_a release would add 72k versions.

Changing a rule rewrites past history. What was actually published on a given day is in the Delta history of
`domain_current`.

`domain_lookup.sql` repeats the category and trust logic so it can answer for names no feed lists. A test checks it
agrees with `domain_current`.

## Reruns and scheduling

Loading a snapshot replaces its rows (`replaceWhere`) and replay empties silver first, so reruns don't duplicate.
A feed added later is missing from older snapshot folders and is skipped there. Scheduling is the notebook's Schedule
button, not an Asset Bundle, so the repo runs from a Git folder without the CLI.

The last notebook cell fails the run if a file of the latest snapshot was rejected or the counts don't match. It
runs after the tables are written, so the job goes red but the data is still updated.
