# Google News + WordPress Checklist

## Search Console Setup

1. Add property for `https://msnewsgroup.com/` in Google Search Console.
2. Verify ownership (DNS preferred).
3. Submit sitemap URL (core or SEO plugin generated).
4. Confirm sitemap is processing without critical errors.
5. Use URL Inspection for fresh article URLs and request indexing as needed.

## Publisher Center Setup

1. Add publication in Google Publisher Center.
2. Set publication URL, logo, and contact details.
3. Define sections using URLs that map to WordPress categories/tags or feeds.
4. Validate that section URLs return crawlable HTML/RSS and are not blocked by robots.
5. Keep publication metadata current after rebranding/theme changes.

## WP-Specific Checks Before Submission

1. `Settings -> Reading`: RSS includes `Full text`.
2. SEO plugin outputs canonical, Open Graph, and schema on single posts.
3. XML sitemap is enabled and visible in `robots.txt` via `Sitemap:` line.
4. Posts include publish/updated dates and featured images.
5. `meta robots` on posts is `index,follow` unless intentionally overridden.
