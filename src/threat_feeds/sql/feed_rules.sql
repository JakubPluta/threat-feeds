-- feed_rules: the rules from feeds.py, one row per feed, rewritten every run.

CREATE TABLE IF NOT EXISTS feed_rules (
  feed STRING,
  category STRING COMMENT 'Our category: malware or ads_and_trackers',
  covers_subdomains BOOLEAN COMMENT 'True for adblock ||x.com^ rules, false for hosts lines',
  severity INT COMMENT 'Higher wins when feeds disagree on the category',
  fresh_for_days INT COMMENT 'Max age of the publish date for a listing to count as fresh'
) COMMENT 'One row per feed'
