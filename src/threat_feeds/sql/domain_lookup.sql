-- domain_lookup: latest answer for any :domain, also subdomains no feed lists but a ||parent^ rule covers.

-- latest listings of the name, or of a parent that covers its subdomains
WITH matching_listings AS (
  SELECT *
  FROM domain_listings
  WHERE snapshot_id = (SELECT max(snapshot_id) FROM feed_files)
    AND (
      domain = lower(:domain)
      OR (covers_subdomains AND endswith(lower(:domain), concat('.', domain)))
    )
)
SELECT
  lower(:domain) AS domain,
  count(*) > 0 AS harmful,
  max_by(category, severity) AS category,
  array_sort(collect_set(feed)) AS sources,
  array_sort(collect_set(CASE WHEN is_fresh THEN feed END)) AS fresh_sources,
  -- same rule as domain_answers_by_snapshot.sql
  CASE
    WHEN count(*) = 0 THEN NULL
    WHEN NOT bool_or(is_fresh) THEN 'low'
    WHEN count(DISTINCT CASE WHEN is_fresh THEN feed END) >= 2 THEN 'high'
    ELSE 'medium'
  END AS trust,
  max(provider_published_at) AS newest_source_published_at,
  array_sort(collect_set(domain)) AS listed_as  -- the listed names that matched
FROM matching_listings
