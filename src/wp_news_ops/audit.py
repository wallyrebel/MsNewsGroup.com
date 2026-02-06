from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

DEFAULT_TIMEOUT = 20
USER_AGENT = "wp-news-ops/0.1 (+https://github.com/)"
SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/wp-sitemap.xml",
    "/news-sitemap.xml",
]


class AuditError(Exception):
    """Raised when the audit cannot continue."""


def normalize_site(site: str) -> str:
    site = site.strip()
    if not site:
        raise AuditError("Site URL cannot be empty.")
    if not site.startswith(("http://", "https://")):
        site = "https://" + site
    parsed = urlparse(site)
    if not parsed.netloc:
        raise AuditError(f"Invalid site URL: {site}")
    base = f"{parsed.scheme}://{parsed.netloc}"
    return base + "/"


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def _safe_request(
    session: requests.Session,
    method: str,
    url: str,
    **kwargs: Any,
) -> tuple[requests.Response | None, str | None]:
    try:
        resp = session.request(method, url, timeout=DEFAULT_TIMEOUT, allow_redirects=True, **kwargs)
        return resp, None
    except requests.RequestException as exc:
        return None, str(exc)


def _parse_robots(text: str) -> dict[str, Any]:
    disallow_rules: list[str] = []
    sitemap_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "disallow":
            disallow_rules.append(value)
        elif key == "sitemap":
            sitemap_lines.append(value)

    blocking_hints: list[str] = []
    important_prefixes = ["/feed", "/sitemap", "/wp-sitemap", "/news-sitemap", "/sitemaps"]
    for rule in disallow_rules:
        clean = rule.strip()
        if not clean:
            continue
        if clean == "/":
            blocking_hints.append(clean)
            continue
        if clean.startswith("/?"):
            if any(token in clean for token in ["/?feed", "/?sitemap"]):
                blocking_hints.append(clean)
            continue
        for prefix in important_prefixes:
            if clean == prefix or clean.startswith(prefix + "/"):
                blocking_hints.append(clean)
                break

    return {
        "disallow_rules": disallow_rules,
        "sitemap_lines": sitemap_lines,
        "potentially_blocking_rules": sorted(set(blocking_hints)),
    }


def _extract_lastmods(xml_text: str, limit: int = 3) -> list[str]:
    values = re.findall(r"<lastmod>([^<]+)</lastmod>", xml_text, flags=re.IGNORECASE)
    return values[:limit]


def _audit_discovery(session: requests.Session, site: str) -> dict[str, Any]:
    robots_url = urljoin(site, "robots.txt")
    robots_resp, robots_err = _safe_request(session, "GET", robots_url)

    robots_data: dict[str, Any] = {
        "url": robots_url,
        "status": robots_resp.status_code if robots_resp else None,
        "error": robots_err,
        "disallow_rules": [],
        "sitemap_lines": [],
        "potentially_blocking_rules": [],
    }

    if robots_resp is not None and robots_resp.ok:
        robots_data.update(_parse_robots(robots_resp.text))

    sitemaps: list[dict[str, Any]] = []
    for path in SITEMAP_PATHS:
        url = urljoin(site, path.lstrip("/"))
        resp, err = _safe_request(session, "GET", url)
        entry: dict[str, Any] = {
            "path": path,
            "url": url,
            "status": resp.status_code if resp is not None else None,
            "error": err,
            "exists": bool(resp is not None and resp.status_code < 400),
            "content_type": resp.headers.get("Content-Type") if resp is not None else None,
            "lastmod_hints": _extract_lastmods(resp.text) if resp is not None and resp.ok else [],
        }
        sitemaps.append(entry)

    return {
        "robots": robots_data,
        "sitemaps": sitemaps,
    }


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1].lower()
    if ":" in tag:
        return tag.split(":", 1)[1].lower()
    return tag.lower()


def _first_child_text_by_name(parent: ET.Element, names: set[str]) -> str:
    for child in list(parent):
        if _local_name(child.tag) in names and child.text:
            return child.text.strip()
    return ""


def _extract_entry_link(entry: ET.Element) -> str:
    for child in list(entry):
        name = _local_name(child.tag)
        if name != "link":
            continue
        href = (child.attrib.get("href") or "").strip()
        if href:
            return href
        if child.text and child.text.strip():
            return child.text.strip()
    return ""


def _content_stats(html: str) -> tuple[int, bool, bool]:
    if not html:
        return 0, False, False
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)
    has_image = bool(soup.find("img"))
    lowered = text.lower()
    excerpt_patterns = ["continue reading", "read more", "[...]", "…"]
    looks_excerpt = any(token in lowered for token in excerpt_patterns)
    return len(text), has_image, looks_excerpt


def _looks_like_image_url(value: str) -> bool:
    lowered = value.lower()
    return lowered.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"))


def _parse_feed_xml(feed_text: str) -> tuple[list[dict[str, Any]], str | None]:
    try:
        root = ET.fromstring(feed_text)
    except ET.ParseError as exc:
        return [], str(exc)

    root_name = _local_name(root.tag)
    items: list[dict[str, Any]] = []

    if root_name == "rss":
        channel = next((node for node in list(root) if _local_name(node.tag) == "channel"), None)
        if channel is None:
            return [], "RSS channel element is missing"
        nodes = [node for node in list(channel) if _local_name(node.tag) == "item"]
    elif root_name == "feed":
        nodes = [node for node in list(root) if _local_name(node.tag) == "entry"]
    else:
        return [], f"Unsupported feed root element: {root_name}"

    for node in nodes:
        title = _first_child_text_by_name(node, {"title"})
        link = _extract_entry_link(node)
        pub_date = _first_child_text_by_name(node, {"pubdate", "date", "published", "updated"})

        content_html = ""
        has_image = False
        for child in list(node):
            lname = _local_name(child.tag)
            if lname in {"encoded", "content", "summary", "description"}:
                content_html = (child.text or "").strip()
                if child.text and "<" in child.text:
                    content_html = child.text
            if lname in {"enclosure", "content", "thumbnail"}:
                media_type = (child.attrib.get("type") or "").lower()
                media_url = (child.attrib.get("url") or child.attrib.get("href") or "").strip()
                if media_type.startswith("image/") or _looks_like_image_url(media_url):
                    has_image = True

        content_len, content_has_image, looks_excerpt = _content_stats(content_html)
        has_image = has_image or content_has_image

        items.append(
            {
                "title": title,
                "link": link,
                "pub_date": pub_date,
                "has_image": has_image,
                "content_length": content_len,
                "looks_excerpt": looks_excerpt,
            }
        )

    return items, None


def _discover_feed_urls(session: requests.Session, site: str) -> tuple[list[str], str | None, str | None]:
    candidates = {urljoin(site, "feed/")}

    homepage_resp, homepage_err = _safe_request(session, "GET", site)
    homepage_html = homepage_resp.text if homepage_resp is not None and homepage_resp.ok else None

    if homepage_html:
        soup = BeautifulSoup(homepage_html, "lxml")
        for link in soup.find_all("link"):
            rel = " ".join(link.get("rel", [])).lower()
            mime = (link.get("type") or "").lower()
            href = (link.get("href") or "").strip()
            if not href:
                continue
            if "alternate" in rel and ("rss+xml" in mime or "atom+xml" in mime):
                candidates.add(urljoin(site, href))

    return sorted(candidates), homepage_html, homepage_err


def _audit_feed(session: requests.Session, site: str) -> dict[str, Any]:
    discovered_feeds, homepage_html, homepage_error = _discover_feed_urls(session, site)

    best_feed: dict[str, Any] | None = None
    feed_checks: list[dict[str, Any]] = []

    for feed_url in discovered_feeds:
        resp, err = _safe_request(session, "GET", feed_url)
        entry: dict[str, Any] = {
            "url": feed_url,
            "status": resp.status_code if resp else None,
            "error": err,
            "items": [],
            "parse_error": None,
        }
        if resp is not None and resp.ok:
            items, parse_error = _parse_feed_xml(resp.text)
            entry["items"] = items
            entry["parse_error"] = parse_error
            if parse_error is None and items and best_feed is None:
                best_feed = {
                    "url": feed_url,
                    "status": resp.status_code,
                    "items": items,
                }
        feed_checks.append(entry)

    selected_items = best_feed["items"] if best_feed else []
    item_count = len(selected_items)
    items_with_title = sum(1 for item in selected_items if item["title"])
    items_with_link = sum(1 for item in selected_items if item["link"])
    items_with_date = sum(1 for item in selected_items if item["pub_date"])
    items_with_image = sum(1 for item in selected_items if item["has_image"])
    excerpt_like = sum(1 for item in selected_items if item["looks_excerpt"])
    avg_content_length = (
        sum(item["content_length"] for item in selected_items) / item_count if item_count else 0
    )

    newsbreak_risk = False
    risk_reasons: list[str] = []
    if item_count:
        image_ratio = items_with_image / item_count
        excerpt_ratio = excerpt_like / item_count
        if image_ratio < 0.7:
            newsbreak_risk = True
            risk_reasons.append("Feed items often do not include images.")
        if excerpt_ratio > 0.5 or avg_content_length < 500:
            newsbreak_risk = True
            risk_reasons.append("Feed content appears excerpt-only.")
    else:
        newsbreak_risk = True
        risk_reasons.append("No valid feed items were found.")

    return {
        "discovered_feed_urls": discovered_feeds,
        "homepage_discovery_error": homepage_error,
        "checked_feeds": feed_checks,
        "selected_feed_url": best_feed["url"] if best_feed else None,
        "selected_feed_status": best_feed["status"] if best_feed else None,
        "item_count": item_count,
        "items_with_title": items_with_title,
        "items_with_link": items_with_link,
        "items_with_date": items_with_date,
        "items_with_image": items_with_image,
        "excerpt_like_items": excerpt_like,
        "avg_content_length": round(avg_content_length, 1),
        "newsbreak_risk": newsbreak_risk,
        "newsbreak_risk_reasons": risk_reasons,
        "items": selected_items,
        "homepage_html": homepage_html,
    }


def _same_domain(url: str, site: str) -> bool:
    host = urlparse(site).netloc.lower()
    target = urlparse(url).netloc.lower()
    return target == host or target.endswith("." + host)


def _normalize_url_for_compare(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    return host, path


def _urls_equivalent(url_a: str, url_b: str) -> bool:
    host_a, path_a = _normalize_url_for_compare(url_a)
    host_b, path_b = _normalize_url_for_compare(url_b)
    if host_a and host_b and host_a != host_b:
        return False
    return path_a == path_b


def _extract_jsonld_entities(soup: BeautifulSoup) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []

    def collect(node: Any) -> None:
        if isinstance(node, dict):
            entities.append(node)
            if "@graph" in node and isinstance(node["@graph"], list):
                for child in node["@graph"]:
                    collect(child)
        elif isinstance(node, list):
            for child in node:
                collect(child)

    for script in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        collect(parsed)

    return entities


def _as_type_list(raw_type: Any) -> list[str]:
    if isinstance(raw_type, str):
        return [raw_type.lower()]
    if isinstance(raw_type, list):
        return [str(item).lower() for item in raw_type]
    return []


def _extract_article_urls(feed_data: dict[str, Any], site: str, sample_size: int) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    for item in feed_data.get("items", []):
        link = (item.get("link") or "").strip()
        if not link:
            continue
        abs_url = urljoin(site, link)
        if not _same_domain(abs_url, site):
            continue
        if abs_url in seen:
            continue
        seen.add(abs_url)
        urls.append(abs_url)
        if len(urls) >= sample_size:
            return urls

    homepage_html = feed_data.get("homepage_html")
    if homepage_html:
        soup = BeautifulSoup(homepage_html, "lxml")
        for anchor in soup.find_all("a"):
            href = (anchor.get("href") or "").strip()
            if not href:
                continue
            abs_url = urljoin(site, href)
            if not _same_domain(abs_url, site):
                continue
            parsed = urlparse(abs_url)
            path = parsed.path.lower()
            if not path or path == "/":
                continue
            if any(token in path for token in ["/tag/", "/category/", "/author/", "/wp-"]):
                continue
            if abs_url in seen:
                continue
            seen.add(abs_url)
            urls.append(abs_url)
            if len(urls) >= sample_size:
                return urls

    return urls


def _parse_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _article_publication_date_visible(soup: BeautifulSoup) -> bool:
    if soup.find("time", attrs={"datetime": True}):
        return True
    body_text = soup.get_text(" ", strip=True)
    snippet = body_text[:10000]
    patterns = [
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},\s+\d{4}\b",
    ]
    for pattern in patterns:
        if re.search(pattern, snippet, flags=re.IGNORECASE):
            return True
    return False


def _audit_article(session: requests.Session, url: str) -> dict[str, Any]:
    resp, err = _safe_request(session, "GET", url)
    if resp is None:
        return {
            "url": url,
            "status": None,
            "error": err,
        }

    soup = BeautifulSoup(resp.text, "lxml")

    def _has_canonical_rel(value: Any) -> bool:
        if not value:
            return False
        if isinstance(value, str):
            rels = [value.lower()]
        else:
            rels = [str(item).lower() for item in value]
        return "canonical" in rels

    canonical_node = soup.find("link", rel=_has_canonical_rel)
    canonical_raw = (canonical_node.get("href") if canonical_node else "") or ""
    canonical_url = urljoin(url, canonical_raw.strip()) if canonical_raw else ""
    canonical_exists = bool(canonical_url)
    canonical_consistent = _urls_equivalent(canonical_url, url) if canonical_url else False

    robots_meta = soup.find("meta", attrs={"name": re.compile("robots", re.I)})
    robots_content = (robots_meta.get("content") if robots_meta else "") or ""
    noindex = "noindex" in robots_content.lower()

    og_fields = {
        "og:title": "",
        "og:type": "",
        "og:url": "",
        "og:image": "",
        "og:image:width": "",
        "og:image:height": "",
    }
    for tag in soup.find_all("meta"):
        prop = (tag.get("property") or "").strip().lower()
        if prop in og_fields:
            og_fields[prop] = (tag.get("content") or "").strip()

    publication_date_visible = _article_publication_date_visible(soup)

    entities = _extract_jsonld_entities(soup)
    article_entities = []
    for entity in entities:
        types = _as_type_list(entity.get("@type"))
        if any(t in {"article", "newsarticle", "blogposting"} for t in types):
            article_entities.append(entity)

    required_fields = ["headline", "datePublished", "dateModified", "author", "publisher", "image"]
    missing_fields: list[str] = []
    if article_entities:
        for field in required_fields:
            if field in {"author", "publisher"}:
                has_value = False
                for entity in article_entities:
                    value = entity.get(field)
                    if isinstance(value, dict) and value.get("name"):
                        has_value = True
                        break
                    if isinstance(value, list) and any(
                        isinstance(item, dict) and item.get("name") for item in value
                    ):
                        has_value = True
                        break
                if not has_value:
                    missing_fields.append(f"{field}.name")
            else:
                if not any(entity.get(field) for entity in article_entities):
                    missing_fields.append(field)

    head = soup.head or soup
    render_blocking_scripts = 0
    huge_inline_scripts = 0
    for script in head.find_all("script"):
        script_type = (script.get("type") or "").lower()
        if "ld+json" in script_type:
            continue
        if script.has_attr("async") or script.has_attr("defer") or script_type == "module":
            continue
        render_blocking_scripts += 1
        inline_len = len((script.string or script.get_text() or "").strip())
        if inline_len > 50000:
            huge_inline_scripts += 1

    return {
        "url": url,
        "status": resp.status_code,
        "error": None,
        "response_size_bytes": len(resp.content),
        "canonical": {
            "exists": canonical_exists,
            "url": canonical_url,
            "consistent_with_url": canonical_consistent,
        },
        "meta_robots": {
            "content": robots_content,
            "noindex": noindex,
        },
        "open_graph": {
            "og:title": bool(og_fields["og:title"]),
            "og:type": bool(og_fields["og:type"]),
            "og:url": bool(og_fields["og:url"]),
            "og:image": bool(og_fields["og:image"]),
            "og:image:width": _parse_int(og_fields["og:image:width"]),
            "og:image:height": _parse_int(og_fields["og:image:height"]),
            "og:image_value": og_fields["og:image"],
        },
        "publication_date_visible_html": publication_date_visible,
        "jsonld": {
            "entity_count": len(entities),
            "article_entity_count": len(article_entities),
            "missing_fields": sorted(set(missing_fields)),
        },
        "performance": {
            "render_blocking_scripts": render_blocking_scripts,
            "huge_inline_scripts": huge_inline_scripts,
        },
    }


def _summarize_articles(pages: list[dict[str, Any]]) -> dict[str, Any]:
    fetched = [page for page in pages if page.get("status")]
    total = len(fetched)
    if total == 0:
        return {
            "sampled": len(pages),
            "fetched": 0,
            "missing_canonical": 0,
            "canonical_mismatch": 0,
            "noindex_pages": 0,
            "missing_og_fields": {
                "og:title": 0,
                "og:type": 0,
                "og:url": 0,
                "og:image": 0,
            },
            "missing_publication_date_html": 0,
            "missing_jsonld_article": 0,
            "jsonld_missing_field_counts": {
                "headline": 0,
                "datePublished": 0,
                "dateModified": 0,
                "author.name": 0,
                "publisher.name": 0,
                "image": 0,
            },
            "avg_response_size_bytes": 0,
            "high_blocking_script_pages": 0,
            "huge_inline_script_pages": 0,
            "missing_og_image_dimensions": 0,
        }

    missing_og_fields = {"og:title": 0, "og:type": 0, "og:url": 0, "og:image": 0}
    jsonld_missing_fields = {
        "headline": 0,
        "datePublished": 0,
        "dateModified": 0,
        "author.name": 0,
        "publisher.name": 0,
        "image": 0,
    }

    for page in fetched:
        og = page.get("open_graph", {})
        for field in missing_og_fields:
            if not og.get(field):
                missing_og_fields[field] += 1

        for field in page.get("jsonld", {}).get("missing_fields", []):
            if field in jsonld_missing_fields:
                jsonld_missing_fields[field] += 1

    return {
        "sampled": len(pages),
        "fetched": total,
        "missing_canonical": sum(1 for page in fetched if not page["canonical"]["exists"]),
        "canonical_mismatch": sum(
            1
            for page in fetched
            if page["canonical"]["exists"] and not page["canonical"]["consistent_with_url"]
        ),
        "noindex_pages": sum(1 for page in fetched if page["meta_robots"]["noindex"]),
        "missing_og_fields": missing_og_fields,
        "missing_publication_date_html": sum(
            1 for page in fetched if not page["publication_date_visible_html"]
        ),
        "missing_jsonld_article": sum(
            1 for page in fetched if page["jsonld"].get("article_entity_count", 0) == 0
        ),
        "jsonld_missing_field_counts": jsonld_missing_fields,
        "avg_response_size_bytes": int(sum(page["response_size_bytes"] for page in fetched) / total),
        "high_blocking_script_pages": sum(
            1 for page in fetched if page["performance"]["render_blocking_scripts"] >= 8
        ),
        "huge_inline_script_pages": sum(
            1 for page in fetched if page["performance"]["huge_inline_scripts"] > 0
        ),
        "missing_og_image_dimensions": sum(
            1
            for page in fetched
            if not page["open_graph"].get("og:image:width")
            or not page["open_graph"].get("og:image:height")
        ),
    }


def _audit_articles(
    session: requests.Session,
    site: str,
    feed_data: dict[str, Any],
    sample_size: int,
) -> dict[str, Any]:
    article_urls = _extract_article_urls(feed_data, site, sample_size)
    pages = [_audit_article(session, url) for url in article_urls]
    return {
        "sample_urls": article_urls,
        "pages": pages,
        "summary": _summarize_articles(pages),
    }


def audit_site(site: str, sample_size: int = 10) -> dict[str, Any]:
    normalized_site = normalize_site(site)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    discovery = _audit_discovery(session, normalized_site)
    feed = _audit_feed(session, normalized_site)
    articles = _audit_articles(session, normalized_site, feed, sample_size=sample_size)

    # Keep homepage HTML out of final payload.
    feed.pop("homepage_html", None)

    return {
        "site": normalized_site,
        "generated_at": _now_iso(),
        "discovery": discovery,
        "feed": feed,
        "articles": articles,
    }


def summarize_for_terminal(audit: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"Site: {audit['site']}")
    lines.append(f"Generated: {audit['generated_at']}")

    robots = audit["discovery"]["robots"]
    lines.append("")
    lines.append("[Discovery]")
    lines.append(f"robots.txt status: {robots['status']}" if robots["status"] else "robots.txt status: ERROR")
    lines.append(f"robots.txt potential blockers: {len(robots['potentially_blocking_rules'])}")
    lines.append(
        "sitemap endpoints found: "
        + str(sum(1 for s in audit["discovery"]["sitemaps"] if s.get("exists")))
        + "/"
        + str(len(audit["discovery"]["sitemaps"]))
    )

    feed = audit["feed"]
    lines.append("")
    lines.append("[Feed]")
    lines.append(f"selected feed: {feed.get('selected_feed_url') or 'none'}")
    lines.append(f"items: {feed['item_count']}")
    lines.append(
        "fields coverage (title/link/date/image): "
        + f"{feed['items_with_title']}/{feed['items_with_link']}/{feed['items_with_date']}/{feed['items_with_image']}"
    )
    lines.append(f"avg content length: {feed['avg_content_length']}")
    lines.append(f"NewsBreak risk: {'YES' if feed['newsbreak_risk'] else 'NO'}")

    summary = audit["articles"]["summary"]
    lines.append("")
    lines.append("[Articles]")
    lines.append(f"sampled/fetched: {summary['sampled']}/{summary['fetched']}")
    lines.append(
        f"missing canonical: {summary['missing_canonical']} | canonical mismatch: {summary['canonical_mismatch']}"
    )
    lines.append(f"noindex pages: {summary['noindex_pages']}")
    lines.append(
        "missing OG fields (title/type/url/image): "
        + f"{summary['missing_og_fields']['og:title']}/"
        + f"{summary['missing_og_fields']['og:type']}/"
        + f"{summary['missing_og_fields']['og:url']}/"
        + f"{summary['missing_og_fields']['og:image']}"
    )
    lines.append(f"missing HTML date: {summary['missing_publication_date_html']}")
    lines.append(f"missing JSON-LD Article: {summary['missing_jsonld_article']}")

    lines.append("")
    lines.append("[Performance]")
    lines.append(f"avg response size bytes: {summary['avg_response_size_bytes']}")
    lines.append(f"high render-blocking script pages: {summary['high_blocking_script_pages']}")
    lines.append(f"huge inline script pages: {summary['huge_inline_script_pages']}")

    return "\n".join(lines)
