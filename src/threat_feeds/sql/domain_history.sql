-- domain_history: every answer a domain has had and when it was valid (valid_to NULL = current).

-- snapshots in order, with the time of the next one
WITH snapshots AS (
  SELECT
    snapshot_id,
    snapshot_taken_at,
    row_number() OVER (ORDER BY snapshot_id) AS snapshot_number,
    lead(snapshot_taken_at) OVER (ORDER BY snapshot_id) AS next_snapshot_taken_at
  FROM (SELECT DISTINCT snapshot_id, snapshot_taken_at FROM domain_answers_by_snapshot)
),
-- gaps and islands: consecutive snapshots with the same answer get the same same_answer_group
numbered_answers AS (
  SELECT
    answers.domain,
    answers.category,
    answers.sources,
    answers.trust,
    snapshots.snapshot_number,
    snapshots.snapshot_taken_at,
    snapshots.next_snapshot_taken_at,
    snapshots.snapshot_number - row_number() OVER (
      -- publish date deliberately left out, see "History" in DECISIONS.md
      PARTITION BY answers.domain, answers.category, answers.sources, answers.trust
      ORDER BY snapshots.snapshot_number
    ) AS same_answer_group
  FROM domain_answers_by_snapshot AS answers
  JOIN snapshots USING (snapshot_id)
)
SELECT
  domain,
  category,
  sources,
  trust,
  min(snapshot_taken_at) AS valid_from,
  max_by(next_snapshot_taken_at, snapshot_number) AS valid_to
FROM numbered_answers
GROUP BY domain, category, sources, trust, same_answer_group
