-- feed_files: one row per downloaded file.

CREATE TABLE IF NOT EXISTS feed_files (
  snapshot_id STRING COMMENT 'UTC time of the snapshot, e.g. 2026-10-03T065617Z',
  feed STRING,
  url STRING,
  started_at TIMESTAMP,
  http_status INT COMMENT 'NULL when there was no response',
  content_type STRING,
  error STRING COMMENT 'Why there was no response, e.g. a timeout',
  bytes BIGINT,
  sha256 STRING,
  line_count INT COMMENT 'Equals the number of rows for this file in feed_lines',
  accepted_lines INT COMMENT 'Lines that became a domain, repeats included',
  provider_published_at TIMESTAMP COMMENT 'Publish date from the file header; NULL if there is none',
  previous_accepted_lines INT COMMENT 'accepted_lines of the feed''s last accepted file before this one',
  rejected_because STRING COMMENT 'RejectReason; NULL = accepted'
) COMMENT 'One row per downloaded file'
