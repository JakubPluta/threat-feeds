-- domain_current: one row per domain listed in the latest snapshot, with its current answer.

SELECT
  answers.domain,
  answers.category,
  answers.sources,
  answers.fresh_sources,
  answers.trust,
  answers.newest_source_published_at,
  domain_history.valid_from AS answer_since,
  answers.snapshot_taken_at AS as_of
FROM domain_answers_by_snapshot AS answers
JOIN domain_history
  ON domain_history.domain = answers.domain
  AND domain_history.valid_to IS NULL
WHERE answers.snapshot_id = (SELECT max(snapshot_id) FROM feed_files)
