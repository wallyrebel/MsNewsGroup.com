# NewsBreak WordPress Feed Playbook

Goal: maximize NewsBreak ingestion quality using native WordPress feeds only.

## Feed Strategy (Inside WordPress)

1. Use primary RSS endpoint: `https://msnewsgroup.com/feed/`.
2. Keep feed URLs stable; do not proxy through external feed hosts.
3. If needed, also provide category-specific feeds (native WordPress URLs).

## Required Feed Quality

1. Include complete headline, permalink, and publication date for each item.
2. Include full article content (not excerpts/truncated summaries).
3. Ensure each item includes an image in content or enclosure.
4. Keep article canonical URLs stable and publicly crawlable.
5. Avoid anti-bot/firewall rules that block feed access.

## WP Configuration

1. `Settings -> Reading`: set feed content to `Full text`.
2. Ensure featured images are mandatory in editorial workflow.
3. Enable Open Graph output so article pages resolve `og:image`.
4. Keep permalinks consistent.
5. Clear caching/CDN layers after feed or SEO setting changes.

## Troubleshooting

1. Validate `/feed/` as XML and confirm HTTP 200.
2. Inspect random feed items for images and sufficient content length.
3. If excerpts persist, check theme/plugin filters overriding feed content.
4. Re-test feed after SEO plugin updates.
5. Re-submit feed URL in NewsBreak partner workflow when major template changes occur.
