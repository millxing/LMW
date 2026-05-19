#!/usr/bin/env python3
"""Build the Longwood Mall static site from structured content."""

from __future__ import annotations

import html
import json
import re
from urllib.parse import quote
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
CONFIG_PATH = SRC / "site.json"
STYLE_PATH = ROOT / "style.css"
SCRIPT_PATH = ROOT / "script.js"


SVG_ICONS = {
    "tree": '<svg class="brand-icon" xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 14h.01"/><path d="M7 7H6a2 2 0 0 0-2 2v.5a2 2 0 0 0 2 2h.5"/><path d="M12 2C8 2 6 5 6 7c0 3.6 3.4 5 6 5s6-1.4 6-5c0-2-2-5-6-5Z"/><path d="m12 22 1-7.5"/><path d="M12 22 7 20"/><path d="M12 22l5-2"/></svg>',
    "menu": '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/></svg>',
    "arrow": '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>',
    "instagram": '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="20" height="20" x="2" y="2" rx="5" ry="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37Z"/><line x1="17.5" x2="17.51" y1="6.5" y2="6.5"/></svg>',
}

IMAGE_EXTENSIONS = {".avif", ".jpg", ".jpeg", ".png", ".webp"}


def escape(text: str) -> str:
    return html.escape(text)


def attr_url(url: str) -> str:
    return html.escape(url, quote=True)


def style_url(url: str) -> str:
    return html.escape(f'url("{url}")', quote=True)


def br_join(lines: list[str]) -> str:
    return "<br>".join(escape(line) for line in lines)


def plain_join(lines: list[str]) -> str:
    return escape(" ".join(lines))


def natural_sort_key(value: str) -> list[object]:
    parts = re.split(r"(\d+)", value.lower())
    return [int(part) if part.isdigit() else part for part in parts]


def humanize_segment(value: str) -> str:
    cleaned = value.replace("_", " ").replace("-", " ")
    cleaned = re.sub(r"([A-Za-z])(\d)", r"\1 \2", cleaned)
    cleaned = re.sub(r"(\d)([A-Za-z])", r"\1 \2", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if re.fullmatch(r"[A-Z0-9 ]+", cleaned):
        return cleaned
    return cleaned.title()


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "item"


def inventory_group_label(value: str) -> str:
    match = re.fullmatch(r"2025-10Beech(\d+)", value)
    if match:
        return f"Tree {int(match.group(1)):02d}"
    return value


def resolve_collection_items(collection: dict) -> list[dict]:
    if collection.get("items"):
        return collection["items"]

    folder = collection.get("folder")
    if not folder:
        return []

    folder_root = ROOT / folder.removeprefix("./")
    if not folder_root.exists():
        return []

    image_paths = sorted(
        [path for path in folder_root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS],
        key=lambda path: natural_sort_key(path.relative_to(folder_root).as_posix()),
    )
    if collection.get("reverse_order"):
        image_paths.reverse()

    sources = collection.get("sources", {})
    items = []
    for index, path in enumerate(image_paths, start=1):
        relative_path = path.relative_to(ROOT).as_posix()
        relative_stem = path.relative_to(folder_root).with_suffix("")
        title = humanize_segment(path.stem)
        if collection.get("caption_mode") == "path":
            caption = " / ".join(humanize_segment(part) for part in relative_stem.parts)
        else:
            caption = title
        items.append(
            {
                "src": f"./{relative_path}",
                "alt": f"{collection['eyebrow']}: {title}",
                "caption": caption,
                "title": title,
                "source": sources.get(path.name, {}),
            }
        )
    return items


def render_source_caption(item: dict) -> str:
    source = item.get("source") or {}
    label = source.get("label")
    if not label:
        return ""

    url = source.get("url")
    note = source.get("note")
    if url:
        source_markup = (
            f'          <a href="{attr_url(url)}" target="_blank" rel="noopener">'
            f"{escape(label)}</a>"
        )
    else:
        source_markup = f"          <span>{escape(label)}</span>"
    note_markup = f"\n          <span>{escape(note)}</span>" if note else ""
    return (
        "              <figcaption class=\"slide-source\">\n"
        "                <span class=\"slide-source-label\">Source</span>\n"
        f"{source_markup}{note_markup}\n"
        "              </figcaption>\n"
    )


def resolve_inventory_groups(collection: dict) -> list[dict]:
    folder = collection.get("folder")
    if not folder:
        return []

    folder_root = ROOT / folder.removeprefix("./")
    if not folder_root.exists():
        return []

    groups = []
    for group_dir in sorted([path for path in folder_root.iterdir() if path.is_dir()], key=lambda path: natural_sort_key(path.name)):
        image_paths = sorted(
            [path for path in group_dir.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS],
            key=lambda path: natural_sort_key(path.relative_to(group_dir).as_posix()),
        )
        if not image_paths:
            continue

        display_label = inventory_group_label(group_dir.name)
        items = []
        for path in image_paths:
            relative_path = path.relative_to(ROOT).as_posix()
            items.append(
                {
                    "src": f"./{relative_path}",
                    "alt": f'{collection["eyebrow"]}: {display_label} {path.stem}',
                    "caption": path.stem,
                    "title": path.stem,
                }
            )

        groups.append(
            {
                "id": group_dir.name,
                "label": display_label,
                "slug": f'{collection["id"]}-{slugify(group_dir.name)}.html',
                "image": items[0]["src"],
                "items": items,
                "page_title": f'{display_label} | {collection["page_title"]}',
                "page_description": f'{display_label} inventory photos for Longwood Mall.',
            }
        )
    return groups


def render_paragraphs(items: list[dict | str], class_name: str) -> str:
    blocks = []
    for item in items:
        if isinstance(item, str):
            blocks.append(f'      <p class="{class_name}">{escape(item)}</p>')
            continue
        if "html" in item:
            blocks.append(f'      <p class="{class_name}">{item["html"]}</p>')
        elif "items" in item:
            list_items = "\n".join(
                f'        <li>{entry["html"]}</li>' if isinstance(entry, dict) and "html" in entry else f"        <li>{escape(entry)}</li>"
                for entry in item["items"]
            )
            blocks.append(f'      <ul class="{class_name} support-page-list">\n{list_items}\n      </ul>')
        else:
            blocks.append(f'      <p class="{class_name}">{escape(item["text"])}</p>')
    return "\n".join(blocks)


def render_buttons(buttons: list[dict], class_prefix: str = "btn", include_icon: bool = True) -> str:
    rendered = []
    for button in buttons:
        variant = button.get("variant", "primary")
        classes = f"{class_prefix} {class_prefix}-{variant}"
        rel = ' rel="noopener"' if button.get("external") else ""
        target = ' target="_blank"' if button.get("external") else ""
        label_suffix = f' {SVG_ICONS["arrow"]}' if include_icon else ""
        rendered.append(
            f'        <a href="{attr_url(button["href"])}" class="{classes}"{target}{rel}>'
            f'{escape(button["label"])}{label_suffix}</a>'
        )
    return "\n".join(rendered)


def render_header(site: dict, active_nav: str) -> str:
    links = []
    for item in site["navigation"]:
        class_name = "nav-link active" if item["id"] == active_nav else "nav-link"
        rel = ' rel="noopener"' if item.get("external") else ""
        target = ' target="_blank"' if item.get("external") else ""
        if item.get("icon"):
            class_name = f"{class_name} nav-icon-link"
            icon = SVG_ICONS[item["icon"]]
            links.append(
                f'          <a href="{attr_url(item["href"])}" class="{class_name}" aria-label="{escape(item["label"])}"{target}{rel}>'
                f'{icon}<span class="nav-icon-label">{escape(item["label"])}</span></a>'
            )
        else:
            links.append(
                f'          <a href="{attr_url(item["href"])}" class="{class_name}"{target}{rel}>{escape(item["label"])}</a>'
            )
    rendered_links = "\n".join(links)
    return (
        "<header class=\"site-header\">\n"
        "  <div class=\"container header-inner\">\n"
        "    <button class=\"nav-toggle\" type=\"button\" aria-label=\"Open menu\" aria-expanded=\"false\" data-nav-toggle>\n"
        f"      {SVG_ICONS['menu']}\n"
        "    </button>\n"
        "    <nav class=\"site-nav\" aria-label=\"Main navigation\" data-nav>\n"
        f"      <p class=\"site-nav-mobile-brand\">{escape(site['brand'])}</p>\n"
        f"{rendered_links}\n"
        "    </nav>\n"
        "  </div>\n"
        "</header>"
    )


def render_footer(site: dict) -> str:
    footer = site["footer"]
    nav_links = "\n".join(
        f'          <a href="{attr_url(link["href"])}">{escape(link["label"])}</a>' for link in footer["links"]
    )
    utility_links = []
    for link in footer["utility_links"]:
        rel = ' rel="noopener"' if link.get("external") else ""
        target = ' target="_blank"' if link.get("external") else ""
        if link.get("icon"):
            icon = SVG_ICONS[link["icon"]]
            utility_links.append(
                f'          <a class="footer-icon-link" href="{attr_url(link["href"])}" aria-label="{escape(link["label"])}"{target}{rel}>'
                f'{icon}<span class="visually-hidden">{escape(link["label"])}</span></a>'
            )
        else:
            utility_links.append(
                f'          <a href="{attr_url(link["href"])}"{target}{rel}>{escape(link["label"])}</a>'
            )
    utility_markup = "\n".join(utility_links)
    return (
        "<footer class=\"site-footer\">\n"
        "  <div class=\"container footer-inner\">\n"
        f'    <div class="footer-brand"><span>{escape(site["brand"])}</span></div>\n'
        "    <div class=\"footer-links\">\n"
        f"{nav_links}\n"
        "    </div>\n"
        "    <div class=\"footer-utility-links\">\n"
        f"{utility_markup}\n"
        "    </div>\n"
        "  </div>\n"
        "</footer>"
    )


def render_head(site: dict, title: str, description: str) -> str:
    style_version = int(STYLE_PATH.stat().st_mtime)
    script_version = int(SCRIPT_PATH.stat().st_mtime)
    return f"""<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(title)}</title>
  <meta name="description" content="{escape(description)}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="{attr_url(site["font_href"])}" rel="stylesheet">
  <link rel="stylesheet" href="style.css?v={style_version}">
  <script src="script.js?v={script_version}" defer></script>
</head>"""


def wrap_page(site: dict, active_nav: str, title: str, description: str, body_class: str, main_content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
{render_head(site, title, description)}
<body class="{escape(body_class)}">
  <div class="page-shell">
{render_header(site, active_nav)}
    <main>
{main_content}
    </main>
{render_footer(site)}
  </div>
</body>
</html>
"""


def render_title_band(title_markup: str) -> str:
    return (
        "          <div class=\"page-title-band\">\n"
        f"            <h1>{title_markup}</h1>\n"
        "          </div>\n"
    )


def find_posts(data: dict, ids: list[str]) -> list[dict]:
    posts = {item["id"]: item for item in data["news"]["items"]}
    return [posts[item_id] for item_id in ids if item_id in posts]


def render_stats(stats: list[dict]) -> str:
    parts = []
    for item in stats:
        parts.append(
            "      <div class=\"stat-card\">\n"
            f"        <span class=\"stat-value\">{escape(item['value'])}</span>\n"
            f"        <span class=\"stat-label\">{escape(item['label'])}</span>\n"
            "      </div>"
        )
    return "\n".join(parts)


def render_home_news(preview: dict, posts: list[dict]) -> str:
    primary = posts[:2]
    secondary = posts[2:]
    primary_markup = []
    for post in primary:
        primary_markup.append(
            "        <article class=\"news-card news-card-featured\">\n"
            f"          <p class=\"card-date\">{escape(post['date'])}</p>\n"
            f"          <h3>{escape(post['title'])}</h3>\n"
            f"          <p>{escape(post['summary'])}</p>\n"
            f'          <a href="latest-news.html#{escape(post["id"])}" class="text-link">Read this update {SVG_ICONS["arrow"]}</a>\n'
            "        </article>"
        )
    secondary_markup = []
    for post in secondary:
        secondary_markup.append(
            "          <article class=\"news-list-item\">\n"
            f"            <p class=\"card-date\">{escape(post['date'])}</p>\n"
            f"            <h4>{escape(post['title'])}</h4>\n"
            f"            <p>{escape(post['summary'])}</p>\n"
            f'            <a href="latest-news.html#{escape(post["id"])}" class="text-link">Open update {SVG_ICONS["arrow"]}</a>\n'
            "          </article>"
        )
    return (
        "<section class=\"section section-news\">\n"
        "  <div class=\"container section-heading-block\">\n"
        f'    <p class="section-eyebrow">{escape(preview["eyebrow"])}</p>\n'
        f'    <h2 class="section-title">{br_join(preview["title_lines"])}</h2>\n'
        f'    <p class="section-copy">{escape(preview["description"])}</p>\n'
        "  </div>\n"
        "  <div class=\"container news-preview-grid\">\n"
        "    <div class=\"news-feature-grid\">\n"
        f"{''.join(primary_markup)}\n"
        "    </div>\n"
        "    <div class=\"news-list-panel\">\n"
        "      <p class=\"mini-label\">More updates</p>\n"
        f"{''.join(secondary_markup)}\n"
        f'      <a href="{attr_url(preview["button"]["href"])}" class="btn btn-ghost">{escape(preview["button"]["label"])} {SVG_ICONS["arrow"]}</a>\n'
        "    </div>\n"
        "  </div>\n"
        "</section>"
    )


def render_home_photos(section: dict, collections: list[dict]) -> str:
    cards = []
    for collection in collections:
        items = resolve_collection_items(collection)
        sample_images = "\n".join(
            f'            <img src="{attr_url(item["src"])}" alt="{escape(item["alt"])}" loading="lazy">'
            for item in items[:3]
        )
        cards.append(
            "      <article class=\"collection-card\">\n"
            f'        <img class="collection-hero-image" src="{attr_url(collection["image"])}" alt="{escape(collection["description"])}" loading="lazy">\n'
            "        <div class=\"collection-card-body\">\n"
            f'          <p class="mini-label">{escape(collection["eyebrow"])}</p>\n'
            f"          <h3>{br_join(collection['title_lines'])}</h3>\n"
            f'          <p>{escape(collection["summary"])}</p>\n'
            "          <div class=\"collection-strip\">\n"
            f"{sample_images}\n"
            "          </div>\n"
            f'          <a href="{attr_url(collection["slug"])}" class="btn btn-outline">Open collection {SVG_ICONS["arrow"]}</a>\n'
            "        </div>\n"
            "      </article>"
        )
    return (
        "<section class=\"section section-dark\">\n"
        "  <div class=\"container section-heading-block\">\n"
        f'    <p class="section-eyebrow">{escape(section["eyebrow"])}</p>\n'
        f'    <h2 class="section-title section-title-light">{br_join(section["title_lines"])}</h2>\n'
        f'    <p class="section-copy section-copy-light">{escape(section["description"])}</p>\n'
        "  </div>\n"
        "  <div class=\"container collection-grid\">\n"
        f"{''.join(cards)}\n"
        "  </div>\n"
        "</section>"
    )


def render_home_bld(section: dict, bld: dict) -> str:
    cards = []
    for item in bld["summary_cards"]:
        cards.append(
            "      <article class=\"info-card\">\n"
            f"        <h3>{escape(item['title'])}</h3>\n"
            f"        <p>{escape(item['text'])}</p>\n"
            "      </article>"
        )
    updates = []
    for item in bld["updates"][:2]:
        updates.append(
            "          <article class=\"update-item compact\">\n"
            f"            <p class=\"card-date\">{escape(item['date'])}</p>\n"
            f"            <h4>{escape(item['title'])}</h4>\n"
            f"            <p>{escape(item['text'])}</p>\n"
            f'            <a href="{attr_url(item["href"])}" class="text-link">Open related note {SVG_ICONS["arrow"]}</a>\n'
            "          </article>"
        )
    return (
        "<section class=\"section\">\n"
        "  <div class=\"container bld-overview-grid\">\n"
        "    <div>\n"
        f'      <p class="section-eyebrow">{escape(section["eyebrow"])}</p>\n'
        f'      <h2 class="section-title">{br_join(section["title_lines"])}</h2>\n'
        f'      <p class="section-copy">{escape(section["description"])}</p>\n'
        "      <div class=\"info-card-grid\">\n"
        f"{''.join(cards)}\n"
        "      </div>\n"
        "    </div>\n"
        "    <aside class=\"surface-panel surface-panel-dark\">\n"
        f'      <p class="mini-label mini-label-light">{escape(bld["current_note"]["label"])}</p>\n'
        f'      <h3>{escape(bld["current_note"]["title"])}</h3>\n'
        f'      <p>{escape(bld["current_note"]["body"])}</p>\n'
        "      <div class=\"stack-list\">\n"
        f"{''.join(updates)}\n"
        "      </div>\n"
        f'      <a href="{attr_url(bld["hero"]["buttons"][0]["href"])}" class="btn btn-outline btn-outline-light">Explore BLD updates {SVG_ICONS["arrow"]}</a>\n'
        "    </aside>\n"
        "  </div>\n"
        "</section>"
    )


def render_home_support(section: dict, support: dict) -> str:
    if "actions" not in support:
        buttons = render_buttons(
            [
                {
                    "label": support["donation_label"],
                    "href": support["donation_href"],
                    "variant": "primary",
                    "external": True,
                }
            ]
        )
        preview_items = "\n".join(
            "      <article class=\"support-card\">\n"
            f"        <p>{escape(item)}</p>\n"
            "      </article>"
            for item in support["paragraphs"][:3]
        )
        return (
            "<section class=\"section section-support\">\n"
            "  <div class=\"container support-grid\">\n"
            "    <div>\n"
            f'      <p class="section-eyebrow">{escape(section["eyebrow"])}</p>\n'
            f'      <h2 class="section-title">{br_join(section["title_lines"])}</h2>\n'
            f'      <p class="section-copy">{escape(section["description"])}</p>\n'
            "      <div class=\"support-card-grid\">\n"
            f"{preview_items}\n"
            "      </div>\n"
            "    </div>\n"
            "    <aside class=\"surface-panel\">\n"
            f"      <h3>{escape(support['title'])}</h3>\n"
            f'      <p>{escape(support["donation_text"])} {escape(support["donation_label"])}.</p>\n'
            "      <div class=\"button-row\">\n"
            f"{buttons}\n"
            "      </div>\n"
            "    </aside>\n"
            "  </div>\n"
            "</section>"
        )
    cards = []
    for item in support["actions"][:3]:
        cards.append(
            "      <article class=\"support-card\">\n"
            f"        <h3>{escape(item['title'])}</h3>\n"
            f"        <p>{escape(item['text'])}</p>\n"
            "      </article>"
        )
    buttons = render_buttons(support["hero"]["buttons"])
    return (
        "<section class=\"section section-support\">\n"
        "  <div class=\"container support-grid\">\n"
        "    <div>\n"
        f'      <p class="section-eyebrow">{escape(section["eyebrow"])}</p>\n'
        f'      <h2 class="section-title">{br_join(section["title_lines"])}</h2>\n'
        f'      <p class="section-copy">{escape(section["description"])}</p>\n'
        "      <div class=\"support-card-grid\">\n"
        f"{''.join(cards)}\n"
        "      </div>\n"
        "    </div>\n"
        "    <aside class=\"surface-panel\">\n"
        f'      <p class="mini-label">{escape(support["partner"]["eyebrow"])}</p>\n'
        f'      <h3>{escape(support["partner"]["title"])}</h3>\n'
        f'      <p>{escape(support["partner"]["text"])}</p>\n'
        f'      <img class="partner-image" src="{attr_url(support["partner"]["image"])}" alt="{escape(support["partner"]["title"])}" loading="lazy">\n'
        "      <div class=\"button-row\">\n"
        f"{buttons}\n"
        "      </div>\n"
        "    </aside>\n"
        "  </div>\n"
        "</section>"
    )


def render_home_tree_nav(tree_nav: dict, mobile_intro: str = "") -> str:
    links = []
    mobile_links = []
    for item in tree_nav["items"]:
        class_name = f'tree-link {escape(item["class_name"])}'
        links.append(
            f'          <a href="{attr_url(item["href"])}" class="{class_name}" aria-label="{escape(item["label"])}">'
            f'<img src="{attr_url(item["image"])}" alt="" loading="lazy"></a>'
        )
        mobile_links.append(
            f'        <a href="{attr_url(item["href"])}" class="mobile-branch-link">'
            f'<span>{escape(item["label"])}</span>{SVG_ICONS["arrow"]}</a>'
        )
    links_markup = "\n".join(links)
    mobile_links_markup = "\n".join(mobile_links)
    eyebrow = ""
    if tree_nav.get("eyebrow"):
        eyebrow = f'    <p class="section-eyebrow">{escape(tree_nav["eyebrow"])}</p>\n'
    description = ""
    if tree_nav.get("description"):
        description = f'    <p class="section-copy">{escape(tree_nav["description"])}</p>\n'
    mobile_intro_markup = ""
    if mobile_intro:
        mobile_intro_markup = f'  <p class="container mobile-branch-intro">{escape(mobile_intro)}</p>\n'
    return (
        "<section class=\"section home-tree-nav\" id=\"choose-a-branch\">\n"
        f"{mobile_intro_markup}"
        "  <div class=\"container section-heading-block tree-nav-heading\">\n"
        f"{eyebrow}"
        f'    <h2 class="section-title">{br_join(tree_nav["title_lines"])}</h2>\n'
        f"{description}"
        "  </div>\n"
        "  <nav class=\"container mobile-branch-list\" aria-label=\"Longwood Mall sections\">\n"
        f"{mobile_links_markup}\n"
        "  </nav>\n"
        "  <div class=\"container tree-nav-container\">\n"
        "    <div class=\"tree-nav-stage\">\n"
        f'      <img class="tree-nav-image" src="{attr_url(tree_nav["image"])}" alt="Illustrated Longwood Mall tree with wooden sign links to the main site sections" loading="eager">\n'
        "      <div class=\"tree-nav-links\">\n"
        f"{links_markup}\n"
        "      </div>\n"
        "    </div>\n"
        "  </div>\n"
        "</section>"
    )


def render_home_event(event: dict) -> str:
    pdf_src = f'{event["pdf"]}#toolbar=0&navpanes=0&scrollbar=0&view=Fit&zoom=page-fit'
    return f"""
        <aside class="home-event-callout" aria-label="Longwood Mall event">
          <p class="home-event-title">{escape(event["title"])}</p>
          <p class="home-event-countdown">
            <span>{escape(event["countdown_label"])}</span>
            <strong data-event-countdown data-event-datetime="{attr_url(event["datetime"])}">Calculating...</strong>
          </p>
          <button class="home-event-link" type="button" data-event-info>
            {escape(event["link_label"])}
          </button>
        </aside>
        <div class="event-overlay" role="dialog" aria-modal="true" aria-labelledby="event-overlay-title" hidden data-event-overlay>
          <div class="event-overlay-backdrop" data-event-close></div>
          <div class="event-overlay-panel">
            <div class="event-overlay-header">
              <h2 id="event-overlay-title">2026 Longwood Mall Event</h2>
              <button class="event-overlay-close" type="button" aria-label="Close event flyer" data-event-close>&times;</button>
            </div>
            <iframe class="event-pdf-frame" src="{attr_url(pdf_src)}" title="2026 Longwood Mall Event flyer"></iframe>
          </div>
        </div>
"""


def render_home_classic(data: dict) -> str:
    site = data["site"]
    home = data["home"]
    featured_posts = find_posts(data, home["latest_news"]["featured_ids"] + home["latest_news"]["list_ids"])
    hero_buttons = render_buttons(home["hero"]["buttons"])
    quote = home["quote"]
    cta_buttons = render_buttons(home["cta"]["buttons"])
    hero_eyebrow = ""
    if home["hero"].get("eyebrow"):
        hero_eyebrow = f'\n            <p class="hero-eyebrow">{escape(home["hero"]["eyebrow"])}</p>'
    hero_subtitle = ""
    if home["hero"].get("subtitle"):
        hero_subtitle = f'\n            <p class="hero-copy">{escape(home["hero"]["subtitle"])}</p>'
    hero_button_row = ""
    if hero_buttons:
        hero_button_row = f'\n            <div class="button-row">\n{hero_buttons}\n            </div>'
    content = f"""
      <section class="home-hero" style="--hero-image: {style_url(home["hero"]["background_image"])};">
        <div class="home-hero-overlay"></div>
        <div class="container home-hero-grid home-hero-grid-single">
          <div class="home-hero-copy">
{hero_eyebrow}
            <h1>{br_join(home["hero"]["title_lines"])}</h1>
{hero_subtitle}
{hero_button_row}
          </div>
        </div>
      </section>

      <section class="quote-band">
        <div class="container quote-inner">
          <p class="quote-mark">&ldquo;</p>
          <blockquote>{escape(quote["text"])}</blockquote>
          <p class="quote-author">{escape(quote["author"])}</p>
        </div>
      </section>

{render_home_news(home["latest_news"], featured_posts)}
{render_home_photos(home["photos"], data["photos"]["collections"])}
{render_home_bld(home["bld"], data["bld"])}
{render_home_support(home["support"], data["support"])}

      <section class="cta-band" style="--cta-image: {style_url(home["cta"]["background_image"])};">
        <div class="cta-overlay"></div>
        <div class="container cta-inner">
          <h2>{escape(home["cta"]["title"])}</h2>
          <p>{br_join(home["cta"]["subtitle_lines"])}</p>
          <div class="button-row">
{cta_buttons}
          </div>
        </div>
      </section>
"""
    return wrap_page(site, "home", home["meta_title"], home["meta_description"], "page-home", content)


def render_home(data: dict) -> str:
    site = data["site"]
    home = data["home"]
    hero_buttons = render_buttons(home["hero"]["buttons"])
    hero_eyebrow = ""
    if home["hero"].get("eyebrow"):
        hero_eyebrow = f'\n            <p class="hero-eyebrow">{escape(home["hero"]["eyebrow"])}</p>'
    hero_subtitle = ""
    if home["hero"].get("subtitle"):
        hero_subtitle = f'\n            <p class="hero-copy">{escape(home["hero"]["subtitle"])}</p>'
    hero_scroll_label = escape(home["hero"].get("scroll_label", "Scroll for main menu"))
    hero_button_row = ""
    if hero_buttons:
        hero_button_row = f'\n            <div class="button-row">\n{hero_buttons}\n            </div>'
    content = f"""
      <section class="home-hero" style="--hero-image: {style_url(home["hero"]["background_image"])};">
        <div class="home-hero-overlay"></div>
        <div class="container home-hero-grid home-hero-grid-single">
          <div class="home-hero-copy">
{hero_eyebrow}
            <h1>{br_join(home["hero"]["title_lines"])}</h1>
{hero_subtitle}
{hero_button_row}
            <a href="#choose-a-branch" class="home-scroll-cue">{hero_scroll_label} {SVG_ICONS["arrow"]}</a>
          </div>
        </div>
{render_home_event(home["event"])}
      </section>

{render_home_tree_nav(home["tree_nav"], home["hero"].get("subtitle", ""))}
"""
    return wrap_page(site, "home", home["meta_title"], home["meta_description"], "page-home", content)


def render_page_hero(
    section: dict,
    body_class: str = "",
    include_button_icons: bool = True,
    include_media: bool = True,
    description_after_buttons: bool = False,
) -> str:
    buttons = (
        render_buttons(section.get("buttons", []), include_icon=include_button_icons) if section.get("buttons") else ""
    )
    button_row = ""
    if buttons:
        button_row = f'\n          <div class="button-row">\n{buttons}\n          </div>'
    eyebrow = section.get("hero_eyebrow", section.get("eyebrow", ""))
    eyebrow_markup = f'            <p class="hero-eyebrow">{escape(eyebrow)}</p>\n' if eyebrow else ""
    media_markup = ""
    if include_media:
        media_markup = f"""
          <figure class="page-hero-media">
            <img src="{attr_url(section["image"])}" alt="{escape(section["description"])}" loading="eager">
          </figure>"""
    description = f'            <p class="hero-copy">{escape(section["description"])}</p>'
    hero_content = f"{eyebrow_markup}{description}{button_row}"
    if description_after_buttons:
        hero_content = f"{eyebrow_markup}{button_row}\n{description}"
    return f"""
      <section class="page-hero {body_class}">
{render_title_band(plain_join(section["title_lines"]))}\
        <div class="container page-hero-grid">
          <div class="page-hero-copy">
{hero_content}
          </div>
{media_markup}
        </div>
      </section>
"""


def render_history_page(data: dict) -> str:
    site = data["site"]
    history = data["history"]
    cards = []
    tilts = ["-1.8deg", "1.2deg", "-0.7deg", "1.8deg", "-1.1deg"]
    for index, item in enumerate(history["items"]):
        rel = ' rel="noopener"' if item.get("external") else ""
        target = ' target="_blank"' if item.get("external") else ""
        cards.append(
            f'          <a class="history-paper-card" href="{attr_url(item["href"])}"{target}{rel} style="--paper-tilt: {tilts[index % len(tilts)]};">\n'
            f'            <span>{escape(item["label"])}</span>\n'
            "          </a>"
        )
    cards_markup = "\n".join(cards)
    content = (
        "      <section class=\"history-menu-page\">\n"
        "        <div class=\"container history-menu-shell\">\n"
        f"{render_title_band(escape(history['title']))}"
        "          <nav class=\"history-paper-grid\" aria-label=\"History links\">\n"
        f"{cards_markup}\n"
        "          </nav>\n"
        "        </div>\n"
        "      </section>\n"
    )
    return wrap_page(site, "history", history["meta_title"], history["meta_description"], "page-interior page-history-menu", content)


def render_history_article_page(site: dict, article: dict) -> str:
    images = []
    for index, image_item in enumerate(article["images"], start=1):
        if isinstance(image_item, str):
            image = image_item
            alt = f'{article["title"]} page {index}'
            caption = ""
        else:
            image = image_item["src"]
            alt = image_item.get("alt", f'{article["title"]} page {index}')
            caption = ""
            if image_item.get("caption"):
                caption = f'            <figcaption>{escape(image_item["caption"])}</figcaption>\n'
        images.append(
            "          <figure class=\"history-document-page\">\n"
            f'            <button class="history-document-open" type="button" data-document-open data-document-src="{attr_url(image)}" data-document-alt="{escape(alt)}" aria-label="Open {escape(alt)}">\n'
            f'              <img src="{attr_url(image)}" alt="{escape(alt)}" loading="lazy" decoding="async">\n'
            "            </button>\n"
            f"{caption}"
            "          </figure>"
        )
    images_markup = "\n".join(images)
    document_grid_class = "history-document-grid"
    if len(images) == 1:
        document_grid_class += " history-document-grid-single"
    if article.get("image_size") == "small":
        document_grid_class += " history-document-grid-small"
    image_note = ""
    if article.get("image_note"):
        image_note = f'            <p class="history-document-note">{escape(article["image_note"])}</p>\n'
    documents_markup = (
        f"          <div class=\"{document_grid_class}\">\n"
        f"{images_markup}\n"
        f"{image_note}"
        "          </div>\n"
    )
    image_after_paragraph = article.get("image_after_paragraph")
    if isinstance(image_after_paragraph, int):
        before_images = render_paragraphs(article["paragraphs"][:image_after_paragraph], "history-article-copy")
        after_images = render_paragraphs(article["paragraphs"][image_after_paragraph:], "history-article-copy")
        article_body = f"{before_images}\n{documents_markup}{after_images}"
        trailing_documents = ""
    else:
        paragraphs = render_paragraphs(article["paragraphs"], "history-article-copy")
        article_body = f"{paragraphs}\n"
        trailing_documents = documents_markup
    article_title = br_join(article.get("title_lines", [article["title"]]))
    content = (
        "      <section class=\"history-article-page\">\n"
        "        <div class=\"container history-article-shell\">\n"
        f"{render_title_band(article_title)}"
        "          <article class=\"history-article-body\">\n"
        f"{article_body}\n"
        "          </article>\n"
        f"{trailing_documents}"
        "          <dialog class=\"history-document-overlay\" data-document-overlay aria-label=\"Enlarged document page\">\n"
        "            <button class=\"history-document-close\" type=\"button\" data-document-close aria-label=\"Close document view\">&times;</button>\n"
        "            <img src=\"\" alt=\"\" data-document-overlay-image>\n"
        "          </dialog>\n"
        "        </div>\n"
        "      </section>\n"
    )
    return wrap_page(site, "history", article["meta_title"], article["meta_description"], "page-interior page-history-article", content)


def render_news_page(data: dict) -> str:
    site = data["site"]
    news = data["news"]
    list_markup = []
    for post in news["items"]:
        post_href = f'#{post["id"]}'
        post_title = escape(post["title"])
        post_title_link = (
            f'            <h2><a class="news-page-title-link" href="{attr_url(post_href)}" '
            f'aria-label="Link directly to: {post_title}">'
            '<span class="news-page-anchor-marker" aria-hidden="true">#</span>'
            f"<span>{post_title}</span></a></h2>\n"
        )
        image_blocks = []
        for item in post.get("images", []):
            caption = ""
            if item.get("caption"):
                caption = f'                <figcaption>{escape(item["caption"])}</figcaption>\n'
            figure_class = "news-page-image"
            if item.get("variant"):
                figure_class += f' news-page-image-{slugify(item["variant"])}'
            image_markup = (
                f'                  <img src="{attr_url(item["src"])}" alt="{escape(item["alt"])}" loading="lazy" decoding="async">\n'
            )
            if item.get("href"):
                rel = ' rel="noopener"' if item.get("external") else ""
                target = ' target="_blank"' if item.get("external") else ""
                image_control = (
                    f'                <a class="news-page-image-link" href="{attr_url(item["href"])}"{target}{rel} aria-label="{escape(item.get("link_label", item["alt"]))}">\n'
                    f"{image_markup}"
                    "                </a>\n"
                )
            else:
                image_control = (
                    f'                <button class="history-document-open" type="button" data-document-open data-document-src="{attr_url(item["src"])}" data-document-alt="{escape(item["alt"])}" aria-label="Open {escape(item["alt"])}">\n'
                    f"{image_markup}"
                    "                </button>\n"
                )
            image_blocks.append(
                f"              <figure class=\"{figure_class}\">\n"
                f"{image_control}"
                f"{caption}"
                "              </figure>"
            )
        images = "\n".join(image_blocks)
        images_markup = ""
        if images:
            image_grid_class = "news-page-image-grid"
            if post.get("image_size") == "small":
                image_grid_class += " news-page-image-grid-small"
            images_markup = f"            <div class=\"{image_grid_class}\">\n{images}\n            </div>\n"
        links = ""
        if post.get("links"):
            link_markup = []
            for link in sorted(post["links"], key=lambda item: item.get("index", 0)):
                link_markup.append(
                    f'              <a href="{attr_url(link["href"])}" target="_blank" rel="noopener">{escape(link["label"])} {SVG_ICONS["arrow"]}</a>'
                )
            links = f"            <div class=\"bld-page-link-list news-page-link-list\">\n{chr(10).join(link_markup)}\n            </div>"
        iframe = ""
        if post.get("iframe"):
            frame = post["iframe"]
            iframe = (
                "\n            <div class=\"bld-page-article-frame news-page-article-frame\">\n"
                f'              <iframe src="{attr_url(frame["src"])}" title="{escape(frame["title"])}" loading="lazy"></iframe>\n'
                "            </div>"
            )
        before_paragraphs = "" if post.get("image_position") == "after_paragraphs" else images_markup
        after_paragraphs = images_markup if post.get("image_position") == "after_paragraphs" else ""
        anchor_aliases = "\n".join(
            f'          <span class="news-page-anchor-alias" id="{attr_url(alias)}" aria-hidden="true"></span>'
            for alias in post.get("anchor_aliases", [])
        )
        if anchor_aliases:
            anchor_aliases += "\n"
        list_markup.append(
            f"{anchor_aliases}"
            "          <article class=\"news-page-entry\""
            f' id="{escape(post["id"])}">\n'
            f"          <p class=\"card-date\">{escape(post['date'])}</p>\n"
            f"{post_title_link}"
            f"{before_paragraphs}"
            f"{render_paragraphs(post['paragraphs'], 'support-page-copy')}\n"
            f"{after_paragraphs}"
            f"{links}\n"
            f"{iframe}\n"
            "          </article>"
        )
    content = (
        "      <section class=\"support-page news-page\">\n"
        "        <div class=\"container support-page-shell news-page-shell\">\n"
        f"{render_title_band(escape(news['title']))}"
        f"{render_mobile_jump_links(news['items'], limit=8)}"
        f"{chr(10).join(list_markup)}\n"
        "          <dialog class=\"history-document-overlay\" data-document-overlay aria-label=\"Enlarged news image\">\n"
        "            <button class=\"history-document-close\" type=\"button\" data-document-close aria-label=\"Close image view\">&times;</button>\n"
        "            <img src=\"\" alt=\"\" data-document-overlay-image>\n"
        "          </dialog>\n"
        "        </div>\n"
        "      </section>\n"
    )
    return wrap_page(site, "news", news["meta_title"], news["meta_description"], "page-interior", content)


def render_photos_overview(data: dict) -> str:
    site = data["site"]
    photos = data["photos"]
    cards = []
    for collection in photos["collections"]:
        cards.append(
            f'          <a href="{attr_url(collection["slug"])}" class="photo-portal" style="--photo-card-image: {style_url(collection["image"])};">\n'
            "            <div class=\"photo-portal-body\">\n"
            f"              <h2>{escape(collection['eyebrow'])}</h2>\n"
            "            </div>\n"
            "          </a>"
        )
    content = (
        "      <section class=\"photos-hub\">\n"
        "        <div class=\"container photos-hub-shell\">\n"
        "          <div class=\"photos-hub-intro\">\n"
        f"{render_title_band(br_join(photos['hero']['title_lines']))}"
        "          </div>\n"
        "          <div class=\"photos-hub-grid\">\n"
        f"{''.join(cards)}\n"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
    )
    return wrap_page(
        site,
        "photos",
        photos["meta_title"],
        photos["meta_description"],
        "page-interior page-photos-overview",
        content,
    )


def render_scroll_gallery(items: list[dict]) -> str:
    slides = []
    for index, item in enumerate(items):
        title = item.get("title") or item.get("caption") or f"Image {index + 1}"
        loading = "eager" if index < 2 else "lazy"
        source_caption = render_source_caption(item)
        slides.append(
            "            <figure class=\"slide\""
            f' data-gallery-slide data-title="{escape(title)}">\n'
            f'              <img src="{attr_url(item["src"])}" alt="{escape(item["alt"])}" loading="{loading}" decoding="async">\n'
            f"{source_caption}"
            "            </figure>"
        )
    return (
        "      <section class=\"gallery-shell\" id=\"gallery-start\" data-gallery-shell>\n"
        "        <div class=\"sticky-wrap\">\n"
        "          <div class=\"stage\" data-gallery-stage>\n"
        f"{''.join(slides)}\n"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
        "      <div class=\"gallery-status\" data-gallery-status hidden>\n"
        "        <span class=\"dot\" aria-hidden=\"true\"></span>\n"
        "        <span data-gallery-status-text>00 / 00</span>\n"
        "      </div>\n"
    )


def render_inventory_index(site: dict, collection: dict, groups: list[dict]) -> str:
    cards = []
    for group in groups:
        cards.append(
            "        <a class=\"inventory-group-card\""
            f' href="{attr_url(group["slug"])}">\n'
            f'          <img src="{attr_url(group["image"])}" alt="{escape(group["label"])}" loading="lazy">\n'
            "          <div class=\"inventory-group-card-body\">\n"
            f'            <h2>{escape(group["label"])}</h2>\n'
            "          </div>\n"
            "        </a>"
        )
    hero = {**collection, "hero_eyebrow": ""}
    content = (
        f"{render_page_hero(hero, include_button_icons=False, include_media=False, description_after_buttons=True)}\n"
        "      <section class=\"section inventory-index-section\">\n"
        "        <div class=\"container inventory-group-grid\">\n"
        f"{''.join(cards)}\n"
        "        </div>\n"
        "      </section>\n"
    )
    return wrap_page(site, "photos", collection["page_title"], collection["page_description"], "page-interior page-inventory-index", content)


def render_gallery_page_header(section: dict) -> str:
    buttons = render_buttons(section.get("buttons", []), include_icon=False) if section.get("buttons") else ""
    button_row = f'\n          <div class="button-row">\n{buttons}\n          </div>' if buttons else ""
    return (
        "      <section class=\"gallery-page-header\">\n"
        f"{render_title_band(plain_join(section['title_lines']))}"
        "        <div class=\"container gallery-page-header-inner\">\n"
        "          <div class=\"gallery-page-copy\">\n"
        f"{button_row}\n"
        f'            <p class="hero-copy">{escape(section["description"])}</p>\n'
        "            <a class=\"gallery-scroll-cue\" href=\"#gallery-start\" aria-label=\"Scroll down to view more photos\">\n"
        "              <span>Scroll for more photos</span>\n"
        f"              {SVG_ICONS['arrow']}\n"
        "            </a>\n"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
    )


def render_mobile_jump_links(items: list[dict], label_key: str = "title", limit: int | None = None) -> str:
    visible_items = items[:limit] if limit else items
    links = []
    for item in visible_items:
        if not item.get("id"):
            continue
        label = item.get(label_key, "")
        if not label:
            continue
        links.append(
            f'            <a href="#{attr_url(item["id"])}">{escape(label)}</a>'
        )
    if not links:
        return ""
    return (
        "          <nav class=\"mobile-page-jump-list\" aria-label=\"Page sections\">\n"
        f"{chr(10).join(links)}\n"
        "          </nav>\n"
    )


def render_gallery_page(site: dict, collection: dict, items: list[dict] | None = None, page_title: str | None = None, page_description: str | None = None, title_lines: list[str] | None = None, buttons: list[dict] | None = None) -> str:
    gallery_items = items if items is not None else resolve_collection_items(collection)
    section = dict(collection)
    if title_lines is not None:
        section["title_lines"] = title_lines
    if page_title is not None:
        section["page_title"] = page_title
    if page_description is not None:
        section["page_description"] = page_description
    if buttons is not None:
        section["buttons"] = buttons
    content = f"{render_gallery_page_header(section)}\n{render_scroll_gallery(gallery_items)}"
    active_nav = "history" if collection.get("id") == "historical" else "photos"
    return wrap_page(site, active_nav, section["page_title"], section["page_description"], "page-interior page-photo-gallery", content)


def render_bld_page(data: dict) -> str:
    site = data["site"]
    bld = data["bld"]
    sections = []
    for section in bld["page_sections"]:
        paragraphs = render_paragraphs(section.get("paragraphs", []), "support-page-copy")
        images = "\n".join(
            f'              <figure class="bld-page-image {escape(image.get("class_name", ""))}">\n'
            f'                <img src="{attr_url(image["src"])}" alt="{escape(image["alt"])}" loading="lazy" decoding="async">\n'
            "              </figure>"
            for image in section.get("images", [])
        )
        images_markup = f"\n            <div class=\"bld-page-image-grid\">\n{images}\n            </div>" if images else ""
        youtube = ""
        if section.get("youtube"):
            video = section["youtube"]
            youtube = (
                "\n            <div class=\"bld-page-video\">\n"
                f'              <iframe src="https://www.youtube-nocookie.com/embed/{attr_url(video["id"])}" title="{escape(video["title"])}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>\n'
                "            </div>"
            )
        iframe = ""
        if section.get("iframe"):
            frame = section["iframe"]
            iframe = (
                "\n            <div class=\"bld-page-article-frame\">\n"
                f'              <iframe src="{attr_url(frame["src"])}" title="{escape(frame["title"])}" loading="lazy"></iframe>\n'
                "            </div>"
            )
        links = []
        for item in sorted(section.get("links", []), key=lambda link: link.get("index", 0)):
            rel = ' rel="noopener"' if item.get("external") else ""
            target = ' target="_blank"' if item.get("external") else ""
            links.append(
                f'              <a href="{attr_url(item["href"])}"{target}{rel}>{escape(item["label"])} {SVG_ICONS["arrow"]}</a>'
            )
        links_markup = f"\n            <div class=\"bld-page-link-list\">\n{chr(10).join(links)}\n            </div>" if links else ""
        sections.append(
            f'          <section class="bld-page-section" id="{attr_url(section["id"])}">\n'
            f"            <h2>{escape(section['title'])}</h2>\n"
            f"{paragraphs}{images_markup}{youtube}{iframe}{links_markup}\n"
            "          </section>"
        )
    content = (
        "      <section class=\"support-page bld-page\">\n"
        "        <div class=\"container support-page-shell bld-page-shell\">\n"
        f"{render_title_band(escape(bld['title']))}"
        f"{render_mobile_jump_links(bld['page_sections'])}"
        f"{chr(10).join(sections)}\n"
        "        </div>\n"
        "      </section>\n"
    )
    return wrap_page(site, "bld", bld["meta_title"], bld["meta_description"], "page-interior", content)


def render_support_page(data: dict) -> str:
    site = data["site"]
    support = data["support"]
    paragraphs = "\n".join(
        f'            <p class="support-page-copy">{escape(item)}</p>' for item in support["paragraphs"]
    )
    images = "\n".join(
        "            <figure class=\"support-sign-image\">\n"
        f'              <button class="history-document-open" type="button" data-document-open data-document-src="{attr_url(item["src"])}" data-document-alt="{escape(item["alt"])}" aria-label="Open {escape(item["alt"])}">\n'
        f'                <img src="{attr_url(item["src"])}" alt="{escape(item["alt"])}" loading="lazy" decoding="async">\n'
        "              </button>\n"
        "            </figure>"
        for item in support.get("images", [])
    )
    images_markup = ""
    if images:
        images_markup = f'          <div class="support-sign-grid">\n{images}\n          </div>\n'
    fields = []
    for field in support["form_fields"]:
        if field == "Write a message":
            fields.append(
                f'              <label><span>{escape(field)}</span><textarea name="message" rows="5"></textarea></label>'
            )
        else:
            fields.append(
                f'              <label><span>{escape(field)}</span><input name="{slugify(field)}" type="text"></label>'
            )
    fields_markup = "\n".join(fields)
    contact_action = f'mailto:{support["contact_email"]}?subject={quote(support["contact_subject"])}'
    content = (
        "      <section class=\"support-page\">\n"
        "        <div class=\"container support-page-shell\">\n"
        f"{render_title_band(escape(support['title']))}"
        "          <div class=\"support-page-body\">\n"
        f'            <p class="support-page-copy">{escape(support["donation_text"])} <a href="{attr_url(support["donation_href"])}" target="_blank" rel="noopener">{escape(support["donation_label"])}</a>.</p>\n'
        f"{paragraphs}\n"
        "          </div>\n"
        f"{images_markup}"
        "          <section class=\"support-contact-block\">\n"
        f"            <h2>{escape(support['contact_title'])}</h2>\n"
        f"            <form class=\"support-contact-form\" action=\"{attr_url(contact_action)}\" method=\"post\" enctype=\"text/plain\">\n"
        f"{fields_markup}\n"
        f'              <button class="btn btn-primary" type="submit">{escape(support["submit_label"])}</button>\n'
        "            </form>\n"
        f'            <p class="support-thanks">{escape(support["thanks_text"])}</p>\n'
        "          </section>\n"
        "          <dialog class=\"history-document-overlay\" data-document-overlay aria-label=\"Enlarged support image\">\n"
        "            <button class=\"history-document-close\" type=\"button\" data-document-close aria-label=\"Close image view\">&times;</button>\n"
        "            <img src=\"\" alt=\"\" data-document-overlay-image>\n"
        "          </dialog>\n"
        "        </div>\n"
        "      </section>\n"
    )
    return wrap_page(site, "support", support["meta_title"], support["meta_description"], "page-interior", content)


def render_donations_page(data: dict) -> str:
    site = data["site"]
    donations = data["donations"]
    paragraphs = "\n".join(
        f'            <p class="support-page-copy">{escape(item)}</p>' for item in donations["paragraphs"]
    )
    address = "\n".join(f"              <span>{escape(item)}</span>" for item in donations["mail_to"])
    contact_action = f'mailto:{donations["contact_email"]}?subject={quote(donations["contact_subject"])}'
    email_link = f'<a href="{attr_url(contact_action)}">'
    closing_paragraph = escape(donations["closing_paragraph"])
    closing_paragraph = closing_paragraph.replace("please email me", f"{email_link}please email me</a>")
    closing_paragraph = closing_paragraph.replace("contact me", f"{email_link}contact me</a>")
    content = (
        "      <section class=\"support-page donations-page\">\n"
        "        <div class=\"container support-page-shell\">\n"
        f"{render_title_band(escape(donations['title']))}"
        "          <div class=\"support-page-body\">\n"
        f"{paragraphs}\n"
        f'            <p class="support-page-callout">{escape(donations["check_payable"])}</p>\n'
        f'            <p class="support-page-copy">{escape(donations["mail_intro"])}</p>\n'
        f"            <address class=\"support-mail-address\">\n{address}\n            </address>\n"
        f'            <p class="support-page-copy">{closing_paragraph}</p>\n'
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
    )
    return wrap_page(site, "support", donations["meta_title"], donations["meta_description"], "page-interior", content)


def build() -> None:
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    site = data["site"]

    outputs = {
        "index.html": render_home(data),
        "index-classic.html": render_home_classic(data),
        "history.html": render_history_page(data),
        "latest-news.html": render_news_page(data),
        "photos.html": render_photos_overview(data),
        "beech-leaf-disease.html": render_bld_page(data),
        "support.html": render_support_page(data),
        "donations.html": render_donations_page(data),
    }

    for article in data.get("history_articles", {}).values():
        outputs[article["slug"]] = render_history_article_page(site, article)

    for collection in data["photos"]["collections"]:
        if collection.get("id") == "inventory":
            groups = resolve_inventory_groups(collection)
            outputs[collection["slug"]] = render_inventory_index(site, collection, groups)
            for group in groups:
                buttons = [
                    {
                        "label": "Back to Inventory Menu",
                        "href": collection["slug"],
                        "variant": "outline",
                    },
                    collection["buttons"][1],
                ]
                outputs[group["slug"]] = render_gallery_page(
                    site,
                    collection,
                    items=group["items"],
                    page_title=group["page_title"],
                    page_description=group["page_description"],
                    title_lines=[group["label"]],
                    buttons=buttons,
                )
            continue
        outputs[collection["slug"]] = render_gallery_page(site, collection)

    for filename, html_output in outputs.items():
        (ROOT / filename).write_text(html_output, encoding="utf-8")


if __name__ == "__main__":
    build()
