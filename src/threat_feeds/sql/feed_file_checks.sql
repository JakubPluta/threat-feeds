-- feed_file_checks: per downloaded file, whether it was accepted, which file is in use, and its line counts.

CREATE OR REPLACE VIEW feed_file_checks AS
-- stored lines per file
WITH line_counts AS (
  SELECT snapshot_id, feed, count(*) AS lines, count(DISTINCT domain) AS distinct_domains
  FROM feed_lines
  GROUP BY snapshot_id, feed
),
-- dropped lines per file and reason
dropped_by_reason AS (
  SELECT snapshot_id, feed, dropped_because, count(*) AS lines
  FROM feed_lines
  WHERE dropped_because IS NOT NULL
  GROUP BY snapshot_id, feed, dropped_because
),
-- the same as one map per file, e.g. {blank -> 2, comment -> 40}
dropped_lines AS (
  SELECT snapshot_id, feed,
    map_from_entries(array_sort(collect_list(struct(dropped_because, lines)))) AS dropped_lines
  FROM dropped_by_reason
  GROUP BY snapshot_id, feed
)
SELECT
  feed_files.snapshot_id,
  feed_files.feed,
  feed_files.rejected_because,
  feed_file_in_use.used_file_snapshot_id,  -- NULL if the feed has no accepted file yet
  feed_files.provider_published_at,
  feed_files.line_count,
  feed_files.accepted_lines,
  line_counts.distinct_domains,
  dropped_lines.dropped_lines,
  feed_files.previous_accepted_lines,
  feed_files.line_count = coalesce(line_counts.lines, 0) AS lines_add_up  -- false if lines were stored twice or lost
FROM feed_files
JOIN feed_file_in_use USING (snapshot_id, feed)
LEFT JOIN line_counts USING (snapshot_id, feed)
LEFT JOIN dropped_lines USING (snapshot_id, feed)
