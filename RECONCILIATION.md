# Reconciliation

Run 1, snapshot `2026-10-04T120448Z`. From the lines in the four files to the rows of `domain_current`.

## Lines → accepted lines

| | feed_a | feed_b | feed_c | feed_d | total |
|---|---|---|---|---|---|
| lines in the file | 79,056 | 17,892 | 89,840 | 1,738 | 188,526 |
| − blank | 2,535 | 0 | 1 | 8 | 2,544 |
| − comment | 4,274 | 6 | 17 | 21 | 4,318 |
| − ip_address | 0 | 14,693 | 0 | 0 | 14,693 |
| − local_machine_name | 14 | 0 | 0 | 2 | 16 |
| − unreadable_rule | 0 | 0 | 0 | 0 | 0 |
| = accepted lines | 72,233 | 3,193 | 89,822 | 1,707 | 166,955 |

Per file, from `feed_file_checks`: `line_count` = `accepted_lines` + the values in `dropped_lines`, and
`lines_add_up` checks that `feed_lines` holds exactly `line_count` rows.

## Accepted lines → listings

| | feed_a | feed_b | feed_c | feed_d | total |
|---|---|---|---|---|---|
| accepted lines | 72,233 | 3,193 | 89,822 | 1,707 | 166,955 |
| − domain repeated in the same file | 0 | 0 | 0 | 62 | 62 |
| = listings (distinct domains per feed) | 72,233 | 3,193 | 89,822 | 1,645 | 166,893 |

## Listings → domains

| | domains | listings |
|---|---|---|
| listed by one feed | 149,433 | 149,433 |
| listed by two feeds | 8,568 | 17,136 |
| listed by three feeds | 108 | 324 |
| total | 158,109 | 166,893 |

166,893 listings − 158,109 domains = 8,784 listings of a domain another feed also lists (8,568 + 2 × 108).

## Domains → `domain_current`

| | |
|---|---|
| distinct listed domains | 158,109 |
| rows in `domain_current` | 158,109 |
| distinct domains in `domain_current` | 158,109 |

`reconciliation.sql` checks both equalities (`adds_up`). A `||parent^` rule doesn't add rows: it only adds sources to
names some feed already lists. Names nobody lists are answered by `domain_lookup.sql`, not stored.

## Queries

```sql
-- per file
SELECT feed, line_count, accepted_lines, distinct_domains, dropped_lines, lines_add_up
FROM workspace.threat_intel.feed_file_checks WHERE snapshot_id = '2026-10-04T120448Z';

-- listings and domains
SELECT count(*) AS listings, count(DISTINCT domain) AS domains
FROM workspace.threat_intel.domain_listings WHERE snapshot_id = '2026-10-04T120448Z';

-- domains by number of feeds
SELECT feeds, count(*) AS domains FROM (
  SELECT domain, count(*) AS feeds FROM workspace.threat_intel.domain_listings
  WHERE snapshot_id = '2026-10-04T120448Z' GROUP BY domain
) GROUP BY feeds ORDER BY feeds;
```

`src/threat_feeds/sql/reconciliation.sql` gives the last table.
