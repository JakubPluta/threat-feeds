-- domain_changes: how many domains the latest snapshot added, removed or changed, by kind of change.

-- time of the latest snapshot
WITH latest AS (
  SELECT max(snapshot_taken_at) AS taken_at FROM feed_file_in_use
),
-- history rows starting at the latest snapshot
started AS (
  SELECT domain_history.*
  FROM domain_history
  JOIN latest ON domain_history.valid_from = latest.taken_at
),
-- history rows ending at the latest snapshot
ended AS (
  SELECT domain_history.*
  FROM domain_history
  JOIN latest ON domain_history.valid_to = latest.taken_at
),
-- one row per changed domain; if several things changed, the first matching kind is used
changes AS (
  SELECT
    CASE
      WHEN ended.domain IS NULL THEN 'added'
      WHEN started.domain IS NULL THEN 'removed'
      WHEN started.category != ended.category THEN 'category_changed'
      WHEN started.sources != ended.sources THEN 'sources_changed'
      ELSE 'trust_changed'
    END AS change
  FROM started
  FULL OUTER JOIN ended ON started.domain = ended.domain
)
SELECT change, count(*) AS domains
FROM changes
GROUP BY change
ORDER BY change
