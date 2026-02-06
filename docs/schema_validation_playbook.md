# Schema Validation Playbook (WordPress)

## What to Validate

On article URLs, validate JSON-LD includes:

1. `@type` = `Article` or `NewsArticle`
2. `headline`
3. `datePublished`
4. `dateModified`
5. `author.name`
6. `publisher.name`
7. `image`

## Validation Workflow

1. Open article source and locate `application/ld+json` scripts.
2. Use a schema validator (Rich Results Test and Schema Markup Validator).
3. Confirm values match visible on-page content and canonical URL.
4. Verify date formats are ISO-8601.
5. Ensure author/publisher names are not blank placeholders.

## Common WP Fixes

1. SEO plugin schema settings:
   - Set post default schema to `Article` or `NewsArticle`.
   - Enable organization/person publisher data.
2. Theme template:
   - Ensure article title/date/author render in HTML.
   - Ensure featured image is present.
3. Plugin conflicts:
   - Disable duplicate schema emitters if multiple plugins output JSON-LD.
   - Keep one authoritative SEO/schema source.

## Regression Guardrails

1. Re-run `python -m wp_news_ops audit --site https://msnewsgroup.com/` after updates.
2. Re-run `python -m wp_news_ops report --site https://msnewsgroup.com/` before major releases.
3. Keep schema checks in release checklist for theme/plugin updates.
