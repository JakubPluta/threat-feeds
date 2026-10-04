-- feed_file_in_use: for each snapshot and feed, the snapshot whose file is used (the feed's last accepted one).

CREATE OR REPLACE VIEW feed_file_in_use AS
SELECT
  snapshot_id,
  to_timestamp(snapshot_id, "yyyy-MM-dd'T'HHmmssX") AS snapshot_taken_at,  -- X reads the trailing Z as UTC
  feed,
  max(CASE WHEN rejected_because IS NULL THEN snapshot_id END)
    OVER (PARTITION BY feed ORDER BY snapshot_id) AS used_file_snapshot_id  -- NULL before the first accepted file
FROM feed_files
