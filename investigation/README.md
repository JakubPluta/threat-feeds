# What the four feeds contain

Files and HTTP headers downloaded with curl on 2026-10-03 are in `2026-10-03/`. The numbers come from
`uv run python investigation/explore.py`, which uses the pipeline's parser. What the pipeline does about each finding
is in [DECISIONS.md](../DECISIONS.md).

| | feed_a | feed_b | feed_c | feed_d |
|---|---|---|---|---|
| Provider | StevenBlack/hosts | malware-filter (URLhaus) | 1Hosts Lite | jdlingyu/ad-wars |
| Format | hosts | adblock | adblock | hosts |
| Publish date in header | 2026-10-02 | 2026-10-03 | 2024-05-12 | none |
| Lines | 79,056 | 17,806 | 89,840 | 1,738 |
| … accepted | 72,233 | 3,245 | 89,822 | 1,707 |
| … comment | 4,274 | 6 | 17 | 21 |
| … blank | 2,535 | | 1 | 8 |
| … ip_address | | 14,555 | | |
| … local_machine_name | 14 | | | 2 |
| Distinct domains | 72,233 | 3,245 | 89,822 | 1,645 |
| In no other feed | 63,882 | 2,903 | 81,776 | 902 |

All four: 166,945 listings, 158,150 distinct domains.

## Findings

1. feed_c hasn't changed since 2024-05-12 (header and `Last-Modified` agree), feed_d has no date. Both return 200.
   83,013 domains (52%) are listed only by these two.
2. 82% of feed_b's lines are IP addresses.
3. feed_b's domains are mostly subdomains on shared platforms: `r2.dev` (88), `workers.dev` (34), `pages.dev` (23),
   `vercel.app` (21), `duckdns.org` (20).
4. 12,830 names in feed_a and 706 in feed_d are already covered by a `||parent^` rule in feed_b or feed_c, e.g.
   `stats.g.doubleclick.net` (feed_a) under `||doubleclick.net^` (feed_c).
5. Category conflicts exist only between feed_a and feed_b: 341 domains. feed_a is 16 upstream lists glued together,
   one of them `URLHaus` (395 hosts), which is also feed_b's source. 338 conflicts come from that section; only
   `old.umcl.us`, `posicionamientonatural.es` and `ss-01.com` don't. 57 hosts of the section aren't in feed_b.
6. feed_d has a section its author says can break apps (`【提示误伤】选择性不√以下子项`), 25 ad hosts such as Tencent's
   `*.gdt.qq.com` and WeChat's `wxsnsdy.wxs.qq.com`.
7. feed_d repeats 62 domains within the file.
8. Every rule in all four files parses: trailing comments (358 in feed_a), one uppercase name (`mobile.Banzai.it`),
   punycode (feed_a 27, feed_b 3, feed_c 38), localhost entries.
9. The counts in two headers match the parser: feed_a `72,233`, feed_c `89,822`.
10. feed_b says `! Expires: 12 hours`.

## Not from the script

- feed_a releases every 2–5 days (StevenBlack/hosts commit history, checked 2026-10-03).
- feed_d's `hosts` was last committed 2023-11-17.
- The 1Hosts repo was last pushed 2026-09-03, so feed_c's URL looks like an abandoned mirror.
- feed_b's README says popular domains are blocked by URL, not whole domain. Might explain the 57 hosts; not checked.
- The translation of feed_d's Chinese comments is a machine translation.
