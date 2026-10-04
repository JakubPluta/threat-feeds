# Notes

## Seen in the data, not handled

- feed_a includes URLhaus (feed_b's source): 338 domains get `high` trust from one source, and 57 hosts of that
  section that aren't in feed_b are filed as ads_and_trackers. Not filtered, because that would override feed_a's
  category from inside its file.
- feed_c's URL looks abandoned (file from 2024-05-12, the 1Hosts repo was updated 2026-09-03). Its 81,776 domains
  that no other feed lists are all `low`. Someone should check whether the URL should change.
- feed_d marks 25 hosts as possibly breaking apps (`【提示误伤】`, e.g. WeChat's `wxsnsdy.wxs.qq.com`). Accepted, since
  they are ad hosts; blocking them is the product's call.
- feed_b's IP addresses are dropped. Blocking IPs would need its own table.

## Not built

- A limit on `domain_changes`: a run where 40% of domains disappear still passes if every file is accepted.
- An expiry on a feed's last accepted file: a feed broken for a month keeps its old list.
- Incremental history: it's recomputed from every snapshot on each run, which will get slow at some point.
- Protection against two runs at once.
- Schema migrations: tables use `CREATE TABLE IF NOT EXISTS`, so a column change needs a manual `ALTER`.
- Alerting beyond the job's failure email.
- `mode=replay` empties silver, so it shouldn't be run on the production schema.
