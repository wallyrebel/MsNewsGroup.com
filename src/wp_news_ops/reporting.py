from __future__ import annotations

from datetime import datetime
from typing import Any


def _ratio(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return count / total


def derive_issues(audit: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    robots = audit["discovery"]["robots"]
    sitemaps = audit["discovery"]["sitemaps"]
    feed = audit["feed"]
    summary = audit["articles"]["summary"]

    if robots.get("potentially_blocking_rules"):
        issues.append(
            {
                "priority": "P0",
                "title": "robots.txt may block news discovery paths",
                "evidence": ", ".join(robots["potentially_blocking_rules"]),
                "fix": "In WordPress, check SEO plugin robots settings and remove Disallow rules blocking /feed/ or sitemap endpoints.",
            }
        )

    sitemap_exists = any(item.get("exists") for item in sitemaps)
    if not sitemap_exists:
        issues.append(
            {
                "priority": "P0",
                "title": "No sitemap endpoint was reachable",
                "evidence": "None of /sitemap.xml, /sitemap_index.xml, /wp-sitemap.xml, /news-sitemap.xml returned 2xx/3xx.",
                "fix": "Enable XML sitemaps in your SEO plugin or core WordPress and verify robots.txt exposes a Sitemap line.",
            }
        )

    if feed["item_count"] == 0:
        issues.append(
            {
                "priority": "P0",
                "title": "No valid RSS feed items found",
                "evidence": "Feed discovery returned no usable entries.",
                "fix": "Ensure /feed/ returns valid RSS and is not cached/rewritten to HTML.",
            }
        )

    fetched = summary["fetched"]
    if fetched > 0 and summary["noindex_pages"] > 0:
        issues.append(
            {
                "priority": "P0",
                "title": "Some sampled articles are marked noindex",
                "evidence": f"{summary['noindex_pages']} of {fetched} sampled pages contain meta robots noindex.",
                "fix": "In SEO plugin settings, set posts to Index and remove per-post noindex overrides.",
            }
        )

    if fetched > 0 and _ratio(summary["missing_canonical"], fetched) > 0.2:
        issues.append(
            {
                "priority": "P1",
                "title": "Canonical tags are missing on many sampled articles",
                "evidence": f"{summary['missing_canonical']} of {fetched} pages were missing canonical.",
                "fix": "Enable canonical output in your SEO plugin and ensure single.php includes wp_head().",
            }
        )

    if fetched > 0 and _ratio(summary["canonical_mismatch"], fetched) > 0.2:
        issues.append(
            {
                "priority": "P1",
                "title": "Canonical URL mismatches article URL on sampled pages",
                "evidence": f"{summary['canonical_mismatch']} of {fetched} pages have inconsistent canonical URLs.",
                "fix": "Review permalink settings and avoid plugins that rewrite canonical URLs to archives or tracking URLs.",
            }
        )

    if feed["newsbreak_risk"]:
        issues.append(
            {
                "priority": "P1",
                "title": "Feed has elevated NewsBreak ingestion risk",
                "evidence": "; ".join(feed.get("newsbreak_risk_reasons", [])) or "Feed appears excerpt-only or image-light.",
                "fix": "Switch RSS to full text and include featured images in feed items.",
            }
        )

    if fetched > 0:
        missing_og = summary["missing_og_fields"]
        if _ratio(missing_og["og:image"], fetched) > 0.2:
            issues.append(
                {
                    "priority": "P1",
                    "title": "Open Graph images are missing on many sampled articles",
                    "evidence": f"{missing_og['og:image']} of {fetched} pages are missing og:image.",
                    "fix": "Set a featured image on all posts and enable Open Graph in SEO plugin social settings.",
                }
            )

        if _ratio(summary["missing_jsonld_article"], fetched) > 0.2:
            issues.append(
                {
                    "priority": "P1",
                    "title": "JSON-LD Article/NewsArticle schema is missing on sampled pages",
                    "evidence": f"{summary['missing_jsonld_article']} of {fetched} pages lacked Article schema.",
                    "fix": "Enable schema output for Posts in your SEO plugin and map it to Article or NewsArticle.",
                }
            )

        if _ratio(summary["missing_publication_date_html"], fetched) > 0.2:
            issues.append(
                {
                    "priority": "P1",
                    "title": "Publication date is not clearly visible in article HTML",
                    "evidence": f"{summary['missing_publication_date_html']} of {fetched} pages did not expose an obvious date signal.",
                    "fix": "Update single post template to render <time datetime> with published and updated timestamps.",
                }
            )

    if fetched > 0 and summary["avg_response_size_bytes"] > 1_500_000:
        issues.append(
            {
                "priority": "P2",
                "title": "Average sampled article response size is heavy",
                "evidence": f"Average response size is {summary['avg_response_size_bytes']} bytes.",
                "fix": "Compress images, reduce third-party scripts, and defer non-critical JS.",
            }
        )

    if fetched > 0 and summary["high_blocking_script_pages"] > 0:
        issues.append(
            {
                "priority": "P2",
                "title": "Potential render-blocking scripts detected",
                "evidence": f"{summary['high_blocking_script_pages']} sampled pages have many non-deferred scripts in <head>.",
                "fix": "Move non-critical scripts to footer or add defer/async where safe.",
            }
        )

    if fetched > 0 and _ratio(summary["missing_og_image_dimensions"], fetched) > 0.5:
        issues.append(
            {
                "priority": "P2",
                "title": "og:image dimensions are often missing",
                "evidence": f"{summary['missing_og_image_dimensions']} of {fetched} pages are missing og:image:width/height.",
                "fix": "Configure SEO plugin to emit og:image width/height metadata for featured images.",
            }
        )

    return sorted(issues, key=lambda item: item["priority"])


def _issue_section(issues: list[dict[str, str]], priority: str) -> str:
    matches = [issue for issue in issues if issue["priority"] == priority]
    if not matches:
        return f"### {priority}\n- None detected.\n"

    lines = [f"### {priority}"]
    for issue in matches:
        lines.append(f"- **{issue['title']}**")
        lines.append(f"  Evidence: {issue['evidence']}")
        lines.append(f"  Fix: {issue['fix']}")
    return "\n".join(lines) + "\n"


def _plugin_fix_matrix() -> str:
    return """## Exact WordPress Fixes
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
"""


def _theme_snippets() -> str:
    return """## Theme Snippets (Minimal PHP)
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
"""


def _submission_checklist() -> str:
    return """## Submission Checklist
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
"""


def _findings_table(audit: dict[str, Any]) -> str:
    feed = audit["feed"]
    summary = audit["articles"]["summary"]
    sitemaps = audit["discovery"]["sitemaps"]
    sitemap_found = sum(1 for item in sitemaps if item.get("exists"))

    lines = [
        "## Findings Snapshot",
        "| Check | Result |",
        "|---|---|",
        f"| Sitemap endpoints reachable | {sitemap_found}/{len(sitemaps)} |",
        f"| Feed items parsed | {feed['item_count']} |",
        f"| Feed title/link/date coverage | {feed['items_with_title']}/{feed['items_with_link']}/{feed['items_with_date']} |",
        f"| Feed image coverage | {feed['items_with_image']}/{feed['item_count'] if feed['item_count'] else 0} |",
        f"| NewsBreak risk | {'YES' if feed['newsbreak_risk'] else 'NO'} |",
        f"| Articles sampled/fetched | {summary['sampled']}/{summary['fetched']} |",
        f"| Missing canonical | {summary['missing_canonical']} |",
        f"| Noindex pages | {summary['noindex_pages']} |",
        f"| Missing JSON-LD Article | {summary['missing_jsonld_article']} |",
        f"| Avg response size (bytes) | {summary['avg_response_size_bytes']} |",
    ]
    return "\n".join(lines) + "\n"


def render_markdown(audit: dict[str, Any], issues: list[dict[str, str]]) -> str:
    generated = datetime.fromisoformat(audit["generated_at"].replace("Z", "+00:00"))
    lines = [
        f"# WordPress News Visibility Ops Report",
        f"- Site: `{audit['site']}`",
        f"- Generated (UTC): `{generated.isoformat()}`",
        "",
        "## What's Broken / Missing",
    ]

    if not issues:
        lines.append("- No major issues detected in this run.")
    else:
        for issue in issues:
            lines.append(f"- [{issue['priority']}] {issue['title']} - {issue['evidence']}")

    lines.extend(
        [
            "",
            _findings_table(audit),
            "## Remediation Plan",
            _issue_section(issues, "P0"),
            _issue_section(issues, "P1"),
            _issue_section(issues, "P2"),
            _plugin_fix_matrix(),
            "",
            _theme_snippets(),
            "",
            _submission_checklist(),
            "",
            "## References",
            "- `docs/google_news_wp_checklist.md`",
            "- `docs/bing_news_wp_checklist.md`",
            "- `docs/newsbreak_wp_feed_playbook.md`",
            "- `docs/schema_validation_playbook.md`",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def build_report_payload(audit: dict[str, Any]) -> dict[str, Any]:
    issues = derive_issues(audit)
    priority_counts = {
        "P0": sum(1 for issue in issues if issue["priority"] == "P0"),
        "P1": sum(1 for issue in issues if issue["priority"] == "P1"),
        "P2": sum(1 for issue in issues if issue["priority"] == "P2"),
    }
    return {
        "site": audit["site"],
        "generated_at": audit["generated_at"],
        "priority_counts": priority_counts,
        "issues": issues,
        "audit": audit,
    }
