# Bing News + WordPress Checklist

## Bing Webmaster Tools

1. Add and verify `https://msnewsgroup.com/`.
2. Submit XML sitemap URL(s).
3. Check crawl diagnostics and index coverage regularly.
4. Use URL inspection on newly published articles.
5. Monitor malware/security warnings and fix immediately.

## Bing News Readiness Signals

1. Clear article headlines and stable URLs.
2. Byline and publication date visible on article pages.
3. Full article content accessible without hard paywall blocks.
4. Proper canonical tags for each article.
5. Structured data present (Article/NewsArticle).

## WordPress Ops Checks

1. Ensure posts are indexable in SEO plugin content type settings.
2. Keep feed endpoints crawlable (`/feed/` and category feeds when used).
3. Avoid blocking bots in security plugins/CDN rules.
4. Keep theme templates outputting `wp_head()` to emit SEO metadata.
5. Validate that featured image is set and exposed via `og:image`.
