# Harmful-domain feeds

Loads four public blocklists (feed_a to feed_d) into Delta tables. For any domain they tell you whether it is harmful,
its category, which feeds list it, how much to trust that, whether it is still current, and how the answer changed
over time.

## Run it on Databricks

1. **Workspace → Create → Git folder**, paste this repository's URL.
2. Open `notebooks/run.py` → **Run all**. The default `mode=replay` rebuilds everything from the snapshots committed
   in `snapshots/`, so you get the numbers in EVIDENCE.md.
3. To run it every morning: **Schedule** in the notebook, daily, with `mode=live`. The run fails when a file was
   rejected or the numbers don't add up.

## Run it locally

```
make install
make test      # the Spark tests need Java 17+
make snapshot  # downloads the four feeds once into snapshots/
```

## What to query

```sql
SELECT * FROM workspace.threat_intel.domain_current WHERE domain = 'stats.g.doubleclick.net';  -- today's answer
SELECT * FROM workspace.threat_intel.domain_history WHERE domain = 'stats.g.doubleclick.net';  -- earlier answers
SELECT * FROM workspace.threat_intel.feed_file_checks ORDER BY snapshot_id DESC;               -- how each run went
```

`src/threat_feeds/sql/domain_lookup.sql` works for any name, including subdomains no feed lists.

## The rest

- [DECISIONS.md](DECISIONS.md): what I chose, what I rejected, and what would change my mind.
- [EVIDENCE.md](EVIDENCE.md): the runs, what I expected, and what changed between them.
- [NOTES.md](NOTES.md): what I left out and what I would do next.
- [investigation/README.md](investigation/README.md): what the feeds contain.
