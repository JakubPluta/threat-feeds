-- domain_answers_by_snapshot: category, sources and trust for each listed domain on each snapshot.

CREATE OR REPLACE VIEW domain_answers_by_snapshot AS
-- each listed name split into labels: a.b.example.com -> [a, b, example, com]
WITH names AS (
  SELECT DISTINCT snapshot_id, domain, split(domain, '[.]') AS labels
  FROM domain_listings
),
-- each parent of each name, without the bare TLD: a.b.example.com -> b.example.com, example.com
parents AS (
  SELECT
    names.snapshot_id,
    names.domain,
    array_join(slice(names.labels, position + 1, size(names.labels)), '.') AS parent
  FROM names
  LATERAL VIEW posexplode(names.labels) AS position, label
  WHERE position BETWEEN 1 AND size(names.labels) - 2
),
-- listings of the name itself, plus ||parent^ listings of its parents
matching_listings AS (
  SELECT domain_listings.*
  FROM domain_listings
  UNION ALL
  SELECT domain_listings.snapshot_id, domain_listings.snapshot_taken_at, parents.domain, domain_listings.feed,
    domain_listings.category, domain_listings.severity, domain_listings.covers_subdomains,
    domain_listings.provider_published_at, domain_listings.is_fresh
  FROM parents
  JOIN domain_listings
    ON domain_listings.snapshot_id = parents.snapshot_id
    AND domain_listings.domain = parents.parent
    AND domain_listings.covers_subdomains
)
SELECT
  snapshot_id,
  snapshot_taken_at,
  domain,
  max_by(category, severity) AS category,
  array_sort(collect_set(feed)) AS sources,
  array_sort(collect_set(CASE WHEN is_fresh THEN feed END)) AS fresh_sources,
  CASE
    WHEN NOT bool_or(is_fresh) THEN 'low'                                     -- no fresh feed
    WHEN count(DISTINCT CASE WHEN is_fresh THEN feed END) >= 2 THEN 'high'  -- two or more fresh feeds
    ELSE 'medium'                                                             -- one fresh feed
  END AS trust,
  max(provider_published_at) AS newest_source_published_at
FROM matching_listings
GROUP BY snapshot_id, snapshot_taken_at, domain
