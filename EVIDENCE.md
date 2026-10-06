# Evidence

Runs are in my Databricks Free Edition workspace (`notebooks/run.py`, `mode=live`). Each run's inputs are committed in
`snapshots/<snapshot_id>/`, so `mode=replay` reproduces the numbers. Expectations are committed before each run.

Numbers come from `feed_file_checks`, `reconciliation.sql`, `domain_changes.sql` and
`SELECT category, trust, count(*) FROM domain_current GROUP BY ALL`.

## Run 1

### Expected

Compared with the curl download from 2026-10-03:

- feed_c and feed_d: same files (sha256 `6179b450…e8`, `061f7953…8e`), same counts.
- feed_b: a new file (it expires every 12 hours), around 3,200 domains.
- feed_a: same file (sha256 `c90ebedf…1a`, 72,233 domains) unless there was a release after 2026-10-02 19:58 UTC,
  then within about 1%.
- All four accepted, unless Free Edition can't reach a host (`no_response`, run fails).
- About 158,000 domains, about 3,300 malware. Trust: about 83,000 `low` (everything only feed_c or feed_d list), no
  ads domain at `high` (feed_a is the only fresh ads feed), a few hundred malware at `high`. Check passes.

### Result

Snapshot `2026-10-04T120448Z`, committed in `snapshots/`.

| Feed | sha256 | Lines | Accepted | Distinct | Published | Expected? |
|---|---|---|---|---|---|---|
| feed_a | `c90ebedf…1a` | 79,056 | 72,233 | 72,233 | 2026-10-02 19:58 | yes, same file, no release since |
| feed_b | `673bacbc…2c` | 17,892 | 3,193 | 3,193 | 2026-10-04 00:06 | yes, new file; 14,693 IPs (82%) |
| feed_c | `6179b450…e8` | 89,840 | 89,822 | 89,822 | 2024-05-12 06:39 | yes, same file |
| feed_d | `061f7953…8e` | 1,738 | 1,707 | 1,645 | none | yes, same file |

- All four accepted, every `lines_add_up` true.
- 158,109 domains in `domain_current`, `adds_up` true. 3,235 malware: feed_b's 3,193 plus 42 names other feeds list
  under one of feed_b's `||parent^` rules.

| category | trust | domains |
|---|---|---|
| ads_and_trackers | low | 83,013 |
| ads_and_trackers | medium | 71,861 |
| malware | high | 372 |
| malware | medium | 2,863 |

- `domain_changes`: 158,109 `added`, as expected on a first snapshot.
- feed_b between the 2026-10-03 curl download and this run: 31 domains added, 83 removed, 3,162 kept.

What didn't go as expected: the notebook failed at the lookup cell (`CANNOT_DETERMINE_TYPE`, building a DataFrame
from a row whose `fresh_sources` was an empty list). The tables were already written, so the data was fine, but the
check cell after it never ran. Fixed by returning the lookup as a DataFrame; the checks above come from a replay of
the committed snapshot, which gives the same tables.

## Run 2

### Expected

The next day, against run 1:

- feed_c and feed_d: same sha256 again.
- feed_b: a new file, roughly 3,100–3,300 domains, accepted (the cut-off line is 80% of 3,193 = 2,554). From one
  day of data: a few dozen domains added and up to about a hundred removed.
- feed_a: either the same file, or a new release (they come every 2–5 days, the last was 2026-10-02) within about
  1% of 72,233 domains.
- `previous_accepted_lines` filled in for all four; nothing rejected, the check passes.
- `domain_changes`: only feed_b's churn if feed_a hasn't released, i.e. tens to about a hundred `added` and
  `removed`, almost all malware, plus a few `category_changed` for names also in feed_a. If feed_a released, a few
  hundred more on the ads side. No `trust_changed` from age: feed_b is republished daily and feed_a stays under 30
  days.
- Domains that didn't change keep their `answer_since` from run 1; `domain_history` grows only by the changes.

### Result

Snapshot `2026-10-05T162535Z`, committed in `snapshots/`.

| Feed | sha256 | Accepted | Previous accepted | Published | Expected? |
|---|---|---|---|---|---|
| feed_a | `c90ebedf…1a` | 72,233 | 72,233 | 2026-10-02 19:58 | yes, same file: no release in 3 days |
| feed_b | `2672fe75…3b` | 3,130 | 3,193 | 2026-10-05 12:07 | yes, new file, 98% of the previous one |
| feed_c | `6179b450…e8` | 89,822 | 89,822 | 2024-05-12 06:39 | yes, same file |
| feed_d | `061f7953…8e` | 1,707 | 1,707 | none | yes, same file |

- Nothing rejected, every `lines_add_up` true, the check passes.
- 158,044 domains in `domain_current` (166,830 listings), `adds_up` true.

`domain_changes`:

| change | domains | |
|---|---|---|
| added | 57 | all malware, new in feed_b |
| removed | 122 | all malware, gone from feed_b |
| category_changed | 24 | 13 ads → malware (feed_b started listing a feed_a domain), 11 malware → ads (the reverse) |

- No `sources_changed` or `trust_changed`, and nothing on the ads side, since feed_a didn't release.
- 157,963 domains still have `answer_since` = run 1; 81 (57 added + 24 changed) start at run 2.
- `domain_history`: 158,190 rows = 158,044 current + 146 closed (122 removed + 24 changed category).

| category | trust | run 1 | run 2 |
|---|---|---|---|
| ads_and_trackers | low | 83,013 | 83,013 |
| ads_and_trackers | medium | 71,861 | 71,859 |
| malware | high | 372 | 374 |
| malware | medium | 2,863 | 2,798 |

Against the expectation: everything held except the size of feed_b's churn. 122 removed is a bit more than "up to
about a hundred"; one earlier day (2026-10-03 → 2026-10-04) isn't enough to know the normal range.

## Broken feed

TODO. One feed's file replaced by an HTML error page. Expected: `not_a_text_list`, the feed keeps its previous file.

## Replay

TODO. Same numbers as the live runs.
