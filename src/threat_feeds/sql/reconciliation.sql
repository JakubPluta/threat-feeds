-- reconciliation: listings in the latest snapshot against rows in domain_current.

-- listings of the latest snapshot
WITH latest_listings AS (
  SELECT domain, feed
  FROM domain_listings
  WHERE snapshot_id = (SELECT max(snapshot_id) FROM feed_files)
),
-- listings, and distinct listed names
listing_counts AS (
  SELECT count(*) AS listings, count(DISTINCT domain) AS listed_names
  FROM latest_listings
),
-- rows, and distinct domains, in domain_current
current_counts AS (
  SELECT count(*) AS domain_current_rows, count(DISTINCT domain) AS domain_current_domains
  FROM domain_current
)
SELECT
  listing_counts.listings,
  listing_counts.listed_names,
  current_counts.domain_current_rows,
  current_counts.domain_current_domains,
  -- every listed name is in domain_current exactly once
  listing_counts.listed_names = current_counts.domain_current_rows
    AND current_counts.domain_current_rows = current_counts.domain_current_domains AS adds_up
FROM listing_counts
CROSS JOIN current_counts
