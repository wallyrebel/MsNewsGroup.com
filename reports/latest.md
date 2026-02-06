# WordPress News Visibility Ops Report
- Site: `https://msnewsgroup.com/`
- Generated (UTC): `2026-02-06T17:09:51+00:00`

## What's Broken / Missing
- [P1] Feed has elevated NewsBreak ingestion risk - Feed content appears excerpt-only.
- [P1] JSON-LD Article/NewsArticle schema is missing on sampled pages - 10 of 10 pages lacked Article schema.

## Findings Snapshot
| Check | Result |
|---|---|
| Sitemap endpoints reachable | 2/4 |
| Feed items parsed | 10 |
| Feed title/link/date coverage | 10/10/10 |
| Feed image coverage | 9/10 |
| NewsBreak risk | YES |
| Articles sampled/fetched | 10/10 |
| Missing canonical | 0 |
| Noindex pages | 0 |
| Missing JSON-LD Article | 10 |
| Avg response size (bytes) | 91457 |

## Remediation Plan
### P0
- None detected.

### P1
- **Feed has elevated NewsBreak ingestion risk**
  Evidence: Feed content appears excerpt-only.
  Fix: Switch RSS to full text and include featured images in feed items.
- **JSON-LD Article/NewsArticle schema is missing on sampled pages**
  Evidence: 10 of 10 pages lacked Article schema.
  Fix: Enable schema output for Posts in your SEO plugin and map it to Article or NewsArticle.

### P2
- None detected.

## Exact WordPress Fixes
### Rank Math
- `Rank Math -> Titles & Meta -> Posts`: set Robots Meta to `index`, enable canonical defaults.
- `Rank Math -> Sitemap Settings`: enable XML sitemap and include Posts; enable News Sitemap if available in your plan.
- `Rank Math -> General Settings -> Social Meta`: enable Open Graph and set fallback image.
- `Rank Math -> Schema (per post type)`: map Posts to `Article` or `NewsArticle` and ensure author/publisher are set.

### Yoast SEO
- `SEO -> Search Appearance -> Content Types -> Posts`: set Show in search results = `Yes`.
- `SEO -> Settings -> Site features`: ensure XML sitemaps are `On`.
- `SEO -> Social`: enable Open Graph meta data and set default image.
- `SEO -> Search Appearance`: verify schema output remains enabled for posts.

### All in One SEO (AIOSEO)
- `AIOSEO -> Search Appearance -> Content Types -> Posts`: set Robots = `Index` and enable canonical URL output.
- `AIOSEO -> Sitemaps`: enable XML sitemap; enable News sitemap module if available.
- `AIOSEO -> Social Networks`: enable Open Graph and default post image source = featured image.
- `AIOSEO -> Schema`: set default post schema to `Article` or `NewsArticle`.

### Plugin-Agnostic WP Admin Areas
- `Settings -> Reading`: set `For each post in a feed, include` to `Full text`.
- `Settings -> Permalinks`: keep stable post permalinks and avoid frequent structure changes.
- Theme check: confirm `wp_head()` exists in `header.php` and `wp_footer()` in footer template.


## Theme Snippets (Minimal PHP)
```php
<?php
// 1) Canonical fallback in header.php (if SEO plugin is missing canonical output).
if (is_single()) {
    echo '<link rel="canonical" href="' . esc_url(get_permalink()) . '" />' . PHP_EOL;
}
```

```php
<?php
// 2) Publish/modified dates in single.php.
if (is_single()) :
    $published = get_the_date('c');
    $modified = get_the_modified_date('c');
    ?>
    <p class="post-dates">
        Published <time datetime="<?php echo esc_attr($published); ?>"><?php echo esc_html(get_the_date()); ?></time>
        | Updated <time datetime="<?php echo esc_attr($modified); ?>"><?php echo esc_html(get_the_modified_date()); ?></time>
    </p>
<?php endif; ?>
```

```php
<?php
// 3) Ensure featured image is available for OG image generation.
if (is_single() && !has_post_thumbnail()) {
    // Optional: set or prompt for a default featured image workflow.
}
```


## Submission Checklist
- Google Search Console
  - Verify property for `https://msnewsgroup.com/`.
  - Submit primary XML sitemap (core or plugin sitemap URL).
  - Use URL Inspection on fresh articles and request indexing when needed.
  - In Publisher Center, maintain publication details and section URLs.
- Bing Webmaster Tools
  - Verify site and submit sitemap URL(s).
  - Check crawl controls, URL inspection, and indexing reports.
  - Confirm RSS/feed URLs are crawlable and return full content.
- NewsBreak Feed Submission
  - Submit the native WordPress feed URL (`/feed/` or category feed if required).
  - Ensure feed items include full content, dates, canonical links, and images.
  - Re-test feed validity after every major plugin/theme update.


## References
- `docs/google_news_wp_checklist.md`
- `docs/bing_news_wp_checklist.md`
- `docs/newsbreak_wp_feed_playbook.md`
- `docs/schema_validation_playbook.md`
