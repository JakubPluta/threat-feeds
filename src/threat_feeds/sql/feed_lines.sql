-- feed_lines: one row per line of every downloaded file, dropped lines included.

CREATE TABLE IF NOT EXISTS feed_lines (
  snapshot_id STRING,
  feed STRING,
  line_number INT COMMENT '1-based',
  text STRING COMMENT 'As in the file',
  domain STRING COMMENT 'Lowercased; NULL when dropped',
  dropped_because STRING COMMENT 'DropReason; NULL = accepted'
) COMMENT 'One row per line of every downloaded file, dropped lines included'
