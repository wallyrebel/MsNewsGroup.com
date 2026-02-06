# WordPress News Visibility Ops

Toolkit for auditing and improving `https://msnewsgroup.com/` visibility in Google News surfaces, Bing News, and NewsBreak using only native WordPress infrastructure (no external feed hosting).

## What It Does

- Audits discovery and crawl readiness (`robots.txt`, sitemap endpoints).
- Audits RSS/feed readiness for news ingestion quality.
- Audits article template signals on up to 10 recent articles.
- Runs lightweight performance checks relevant to indexing speed.
- Generates a WordPress-specific remediation report with P0/P1/P2 priorities.

## Install

```bash
python -m pip install -e .
```

## CLI Usage

Run audit only:

```bash
python -m wp_news_ops audit --site https://msnewsgroup.com/
```

Run report and write outputs:

```bash
python -m wp_news_ops report --site https://msnewsgroup.com/ \
  --markdown-out reports/latest.md \
  --json-out reports/latest.json
```

## Outputs

- `reports/latest.md` - human-readable remediation plan.
- `reports/latest.json` - structured audit + issue summary.

## Repo Layout

- `src/wp_news_ops/` - Python package.
- `docs/` - operational playbooks/checklists.
- `.github/workflows/audit.yml` - daily scheduled audit run.
- `reports/` - latest generated artifacts.

## GitHub Action

The workflow runs daily and on manual dispatch, generates both report files, and uploads them as artifacts.

Manual run in GitHub:

1. Open `Actions` tab in `wallyrebel/MsNewsGroup.com`.
2. Select workflow `WP News Visibility Audit`.
3. Click `Run workflow`.
4. Optionally override `site` (default `https://msnewsgroup.com/`) and `sample_size` (default `10`).
5. Open the run and download artifact `wp-news-visibility-report-<run_number>`.

Artifact contents:

- `reports/latest.md`
- `reports/latest.json`
