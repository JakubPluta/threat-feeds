-- domain_listings: one row per snapshot, feed and listed domain, from the file each feed currently uses.

CREATE OR REPLACE VIEW domain_listings AS
SELECT DISTINCT  -- a domain listed twice in one file counts once
  feed_file_in_use.snapshot_id,
  feed_file_in_use.snapshot_taken_at,
  feed_lines.domain,
  feed_rules.feed,
  feed_rules.category,
  feed_rules.severity,
  feed_rules.covers_subdomains,
  feed_files.provider_published_at,
  -- no publish date -> not fresh
  coalesce(
    feed_files.provider_published_at
      >= feed_file_in_use.snapshot_taken_at - make_dt_interval(feed_rules.fresh_for_days),
    false
  ) AS is_fresh
FROM feed_file_in_use
JOIN feed_files
  ON feed_files.snapshot_id = feed_file_in_use.used_file_snapshot_id
  AND feed_files.feed = feed_file_in_use.feed
JOIN feed_lines
  ON feed_lines.snapshot_id = feed_file_in_use.used_file_snapshot_id
  AND feed_lines.feed = feed_file_in_use.feed
JOIN feed_rules
  ON feed_rules.feed = feed_file_in_use.feed
WHERE feed_lines.domain IS NOT NULL
