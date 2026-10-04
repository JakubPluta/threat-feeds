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

TODO

## Run 2

TODO: expectations before the run.

## Broken feed

TODO. One feed's file replaced by an HTML error page. Expected: `not_a_text_list`, the feed keeps its previous file.

## Replay

TODO. Same numbers as the live runs.
