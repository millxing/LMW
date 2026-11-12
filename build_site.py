#!/usr/bin/env python3
"""Build the Longwood Mall static site from structured content in src/site.json."""

from __future__ import annotations

import html
import json
import math
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
CONFIG_PATH = SRC / "site.json"
STYLE_PATH = ROOT / "style.css"
SCRIPT_PATH = ROOT / "script.js"

IMAGE_EXTENSIONS = {".avif", ".jpg", ".jpeg", ".png", ".webp"}
THUMB_DIR = ROOT / "assets" / "thumbs"

try:
    from PIL import Image, ImageOps
except ImportError:  # thumbnails and dimensions are optional niceties
    Image = None


def _svg(body: str, size: int = 20, cls: str = "icon") -> str:
    return (
        f'<svg class="{cls}" xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true" focusable="false">{body}</svg>'
    )


ICONS = {
    "arrow": _svg('<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>', 18),
    "external": _svg('<path d="M7 17 17 7"/><path d="M8 7h9v9"/>', 14, "icon icon-ext"),
    "menu": _svg('<path d="M4 7h16"/><path d="M4 12h16"/><path d="M4 17h16"/>', 22),
    "close": _svg('<path d="M6 6l12 12"/><path d="M18 6 6 18"/>', 22),
    "prev": _svg('<path d="m15 6-6 6 6 6"/>', 26),
    "next": _svg('<path d="m9 6 6 6-6 6"/>', 26),
    "pin": _svg('<path d="M12 21s7-5.6 7-11a7 7 0 1 0-14 0c0 5.4 7 11 7 11Z"/><circle cx="12" cy="10" r="2.5"/>'),
    "clock": _svg('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'),
    "mail": _svg('<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>'),
    "copy": _svg('<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>', 16),
    "instagram": _svg('<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><path d="M17.5 6.5h.01"/>'),
    "expand": _svg('<path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="M21 3l-7 7"/><path d="M3 21l7-7"/>', 16),
    "up": _svg('<path d="M12 19V5"/><path d="m6 11 6-6 6 6"/>', 18),
    "doc": _svg('<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z"/><path d="M14 3v6h6"/>'),
    "train": _svg('<rect x="5" y="3" width="14" height="13" rx="3"/><path d="M5 10h14"/><path d="M9 20l-2 2M15 20l2 2"/><circle cx="9" cy="13" r=".6"/><circle cx="15" cy="13" r=".6"/><path d="M8 16l-1 4h10l-1-4"/>'),
    "play": _svg('<circle cx="12" cy="12" r="9"/><path d="m10 8 6 4-6 4Z"/>'),
}

NEW_TAB_TEXT = '<span class="visually-hidden"> (opens in a new tab)</span>'


# --------------------------------------------------------------------------- helpers


def escape(text: str) -> str:
    return html.escape(str(text))


def attr_url(url: str) -> str:
    return html.escape(url, quote=True)


SCIENTIFIC_NAMES = ("Litylenchus crenatae mccannii", "Fagus sylvatica")


def rich(text: str) -> str:
    """Escape plain text and italicise scientific names."""
    out = escape(text)
    for name in SCIENTIFIC_NAMES:
        out = out.replace(name, f"<em>{name}</em>")
    return out


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


def is_external(href: str) -> bool:
    return href.startswith("http://") or href.startswith("https://")


def link(href: str, label_html: str, cls: str = "", external: bool | None = None, extra: str = "") -> str:
    """Render an anchor; external links open in a new tab and say so."""
    ext = is_external(href) if external is None else external
    class_attr = f' class="{cls}"' if cls else ""
    if ext:
        return (
            f'<a href="{attr_url(href)}"{class_attr} target="_blank" rel="noopener"{extra}>'
            f'{label_html}{ICONS["external"]}{NEW_TAB_TEXT}</a>'
        )
    return f'<a href="{attr_url(href)}"{class_attr}{extra}>{label_html}</a>'


def button(item: dict) -> str:
    variant = item.get("variant", "primary")
    href = item["href"]
    ext = item.get("external", is_external(href))
    icon = "" if ext or href.startswith("mailto:") else ICONS["arrow"]
    return link(href, f'<span>{escape(item["label"])}</span>{icon}', f"btn btn-{variant}", ext)


def buttons_row(items: list[dict], cls: str = "button-row") -> str:
    if not items:
        return ""
    return f'<div class="{cls}">' + "".join(button(item) for item in items) + "</div>"


def label_external_links(markup: str) -> str:
    """Make sure every target=_blank text link in hand-written HTML announces the new tab."""

    def fix(match: re.Match) -> str:
        whole = match.group(0)
        inner = match.group(2)
        if "visually-hidden" in inner or "<img" in inner or "aria-label=" in match.group(1):
            return whole
        return f"{match.group(1)}{inner}{ICONS['external']}{NEW_TAB_TEXT}</a>"

    return re.sub(r'(<a\b[^>]*target="_blank"[^>]*>)(.*?)</a>', fix, markup, flags=re.S)


def year_of(date: str) -> str:
    match = re.search(r"(\d{4})", date)
    return match.group(1) if match else "Earlier"


# --------------------------------------------------------------------------- images


def local_path(src: str) -> Path | None:
    if is_external(src) or src.startswith("data:"):
        return None
    path = ROOT / src.removeprefix("./").split("#")[0]
    return path if path.is_file() else None


@lru_cache(maxsize=None)
def image_size(src: str) -> tuple[int, int] | None:
    path = local_path(src)
    if not path:
        return None
    if Image is not None:
        try:
            with Image.open(path) as im:
                w, h = im.size
                if im.getexif().get(0x0112) in (5, 6, 7, 8):
                    w, h = h, w
                return w, h
        except Exception:
            pass
    if sys.platform == "darwin":
        try:
            out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)], capture_output=True, text=True, check=True).stdout
            w = int(re.search(r"pixelWidth: (\d+)", out).group(1))
            h = int(re.search(r"pixelHeight: (\d+)", out).group(1))
            return w, h
        except Exception:
            return None
    return None


def resized(src: str, width: int) -> str:
    """Return a cached, EXIF-corrected JPEG no wider than `width`, or the original when it is already small."""
    path = local_path(src)
    size = image_size(src)
    if Image is None or not path or not size or path.suffix.lower() not in {".jpg", ".jpeg", ".png"} or size[0] <= width * 1.25:
        return src
    rel = path.relative_to(ROOT / "assets").with_suffix("").as_posix()
    out = THUMB_DIR / f"{slugify(rel)}-{width}.webp"
    if not out.exists() or out.stat().st_mtime < path.stat().st_mtime:
        out.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((width, width * 4))
            im.save(out, "WEBP", quality=70, method=5)
    return f"./{out.relative_to(ROOT).as_posix()}"


def dims(src: str) -> str:
    size = image_size(src)
    return f' width="{size[0]}" height="{size[1]}"' if size else ""


def img_tag(src: str, alt: str, width: int | None = None, loading: str = "lazy", cls: str = "", extra: str = "") -> str:
    shown = resized(src, width) if width else src
    class_attr = f' class="{cls}"' if cls else ""
    return f'<img src="{attr_url(shown)}" alt="{escape(alt)}"{dims(shown)} loading="{loading}" decoding="async"{class_attr}{extra}>'


# --------------------------------------------------------------------------- data


def inventory_group_label(value: str) -> str:
    match = re.fullmatch(r"2025-10Beech(\d+)", value)
    if match:
        return f"Tree {int(match.group(1)):02d}"
    return value


ALT_PREFIX = {
    "contemporary": "Longwood Mall today",
    "aerial": "Aerial view of Longwood Mall and the surrounding neighborhood",
    "historical": "Historical image of Longwood Mall",
}


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
        [p for p in folder_root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS],
        key=lambda p: natural_sort_key(p.relative_to(folder_root).as_posix()),
    )
    if collection.get("reverse_order"):
        image_paths.reverse()
    sources = collection.get("sources", {})
    alts = collection.get("alts", [])
    items = []
    for index, path in enumerate(image_paths, start=1):
        source = sources.get(path.name, {})
        note = source.get("note", "")
        items.append(
            {
                "src": f"./{path.relative_to(ROOT).as_posix()}",
                "alt": note or (alts[index - 1] if index - 1 < len(alts) else f'{ALT_PREFIX.get(collection["id"], "Longwood Mall")}, photo {index} of {len(image_paths)}'),
                "caption": note,
                "source": source,
            }
        )
    return items


def resolve_inventory_groups(collection: dict) -> list[dict]:
    folder = collection.get("folder")
    if not folder:
        return []
    folder_root = ROOT / folder.removeprefix("./")
    if not folder_root.exists():
        return []
    groups = []
    for group_dir in sorted([p for p in folder_root.iterdir() if p.is_dir()], key=lambda p: natural_sort_key(p.name)):
        image_paths = sorted(
            [p for p in group_dir.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS],
            key=lambda p: natural_sort_key(p.relative_to(group_dir).as_posix()),
        )
        if not image_paths:
            continue
        label = inventory_group_label(group_dir.name)
        items = [
            {
                "src": f"./{p.relative_to(ROOT).as_posix()}",
                "alt": f"{label}, inventory photo {i} of {len(image_paths)}",
                "caption": "",
                "source": {},
            }
            for i, p in enumerate(image_paths, start=1)
        ]
        groups.append(
            {
                "id": group_dir.name,
                "label": label,
                "slug": f'{collection["id"]}-{slugify(group_dir.name)}.html',
                "image": items[0]["src"],
                "items": items,
                "page_title": f'{label} | Tree inventory | Longwood Mall',
                "page_description": f"{label}: inventory photos of an individual beech tree at Longwood Mall.",
            }
        )
    return groups


# --------------------------------------------------------------------------- shared chrome


def render_head(site: dict, title: str, description: str) -> str:
    style_version = int(STYLE_PATH.stat().st_mtime)
    script_version = int(SCRIPT_PATH.stat().st_mtime)
    return f"""<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(title)}</title>
  <meta name="description" content="{escape(description)}">
  <meta name="theme-color" content="#1f3a2b">
  <meta property="og:title" content="{escape(title)}">
  <meta property="og:description" content="{escape(description)}">
  <meta property="og:image" content="./assets/hero-home-small.jpg">
  <link rel="icon" href="./assets/logo.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="{attr_url(site["font_href"])}" rel="stylesheet">
  <link rel="stylesheet" href="style.css?v={style_version}">
  <script>document.documentElement.classList.add("js")</script>
  <script src="script.js?v={script_version}" defer></script>
</head>"""


def render_header(site: dict, active_nav: str) -> str:
    items = []
    for item in site["navigation"]:
        current = ' aria-current="page"' if item["id"] == active_nav else ""
        classes = ["nav-link"]
        if item.get("cta"):
            classes = ["btn", "btn-primary", "nav-cta"]
        li_class = ' class="nav-mobile-only"' if item.get("mobile_only") else ""
        items.append(
            f'<li{li_class}><a href="{attr_url(item["href"])}" class="{" ".join(classes)}"{current}>{escape(item["label"])}</a></li>'
        )
    return f"""<a class="skip-link" href="#main">Skip to main content</a>
<header class="site-header" data-header>
  <div class="container header-inner">
    <a class="brand" href="index.html">
      <img class="brand-mark" src="./assets/logo.png" alt="" width="44" height="44">
      <span class="brand-text">
        <span class="brand-name">{escape(site["brand"])}</span>
        <span class="brand-sub">{tagline_markup(site["tagline"])}</span>
      </span>
    </a>
    <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav" data-nav-toggle>
      <span class="nav-toggle-open">{ICONS["menu"]}</span><span class="nav-toggle-close">{ICONS["close"]}</span>
      <span class="nav-toggle-label">Menu</span>
    </button>
    <div class="nav-scrim" data-nav-scrim hidden></div>
    <nav class="site-nav" id="site-nav" aria-label="Main" data-nav>
      <ul class="nav-list">
        {"".join(items)}
      </ul>
    </nav>
  </div>
</header>"""


def tagline_markup(tagline: str) -> str:
    if " · " in tagline:
        head, tail = tagline.split(" · ", 1)
        return f'<span class="brand-sub-long">{escape(head)} · </span>{escape(tail)}'
    return escape(tagline)


def render_footer(site: dict) -> str:
    footer = site["footer"]
    links = "".join(f'<li><a href="{attr_url(l["href"])}">{escape(l["label"])}</a></li>' for l in footer["links"])
    email = site["contact_email"]
    return f"""<footer class="site-footer">
  <div class="container footer-grid">
    <div class="footer-about">
      <a class="brand brand-footer" href="index.html">
        <img class="brand-mark" src="./assets/logo.png" alt="" width="44" height="44">
        <span class="brand-text"><span class="brand-name">{escape(site["brand"])}</span><span class="brand-sub">{escape(site["tagline"])}</span></span>
      </a>
      <p>{escape(footer["about"])}</p>
    </div>
    <nav class="footer-col" aria-label="Footer">
      <h2 class="footer-heading">Explore</h2>
      <ul class="footer-list">{links}</ul>
    </nav>
    <div class="footer-col">
      <h2 class="footer-heading">Visit</h2>
      <ul class="footer-list footer-list-plain">
        <li>{ICONS["pin"]}<span>{escape(site["visit_address"])}</span></li>
        <li>{ICONS["clock"]}<span>Open daily, dawn to dusk</span></li>
        <li>{link(site["directions_href"], "Get directions", "footer-action")}</li>
      </ul>
    </div>
    <div class="footer-col">
      <h2 class="footer-heading">Contact</h2>
      <ul class="footer-list">
        <li><a class="footer-action" href="support.html#contact">{ICONS["mail"]}<span>Contact the Friends</span></a></li>
        <li>{link(site["instagram"], ICONS["instagram"] + "<span>Instagram</span>", "footer-action")}</li>
      </ul>
    </div>
  </div>
  <div class="container footer-bottom">
    <p>&copy; 2026 {escape(footer["credit"])}. Longwood Mall is a public park of the Town of Brookline.</p>
    <a class="footer-top" href="#top">{ICONS["up"]}<span>Back to top</span></a>
  </div>
</footer>"""


LIGHTBOX = f"""<dialog class="lightbox" data-lightbox aria-label="Photo viewer">
  <div class="lightbox-inner">
    <div class="lightbox-bar">
      <p class="lightbox-count" data-lightbox-count aria-live="polite"></p>
      <button class="lightbox-btn lightbox-close" type="button" data-lightbox-close aria-label="Close photo viewer">{ICONS["close"]}</button>
    </div>
    <figure class="lightbox-figure">
      <img alt="" data-lightbox-img>
      <figcaption class="lightbox-caption" data-lightbox-caption></figcaption>
    </figure>
    <button class="lightbox-btn lightbox-prev" type="button" data-lightbox-prev aria-label="Previous photo">{ICONS["prev"]}</button>
    <button class="lightbox-btn lightbox-next" type="button" data-lightbox-next aria-label="Next photo">{ICONS["next"]}</button>
  </div>
</dialog>"""


def wrap_page(site: dict, active_nav: str, title: str, description: str, body_class: str, main_content: str, lightbox: bool = False) -> str:
    main_content = label_external_links(main_content)
    main_content = re.sub(
        r'href="latest-news\.html#([a-z0-9-]+)"',
        lambda m: f'href="{NEWS_LINKS[m.group(1)]}"' if m.group(1) in NEWS_LINKS else m.group(0),
        main_content,
    )
    return f"""<!DOCTYPE html>
<html lang="en" id="top">
{render_head(site, title, description)}
<body class="{escape(body_class)}">
{render_header(site, active_nav)}
<main id="main" tabindex="-1">
{main_content}
</main>
{render_footer(site)}
{LIGHTBOX if lightbox else ""}
</body>
</html>
"""


def render_breadcrumb(trail: list[tuple[str, str | None]]) -> str:
    parts = ['<li><a href="index.html">Home</a></li>']
    for label, href in trail:
        if href:
            parts.append(f'<li><a href="{attr_url(href)}">{escape(label)}</a></li>')
        else:
            parts.append(f'<li><span aria-current="page">{escape(label)}</span></li>')
    return f'<nav class="breadcrumb" aria-label="Breadcrumb"><ol>{"".join(parts)}</ol></nav>'


def render_page_header(title: str, description: str = "", trail: list | None = None, eyebrow: str = "", actions: str = "", meta: str = "", wide: bool = False) -> str:
    crumb = render_breadcrumb(trail) if trail is not None else ""
    eyebrow_markup = f'<p class="eyebrow">{escape(eyebrow)}</p>' if eyebrow else ""
    desc = f'<p class="page-lede">{escape(description)}</p>' if description else ""
    meta_markup = f'<p class="page-meta">{meta}</p>' if meta else ""
    return f"""<header class="page-header{' page-header-wide' if wide else ''}">
  <div class="container">
    {crumb}
    {eyebrow_markup}
    <h1 class="page-title">{title}</h1>
    {desc}
    {meta_markup}
    {actions}
  </div>
</header>"""


def render_paragraphs(items: list, class_name: str = "") -> str:
    cls = f' class="{class_name}"' if class_name else ""
    blocks = []
    for item in items:
        if isinstance(item, str):
            blocks.append(f"<p{cls}>{escape(item)}</p>")
        elif "html" in item:
            content = item["html"]
            if re.fullmatch(r"\s*<strong>[^<]+</strong>\s*", content):
                blocks.append(f'<h3 class="prose-subhead">{re.sub(r"</?strong>", "", content).strip()}</h3>')
            else:
                blocks.append(f"<p{cls}>{content}</p>")
        elif "items" in item:
            lis = "".join(
                f'<li>{e["html"]}</li>' if isinstance(e, dict) and "html" in e else f"<li>{escape(e)}</li>" for e in item["items"]
            )
            blocks.append(f"<ul>{lis}</ul>")
        else:
            blocks.append(f"<p{cls}>{escape(item.get('text', ''))}</p>")
    return "\n".join(blocks)


def zoomable_figure(src: str, alt: str, caption: str = "", cls: str = "", group: str = "page") -> str:
    cap = f"<figcaption>{escape(caption)}</figcaption>" if caption else ""
    return (
        f'<figure class="zoom-figure {cls}">'
        f'<button class="zoom-trigger" type="button" data-lightbox-item data-group="{group}" data-src="{attr_url(src)}" '
        f'data-alt="{escape(alt)}" data-caption="{escape(caption)}">'
        f'{img_tag(src, alt, 640)}'
        f'<span class="zoom-hint">{ICONS["expand"]}<span class="visually-hidden"> (enlarge)</span></span>'
        f"</button>{cap}</figure>"
    )


def link_card(title: str, href: str, source: str, text: str = "", icon: str = "doc", cta: str = "Read the article") -> str:
    body = f"<p>{escape(text)}</p>" if text else ""
    return (
        f'<div class="link-card"><span class="link-card-icon">{ICONS[icon]}</span>'
        f'<div><p class="link-card-source">{escape(source)}</p><p class="link-card-title">{escape(title)}</p>{body}'
        f'{link(href, escape(cta), "text-link")}</div></div>'
    )


def embed_block(frame: dict) -> str:
    src = frame["src"]
    if is_external(src):
        host = re.sub(r"^https?://(www\.)?", "", src).split("/")[0]
        return link_card(frame["title"], src, host, cta=f"Read on {host}")
    pdf = src.split("#")[0]
    return (
        f'<div class="pdf-embed">{link_card(frame["title"], pdf, "PDF report", cta="Open the full report (PDF)")}'
        f'<iframe class="pdf-frame" src="{attr_url(src)}" title="{escape(frame["title"])}" loading="lazy"></iframe></div>'
    )


def youtube_embed(video: dict) -> str:
    vid, title = video["id"], video["title"]
    return (
        f'<figure class="video"><div class="video-embed" data-youtube="{attr_url(vid)}" data-title="{escape(title)}">'
        f'<button class="video-facade" type="button" aria-label="Play video: {escape(title)}">'
        f'<img src="https://i.ytimg.com/vi/{attr_url(vid)}/hqdefault.jpg" alt="" width="480" height="360" loading="lazy" decoding="async">'
        f'<span class="video-play" aria-hidden="true">{ICONS["play"]}</span></button></div>'
        f'<figcaption class="video-caption"><span>{escape(title)}</span>'
        f'{link("https://www.youtube.com/watch?v=" + vid, "Watch on YouTube", "text-link", True)}</figcaption></figure>'
    )


# --------------------------------------------------------------------------- home


def news_card(post: dict, featured: bool = False) -> str:
    image = ""
    if post.get("images"):
        img = post["images"][0]
        image = f'<div class="news-card-media">{img_tag(img["src"], "", 640)}</div>'
    return (
        f'<article class="news-card{" news-card-featured" if featured else ""}">{image}'
        f'<div class="news-card-body"><p class="card-date">{escape(post["date"])}</p>'
        f'<h3 class="news-card-title"><a class="stretched-link" href="{attr_url(news_href(post["id"]))}">{escape(post["title"])}</a></h3>'
        f'<p>{rich(post["summary"])}</p><span class="text-link" aria-hidden="true">Read update {ICONS["arrow"]}</span></div></article>'
    )


LEAF_SVG = (
    '<svg viewBox="0 0 24 36" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">'
    '<path d="M12 1C5 8 3 16 4.5 23 6 29 9.5 33 12 35c2.5-2 6-6 7.5-12C21 16 19 8 12 1Z" fill="currentColor"/>'
    '<path d="M12 4v30M12 12l-4-3M12 12l4-3M12 18l-5-3.5M12 18l5-3.5M12 24l-5-3M12 24l5-3" '
    'stroke="rgba(25,45,15,.35)" stroke-width=".8" fill="none"/></svg>'
)

# x position, size, fall duration, start offset, sideways drift (vw), spin (deg), colour (greens sampled from the hero canopy)
LEAVES = [
    (8, 0.9, 19, -2, 6, 260, "#7d9a3c"), (22, 0.7, 23, -11, -4, -220, "#5f7f2f"),
    (37, 1.1, 21, -6, 8, 300, "#9bb552"), (55, 0.8, 26, -16, -6, -280, "#4f6e2a"),
    (68, 1.0, 20, -9, 5, 240, "#7d9a3c"), (81, 0.75, 24, -3, -7, -300, "#87a447"),
    (93, 0.9, 22, -13, 4, 200, "#a9c25e"),
]


def hero_leaves() -> str:
    leaves = "".join(
        f'<span class="leaf" style="--x: {x}%; --s: {sz}; --d: {d}s; --delay: {dl}s; --drift: {dr}; --spin: {sp}; --leaf: {c}">{LEAF_SVG}</span>'
        for x, sz, d, dl, dr, sp, c in LEAVES
    )
    return f'<div class="hero-leaves" aria-hidden="true">{leaves}</div>'


def fact_value(value: str) -> str:
    match = re.match(r"^(\d+(?:\.\d+)?)(.*)$", value)
    if not match:
        return f'<span class="fact-value">{escape(value)}</span>'
    number, suffix = match.groups()
    return f'<span class="fact-value" data-count="{number}" data-suffix="{escape(suffix)}">{escape(value)}</span>'


def tree_plate(tree: dict) -> str:
    """Engraved beech with a margin label and a leader line for each section of the site.

    All coordinates in `tree_nav` are in `view_box` units. The labels repeat the explore list next to
    the plate, so they are hidden from assistive technology and from the tab order.
    """
    view_w, view_h = tree["view_box"]
    img_x, img_y, img_size = tree["image_box"]
    line_height = 21
    callouts = []
    for item in tree["items"]:
        lines, (x, y) = item["lines"], item["label_at"]
        x1, y1, x2, y2 = item["leader"]
        hit_w = max(len(line) for line in lines) * 9.5 + 16
        hit_x = x - hit_w + 8 if item["anchor"] == "end" else x - 8
        text = escape(lines[0]) + "".join(f'<tspan x="{x}" dy="{line_height}">{escape(line)}</tspan>' for line in lines[1:])
        callouts.append(
            f'<a class="tree-link tree-link-{escape(item["id"])}" href="{attr_url(item["href"])}" tabindex="-1">'
            f'<rect class="tree-link-hit" x="{hit_x:g}" y="{y - 20}" width="{hit_w:g}" height="{line_height * len(lines) + 10}"/>'
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"/><circle cx="{x2}" cy="{y2}" r="4"/>'
            f'<text x="{x}" y="{y}" text-anchor="{escape(item["anchor"])}">{text}</text></a>'
        )
    caption, mid, base = tree["caption"], img_x + img_size / 2, img_y + img_size
    place = f' style="left:{img_x / view_w:.4%};top:{img_y / view_h:.4%};width:{img_size / view_w:.4%}"'
    image = img_tag(tree["image"], tree["image_alt"], cls="tree-image", extra=place)
    return (
        f'<div class="tree-stage" style="aspect-ratio:{view_w} / {view_h}">'
        f'{image}'
        f'<svg class="tree-plate" viewBox="0 0 {view_w} {view_h}" aria-hidden="true" focusable="false">'
        f'{"".join(callouts)}'
        f'<line class="tree-plate-rule" x1="{mid - 30:g}" y1="{base + 12}" x2="{mid + 30:g}" y2="{base + 12}"/>'
        f'<text class="tree-plate-name" x="{mid:g}" y="{base + 32}" text-anchor="middle">{escape(caption["name"])}</text>'
        f'<text class="tree-plate-common" x="{mid:g}" y="{base + 49}" text-anchor="middle">{escape(caption["common"])}</text>'
        f'</svg></div>'
    )


def photo_panel(tree: dict) -> str:
    """Square photo panel. Hovering or focusing an explore row (see script.js) swaps the photo."""
    shots = "".join(
        f'<figure class="shot{" is-active" if n == 0 else ""}" data-shot="{escape(i["id"])}">'
        f'{img_tag(i["image"], i["alt"], 900, loading="eager" if n == 0 else "lazy")}'
        f'<figcaption><span class="shot-label">{escape(i["label"])}</span><span class="shot-title">{escape(i["title"])}</span></figcaption></figure>'
        for n, i in enumerate(tree["photos"])
    )
    return f'<div class="photo-panel">{shots}</div>'


def render_home(data: dict) -> str:
    site, home = data["site"], data["home"]
    hero = home["hero"]
    stats = "".join(
        f'<li class="fact">{fact_value(s["value"])}<span class="fact-label">{escape(s["label"])}</span></li>'
        for s in home["stats"]
    )
    explore = home["explore"]
    tree = home["tree_nav"]
    explore_items = "".join(
        f'<li><a class="explore-link" href="{attr_url(i["href"])}" data-explore="{escape(i["id"])}">'
        f'<span class="explore-text"><span class="explore-label">{escape(i["label"])}</span>'
        f'<span class="explore-desc">{escape(i["text"])}</span></span>{ICONS["arrow"]}</a></li>'
        for i in explore["items"]
    )
    posts = data["news"]["items"][: home["latest_news"].get("count", 3)]
    news_cards = "".join(news_card(p, i == 0) for i, p in enumerate(posts))
    quote = home["quote"]
    bld, sup = home["bld_band"], home["support_band"]
    visit = data["visit"]
    content = f"""
<section class="hero" aria-labelledby="hero-title">
  <picture class="hero-media">
    <source media="(max-width: 700px)" srcset="{attr_url(hero["background_image_small"])}">
    <img src="{attr_url(hero["background_image"])}" alt="Old European Beech trees casting dappled shade across the lawn at Longwood Mall"{dims(hero["background_image"])} fetchpriority="high">
  </picture>
  <div class="hero-scrim" aria-hidden="true"></div>
  {hero_leaves()}
  <div class="container hero-content">
    <p class="hero-eyebrow">{escape(hero["eyebrow"])}</p>
    <h1 id="hero-title" class="hero-title">{br_join(hero["title_lines"])}</h1>
    <p class="hero-lede">{escape(hero["subtitle"])}</p>
    {buttons_row(hero["buttons"])}
  </div>
</section>

<section class="facts-band" aria-label="Longwood Mall at a glance">
  <ul class="container facts">{stats}</ul>
</section>

<section class="section explore" aria-labelledby="explore-title">
  <div class="container explore-grid">
    <div class="explore-copy">
      <p class="eyebrow">{escape(explore["eyebrow"])}</p>
      <h2 id="explore-title" class="section-title">{escape(explore["title"])}</h2>
      <p class="section-lede">{escape(explore["description"])}</p>
      <ul class="explore-list">{explore_items}</ul>
    </div>
    <figure class="explore-tree">
      {photo_panel(tree) if tree.get("mode") == "photos" else tree_plate(tree)}
      <figcaption class="tree-quote"><blockquote>&ldquo;{escape(quote["text"])}&rdquo;</blockquote><cite>{escape(quote["author"])}</cite></figcaption>
    </figure>
  </div>
</section>

<section class="section section-tint" aria-labelledby="news-title">
  <div class="container">
    <div class="section-head">
      <div><p class="eyebrow">From the park</p><h2 id="news-title" class="section-title">Latest news</h2></div>
      <a class="btn btn-outline" href="latest-news.html"><span>All news</span>{ICONS["arrow"]}</a>
    </div>
    <div class="news-grid">{news_cards}</div>
  </div>
</section>

<section class="band band-dark" aria-labelledby="bld-title">
  <div class="container band-grid">
    <div>
      <p class="eyebrow eyebrow-light">{escape(bld["eyebrow"])}</p>
      <h2 id="bld-title" class="section-title">{escape(bld["title"])}</h2>
    </div>
    <div>
      <p class="band-text">{escape(bld["text"])}</p>
      {buttons_row(bld["buttons"])}
    </div>
  </div>
</section>

<section class="section" aria-label="Visit and support">
  <div class="container duo">
    <article class="panel panel-visit">
      <p class="eyebrow">Plan your visit</p>
      <h2 class="panel-title">Visit the park</h2>
      <ul class="info-list">
        <li>{ICONS["pin"]}<span><strong>Where</strong>{escape(", ".join(visit["address_lines"]))}</span></li>
        <li>{ICONS["clock"]}<span><strong>When</strong>Open daily, dawn to dusk. Free.</span></li>
        <li>{ICONS["train"]}<span><strong>By T</strong>One block from Hawes Street (Green Line C)</span></li>
      </ul>
      <p class="panel-note">Please help protect the trees: no dogs, and no climbing or sitting on trunks and branches.</p>
      <div class="button-row">
        <a class="btn btn-primary" href="visit.html"><span>Visitor information</span>{ICONS["arrow"]}</a>
        {link(site["directions_href"], "<span>Get directions</span>", "btn btn-outline")}
      </div>
    </article>
    <article class="panel panel-support">
      {f'<div class="panel-media">{img_tag(sup["image"], sup.get("image_alt", ""), 640)}</div>' if sup.get("image") else ""}
      <p class="eyebrow">{escape(sup["eyebrow"])}</p>
      <h2 class="panel-title">{escape(sup["title"])}</h2>
      <p>{escape(sup["text"])}</p>
      {buttons_row(sup["buttons"])}
    </article>
  </div>
</section>
"""
    return wrap_page(site, "home", home["meta_title"], home["meta_description"], "page-home", content)


# --------------------------------------------------------------------------- news


NEWS_LINKS: dict[str, str] = {}


def news_href(post_id: str) -> str:
    return f"news-{post_id}.html"


def post_body(post: dict) -> str:
    images = []
    group = f'news-{post["id"]}'
    for item in post.get("images", []):
        if item.get("href"):
            cap = f'<figcaption>{escape(item["caption"])}</figcaption>' if item.get("caption") else ""
            cls = " news-logo" if item.get("variant") == "logo" else ""
            label = item.get("link_label", item["alt"])
            extra = f' aria-label="{escape(label)} (opens in a new tab)"' if item.get("external") else f' aria-label="{escape(label)}"'
            images.append(
                f'<figure class="zoom-figure{cls}">'
                + link(item["href"], img_tag(item["src"], item["alt"], 640), "image-link", item.get("external"), extra)
                + f"{cap}</figure>"
            )
        else:
            images.append(zoomable_figure(item["src"], item["alt"], item.get("caption", ""), group=group))
    image_markup = f'<div class="media-grid media-grid-{min(len(images), 3)}">{"".join(images)}</div>' if images else ""
    embedded = (post.get("iframe") or {}).get("src", "").split("#")[0]
    post_links = [l for l in post.get("links", []) if l["href"].split("#")[0] != embedded]
    links = ""
    if post_links:
        items = "".join(
            f"<li>{link(l['href'], escape(l['label']), 'text-link', is_external(l['href']))}</li>"
            for l in sorted(post_links, key=lambda l: l.get("index", 0))
        )
        links = f'<ul class="resource-list">{items}</ul>'
    embed = embed_block(post["iframe"]) if post.get("iframe") else ""
    after = post.get("image_position") == "after_paragraphs"
    return f"""{"" if after else image_markup}
<div class="prose">{render_paragraphs(post["paragraphs"])}</div>
{image_markup if after else ""}
{links}
{embed}"""


def post_teaser(post: dict, label: str) -> str:
    return (
        f'<a class="post-nav-link" href="{attr_url(news_href(post["id"]))}"><span class="post-nav-label">{escape(label)}</span>'
        f'<span class="post-nav-title">{escape(post["title"])}</span><span class="card-date">{escape(post["date"])}</span></a>'
    )


def render_news_post_page(site: dict, news: dict, index: int) -> str:
    items = news["items"]
    post = items[index]
    newer = items[index - 1] if index > 0 else None
    older = items[index + 1] if index + 1 < len(items) else None
    pager = '<nav class="post-nav" aria-label="More posts">'
    pager += post_teaser(newer, "Newer post") if newer else "<span></span>"
    pager += post_teaser(older, "Older post") if older else "<span></span>"
    pager += "</nav>"
    header = render_page_header(escape(post["title"]), "", [("Latest news", "latest-news.html")],
                                eyebrow=post["date"], wide=True, meta="Posted by Friends of Longwood Mall")
    content = f"""{header}
<section class="section section-tight">
  <div class="container">
    <article class="post-article" aria-labelledby="post-title">{post_body(post)}
      <p class="post-contact">Questions or something to report? <a href="support.html#contact">Contact the Friends of Longwood Mall</a>.</p>
    </article>
    {pager}
    <p class="article-back"><a class="text-link" href="latest-news.html">{ICONS["prev"]}<span>All news</span></a></p>
  </div>
</section>"""
    page = wrap_page(site, "news", f'{post["title"]} | Longwood Mall', post["summary"], "page-interior page-post", content, lightbox=True)
    return page.replace('<h1 class="page-title">', '<h1 class="page-title" id="post-title">', 1)


def render_news_page(data: dict) -> str:
    site, news = data["site"], data["news"]
    groups: dict[str, list] = {}
    for post in news["items"]:
        groups.setdefault(year_of(post["date"]), []).append(post)
    year_links = "".join(f'<li><a class="year-chip" href="#y{escape(y)}">{escape(y)}</a></li>' for y in groups)
    sections = []
    first = True
    for year, posts in groups.items():
        cards = []
        for post in posts:
            aliases = "".join(
                f'<span class="anchor-alias" id="{attr_url(a)}" data-post-href="{attr_url(news_href(post["id"]))}"></span>'
                for a in post.get("anchor_aliases", [])
            )
            card = news_card(post, featured=first)
            card = card.replace('<article class="news-card', f'<article id="{attr_url(post["id"])}" data-post-href="{attr_url(news_href(post["id"]))}" class="news-card', 1)
            card = card.replace('<div class="news-card-body">', f'<div class="news-card-body">{aliases}', 1)
            cards.append(card)
            first = False
        sections.append(
            f'<section class="news-year" id="y{escape(year)}" aria-labelledby="y{escape(year)}-h">'
            f'<h2 class="news-year-title" id="y{escape(year)}-h">{escape(year)}</h2><div class="news-list">{"".join(cards)}</div></section>'
        )
    header = render_page_header(
        "Latest news",
        "Events, plantings, Beech Leaf Disease treatment, and other updates from Longwood Mall, newest first.",
        [("Latest news", None)],
        eyebrow=news.get("eyebrow", "Updates"),
        meta=f'{len(news["items"])} posts, 2012 to 2026',
        actions=f'<nav class="year-nav" aria-label="Jump to year"><ul>{year_links}</ul></nav>',
    )
    content = f'{header}<div class="container news-archive">{"".join(sections)}</div>'
    return wrap_page(site, "news", news["meta_title"], news["meta_description"], "page-interior page-news", content)


# --------------------------------------------------------------------------- photos


def render_photos_overview(data: dict) -> str:
    site, photos = data["site"], data["photos"]
    cards = []
    for c in photos["collections"]:
        if c["id"] == "inventory":
            count = len(resolve_inventory_groups(c))
            count_label = f"{count} trees"
        else:
            count_label = f"{len(resolve_collection_items(c))} photos"
        cards.append(
            f'<article class="collection-card"><div class="collection-media">{img_tag(c["image"], "", 640)}</div>'
            f'<div class="collection-body"><p class="card-meta">{escape(count_label)}</p>'
            f'<h2 class="collection-title"><a class="stretched-link" href="{attr_url(c["slug"])}">{escape(" ".join(c["title_lines"]))}</a></h2>'
            f'<p>{escape(c["summary"])}</p><span class="text-link" aria-hidden="true">View collection {ICONS["arrow"]}</span></div></article>'
        )
    video = photos["drone_video"]
    cards.append(
        f'<article class="collection-card collection-card-video"><div class="collection-body"><p class="card-meta">{len(video["reels"])} short videos</p>'
        f'<h2 class="collection-title"><a class="stretched-link" href="{attr_url(video["slug"])}">Drone video</a></h2>'
        f'<p>Fly over the grove: short aerial clips of Longwood Mall shared on Instagram.</p><span class="text-link" aria-hidden="true">Watch {ICONS["arrow"]}</span></div></article>'
    )
    header = render_page_header(
        "Photos",
        "Browse the park today, from above, tree by tree, and through more than a century of historical images.",
        [("Photos", None)],
        eyebrow="Collections",
        actions=f'<div class="button-row"><a class="btn btn-outline" href="mailto:{attr_url(site["contact_email"])}?subject=Photo%20for%20Longwood%20Mall">{ICONS["mail"]}<span>Share a photo with us</span></a></div>',
    )
    content = f'{header}<section class="section section-tight"><div class="container collection-grid">{"".join(cards)}</div></section>'
    return wrap_page(site, "photos", photos["meta_title"], photos["meta_description"], "page-interior page-photos", content)


def pile_offsets(index: int) -> tuple[float, float]:
    """Deterministic 'tossed print' tilt (degrees) and sideways shift (%) for a photo in the pile."""
    unit = lambda seed: (math.sin(index * 127.1 + seed * 311.7) * 43758.5453) % 1
    tilt = (2 + unit(3) * 3.5) * (-1 if index % 2 == 0 else 1)
    shift = (unit(2) - 0.5) * 14
    return round(tilt, 2), round(shift, 2)


def render_gallery(items: list[dict], group: str = "gallery") -> str:
    """One set of photos that can be shown as the signature 'photo pile' or as a grid."""
    total = len(items)
    photos = []
    for index, item in enumerate(items):
        source = item.get("source") or {}
        caption = item.get("caption", "")
        credit = source.get("label", "")
        credit_url = source.get("url", "")
        cap_parts = []
        if caption:
            cap_parts.append(f'<span class="photo-caption">{escape(caption)}</span>')
        if credit:
            src_link = link(credit_url, escape(credit), "photo-credit-link", True) if credit_url else escape(credit)
            cap_parts.append(f'<span class="photo-credit">Source: {src_link}</span>')
        cap_parts.append(f'<span class="photo-number" aria-hidden="true">{index + 1:02d} / {total:02d}</span>')
        tilt, shift = pile_offsets(index)
        size = image_size(resized(item["src"], 640)) or image_size(item["src"]) or (4, 3)
        ratio = round(size[0] / size[1], 4)
        photos.append(
            f'<figure class="photo" style="--i: {index + 1}; --tilt: {tilt}deg; --shift: {shift}%; --ar: {ratio}" data-photo>'
            f'<button class="zoom-trigger" type="button" data-lightbox-item data-group="{group}" data-src="{attr_url(item["src"])}" '
            f'data-alt="{escape(item["alt"])}" data-caption="{escape(caption)}" data-credit="{escape(credit)}" data-credit-url="{attr_url(credit_url)}">'
            f'{img_tag(item["src"], item["alt"], 640, "eager" if index < 3 else "lazy")}'
            f'<span class="zoom-hint">{ICONS["expand"]}<span class="visually-hidden"> (photo {index + 1} of {total}, enlarge)</span></span></button>'
            f'<figcaption>{"".join(cap_parts)}</figcaption></figure>'
        )
    captioned = " photos-captioned" if any(i.get("caption") or (i.get("source") or {}).get("label") for i in items) else ""
    return f"""<div class="gallery-view" data-gallery-view data-view="pile">
  <div class="view-bar">
    <p class="view-hint"><span class="view-hint-pile">Scroll to leaf through the pile.</span><span class="view-hint-grid">All {total} photos at a glance.</span> Select any photo to enlarge it.</p>
    <div class="view-toggle" role="group" aria-label="Gallery layout">
      <button type="button" class="view-btn" data-view-btn="pile" aria-pressed="true">Photo pile</button>
      <button type="button" class="view-btn" data-view-btn="grid" aria-pressed="false">Grid</button>
    </div>
  </div>
  <div class="photos{captioned}" data-photos>{"".join(photos)}</div>
  <button type="button" class="pile-counter" data-pile-counter data-view-btn="grid"><span aria-hidden="true"><span data-pile-current>01</span> / {total:02d}</span><span class="pile-counter-action">Show grid</span></button>
</div>"""


def collection_actions(site: dict, collection: dict, extra: list[dict] | None = None) -> str:
    items = list(extra or [])
    for b in collection.get("buttons", []):
        if b["href"] == "photos.html":
            continue
        if b["href"].startswith("mailto:"):
            items.append({"label": "Share a photo", "href": f'mailto:{site["contact_email"]}?subject=Photo%20for%20Longwood%20Mall', "variant": "outline"})
        else:
            items.append({**b, "variant": "outline"})
    return buttons_row(items)


def render_gallery_page(site: dict, collection: dict, items: list[dict] | None = None, page_title: str | None = None,
                        page_description: str | None = None, title: str | None = None, trail: list | None = None,
                        extra_buttons: list[dict] | None = None, pager: str = "") -> str:
    gallery_items = items if items is not None else resolve_collection_items(collection)
    active = "photos"
    heading = title or " ".join(collection["title_lines"])
    if trail is None:
        trail = [("Photos", "photos.html"), (heading, None)]
    header = render_page_header(
        escape(heading),
        collection["description"],
        trail,
        eyebrow="Photo collection",
        meta=f"{len(gallery_items)} photos",
        actions=collection_actions(site, collection, extra_buttons),
    )
    content = f'{header}<section class="section section-tight"><div class="container">{render_gallery(gallery_items)}{pager}</div></section>'
    return wrap_page(site, active, page_title or collection["page_title"], page_description or collection["page_description"],
                     "page-interior page-gallery", content, lightbox=True)


def render_inventory_index(site: dict, collection: dict, groups: list[dict]) -> str:
    cards = "".join(
        f'<article class="tree-card"><div class="tree-card-media">{img_tag(g["image"], "", 640)}</div>'
        f'<div class="tree-card-body"><h2 class="tree-card-title"><a class="stretched-link" href="{attr_url(g["slug"])}">{escape(g["label"])}</a></h2>'
        f'<p class="card-meta">{len(g["items"])} photos</p></div></article>'
        for g in groups
    )
    header = render_page_header(
        "Tree inventory",
        f'{collection["description"]} Each of the {len(groups)} beech trees has its own set of photos.',
        [("Photos", "photos.html"), ("Tree inventory", None)],
        eyebrow="Photo collection",
        actions=collection_actions(site, collection),
    )
    content = f'{header}<section class="section section-tight"><div class="container tree-grid">{cards}</div></section>'
    return wrap_page(site, "photos", collection["page_title"], collection["page_description"], "page-interior page-inventory", content)


def render_drone_video_page(data: dict) -> str:
    site = data["site"]
    section = data["photos"]["drone_video"]
    reels = "".join(
        f'<article class="reel-card"><blockquote class="instagram-media" data-instgrm-captioned '
        f'data-instgrm-permalink="{attr_url(r["permalink"])}?utm_source=ig_embed&amp;utm_campaign=loading" data-instgrm-version="14">'
        f'{link(r["permalink"], f"Watch drone video {i} on Instagram", "text-link", True)}</blockquote></article>'
        for i, r in enumerate(section["reels"], start=1)
    )
    header = render_page_header(
        "Drone video",
        "Short aerial clips of Longwood Mall, shared on the park's Instagram account.",
        [("Photos", "photos.html"), ("Drone video", None)],
        eyebrow="Video",
        actions=buttons_row([{"label": "Aerial photos", "href": "aerial-photos.html", "variant": "outline"}]),
    )
    content = (
        f'{header}<section class="section section-tight"><div class="container reel-grid">{reels}</div></section>'
        '<script async src="https://www.instagram.com/embed.js"></script>'
    )
    return wrap_page(site, "photos", section["page_title"], section["page_description"], "page-interior page-video", content)


# --------------------------------------------------------------------------- history


def render_history_page(data: dict) -> str:
    site, history = data["site"], data["history"]
    cards, reading = [], []
    for item in history["items"]:
        if item.get("external"):
            reading.append(
                f'<li class="reading-item"><p class="card-meta">{escape(item.get("kicker", ""))}</p>'
                f'{link(item["href"], escape(item["label"]), "reading-link", True)}<p>{escape(item.get("summary", ""))}</p></li>'
            )
            continue
        media = f'<div class="history-card-media">{img_tag(item["image"], "", 640)}</div>' if item.get("image") else ""
        cards.append(
            f'<article class="history-card">{media}<div class="history-card-body"><p class="card-meta">{escape(item.get("kicker", ""))}</p>'
            f'<h2 class="history-card-title"><a class="stretched-link" href="{attr_url(item["href"])}">{escape(item["label"])}</a></h2>'
            f'<p>{escape(item.get("summary", ""))}</p><span class="text-link" aria-hidden="true">{escape(item.get("cta", "Read"))} {ICONS["arrow"]}</span></div></article>'
        )
    reading_markup = ""
    if reading:
        reading_markup = (
            '<section class="further-reading" aria-labelledby="reading-title"><h2 class="section-subtitle" id="reading-title">Further reading on other sites</h2>'
            f'<ul class="reading-list">{"".join(reading)}</ul></section>'
        )
    header = render_page_header("History", history["description"], [("History", None)], eyebrow="Since the 1840s")
    content = f'{header}<section class="section section-tight"><div class="container"><div class="history-grid">{"".join(cards)}</div>{reading_markup}</div></section>'
    return wrap_page(site, "history", history["meta_title"], history["meta_description"], "page-interior page-history", content)


def render_history_article_page(site: dict, article: dict) -> str:
    figures = []
    for index, image_item in enumerate(article["images"], start=1):
        if isinstance(image_item, str):
            src, alt, caption = image_item, f'{article["title"]}, page {index}', ""
        else:
            src = image_item["src"]
            alt = image_item.get("alt", f'{article["title"]}, page {index}')
            caption = image_item.get("caption", "")
        figures.append(zoomable_figure(src, alt, caption, "document", group="doc"))
    size_cls = " documents-small" if article.get("image_size") == "small" else ""
    single = " documents-single" if len(figures) == 1 else ""
    note = f'<p class="documents-note">{escape(article["image_note"])}</p>' if article.get("image_note") else ""
    documents = f'<div class="documents{size_cls}{single}">{"".join(figures)}</div>{note}'
    split = article.get("image_after_paragraph")
    if isinstance(split, int):
        body = f'{render_paragraphs(article["paragraphs"][:split])}{documents}{render_paragraphs(article["paragraphs"][split:])}'
    else:
        body = f'{render_paragraphs(article["paragraphs"])}{documents}'
    title = plain_join(article.get("title_lines", [article["title"]]))
    header = render_page_header(title, "", [("History", "history.html"), (article["title"], None)], eyebrow="History")
    content = f"""{header}<section class="section section-tight"><div class="container"><article class="prose prose-article">{body}</article>
<p class="article-back"><a class="text-link" href="history.html">{ICONS["prev"]}<span>All history</span></a></p></div></section>"""
    return wrap_page(site, "history", article["meta_title"], article["meta_description"], "page-interior page-article", content, lightbox=True)


# --------------------------------------------------------------------------- BLD


def video_card(section: dict) -> str:
    video = section["youtube"]
    vid = video["id"]
    thumbs = ""
    if section.get("images"):
        thumbs = '<div class="video-card-thumbs">' + "".join(
            zoomable_figure(i["src"], i["alt"], group=f'bld-{section["id"]}') for i in section["images"]
        ) + "</div>"
    return f"""<article class="video-card" id="{attr_url(section["id"])}">
  <div class="video-embed" data-youtube="{attr_url(vid)}" data-title="{escape(video["title"])}">
    <button class="video-facade" type="button" aria-label="Play video: {escape(section.get("card_title", video["title"]))}">
      <img src="https://i.ytimg.com/vi/{attr_url(vid)}/hqdefault.jpg" alt="" width="480" height="360" loading="lazy" decoding="async">
      <span class="video-play" aria-hidden="true">{ICONS["play"]}</span>
    </button>
  </div>
  <div class="video-card-body">
    <p class="card-date">{escape(section.get("date", ""))}</p>
    <h3 class="video-card-title">{escape(section.get("card_title", section["title"]))}</h3>
    <p>{escape(section.get("card_text", ""))}</p>
    {thumbs}
    {link("https://www.youtube.com/watch?v=" + vid, "Watch on YouTube", "text-link", True)}
  </div>
</article>"""


def render_bld_page(data: dict) -> str:
    site, bld = data["site"], data["bld"]
    secs = {s["id"]: s for s in bld["page_sections"]}
    glance = "".join(
        f'<article class="glance-card"><h2 class="glance-title">{escape(g["title"])}</h2><p>{escape(g["text"])}</p>'
        + (f'<a class="text-link" href="{attr_url(g["href"])}">{escape(g["link_label"])} {ICONS["arrow"]}</a>' if g.get("href") else "")
        + "</article>"
        for g in bld["at_a_glance"]
    )
    updates = "".join(
        f'<li class="timeline-item"><p class="card-date">{escape(u["date"])}</p><h3 class="timeline-title"><a href="{attr_url(u["href"])}">{escape(u["title"])}</a></h3><p>{escape(u["text"])}</p></li>'
        for u in bld["updates"]
    )
    about = secs["what-is-bld"]
    videos = [s for s in bld["page_sections"] if s.get("youtube")]
    article = secs.get("brookline-news")
    article_card = ""
    if article:
        article_card = link_card(article["iframe"]["title"], article["iframe"]["src"], f'Brookline.News · {article.get("date", "")}',
                                 article.get("card_text", ""), cta="Read the article")
    reading = secs.get("links", {"links": []})
    reading_items = "".join(
        f"<li>{link(l['href'], escape(l['label']), 'text-link', True)}</li>"
        for l in sorted(reading["links"], key=lambda l: l.get("index", 0))
    )
    toc = [("updates", "Treatment timeline"), ("what-is-bld", about["title"]), ("videos", "Videos and webinars"),
           ("brookline-news", "In the news"), ("links", reading.get("title", "Further reading"))]
    toc_links = "".join(f'<li><a href="#{attr_url(i)}" data-toc-link>{escape(t)}</a></li>' for i, t in toc)
    header = render_page_header("Beech Leaf Disease", bld["description"], [("Beech Leaf Disease", None)], eyebrow="Protecting the grove")
    content = f"""{header}
<section class="section section-tight" aria-label="At a glance">
  <div class="container"><div class="glance-grid">{glance}</div></div>
</section>
<div class="container layout-sidebar">
  <aside class="sidebar" aria-label="On this page">
    <details class="toc" data-toc open><summary class="toc-summary">On this page</summary><ol class="toc-list">{toc_links}</ol></details>
  </aside>
  <div class="layout-main">
    <section class="doc-section" id="updates" aria-labelledby="updates-h">
      <h2 class="doc-section-title" id="updates-h">Treatment timeline at Longwood Mall</h2>
      <ol class="timeline">{updates}</ol>
    </section>
    <section class="doc-section" id="what-is-bld" aria-labelledby="what-is-bld-h">
      <h2 class="doc-section-title" id="what-is-bld-h">{escape(about["title"])}</h2>
      <div class="prose">{render_paragraphs(about["paragraphs"])}</div>
    </section>
    <section class="doc-section" id="videos" aria-labelledby="videos-h">
      <h2 class="doc-section-title" id="videos-h">Videos and webinars</h2>
      <div class="video-grid">{"".join(video_card(v) for v in videos)}</div>
    </section>
    <section class="doc-section" id="brookline-news" aria-labelledby="news-h">
      <h2 class="doc-section-title" id="news-h">In the news</h2>
      {article_card}
    </section>
    <section class="doc-section" id="links" aria-labelledby="links-h">
      <h2 class="doc-section-title" id="links-h">{escape(reading.get("title", "Further reading"))}</h2>
      <ul class="resource-list resource-list-2">{reading_items}</ul>
    </section>
  </div>
</div>"""
    return wrap_page(site, "bld", bld["meta_title"], bld["meta_description"], "page-interior page-bld", content, lightbox=True)


# --------------------------------------------------------------------------- visit / support / donations


def render_visit_page(data: dict) -> str:
    site, visit = data["site"], data["visit"]
    facts = "".join(f'<div class="fact-row"><dt>{escape(f["label"])}</dt><dd>{escape(f["value"])}</dd></div>' for f in visit["facts"])
    ways = "".join(f'<article class="way"><h3 class="way-title">{escape(w["title"])}</h3><p>{escape(w["text"])}</p></article>' for w in visit["getting_there"])
    rules = "".join(f"<li>{escape(r)}</li>" for r in visit["rules"])
    signs = "".join(zoomable_figure(i["src"], i["alt"], cls="sign", group="signs") for i in visit["images"])
    header = render_page_header(escape(visit["title"]), visit["description"], [("Visit", None)], eyebrow=visit["eyebrow"])
    content = f"""{header}
<section class="section section-tight">
  <div class="container visit-grid">
    <div class="panel visit-info">
      <h2 class="panel-title">Location and hours</h2>
      <address class="visit-address">{ICONS["pin"]}<span>{"<br>".join(escape(l) for l in visit["address_lines"])}</span></address>
      <dl class="fact-list">{facts}</dl>
      <div class="button-row">{link(site["directions_href"], "<span>Get directions</span>", "btn btn-primary")}</div>
    </div>
    <figure class="map-frame">
      <iframe src="{attr_url(visit["map_embed"])}" title="Map of the walking route from the Hawes Street T stop to Longwood Mall in Brookline, Massachusetts" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
      <figcaption class="map-caption">{escape(visit.get("map_caption", ""))}</figcaption>
    </figure>
  </div>
</section>
<section class="section section-tint" aria-labelledby="getting-there">
  <div class="container">
    <h2 class="section-title" id="getting-there">Getting there</h2>
    <div class="ways">{ways}</div>
  </div>
</section>
<section class="section" id="rules" aria-labelledby="rules-title">
  <div class="container rules-grid">
    <div>
      <p class="eyebrow">Protect the trees</p>
      <h2 class="section-title" id="rules-title">Park rules</h2>
      <p class="section-lede">{escape(visit["rules_intro"])}</p>
      <ul class="check-list">{rules}</ul>
    </div>
    <div class="signs">{signs}</div>
  </div>
</section>"""
    return wrap_page(site, "visit", visit["meta_title"], visit["meta_description"], "page-interior page-visit", content, lightbox=True)


def render_contact_form(site: dict, support: dict) -> str:
    email = site["contact_email"]
    return f"""<section class="section section-tint" id="contact" aria-labelledby="contact-title">
  <div class="container contact-grid">
    <div>
      <p class="eyebrow">Get in touch</p>
      <h2 class="section-title" id="contact-title">{escape(support["contact_title"])}</h2>
      <p class="section-lede">{escape(support["contact_text"])}</p>
      <div class="email-box">
        <p class="email-box-label">Email us directly</p>
        <p class="email-box-row"><a class="email-address" href="mailto:{attr_url(email)}">{escape(email)}</a>
        <button class="btn btn-small btn-outline" type="button" data-copy="{attr_url(email)}">{ICONS["copy"]}<span data-copy-label>Copy</span></button></p>
      </div>
      <p class="contact-aside">{escape(support.get("contact_reply", ""))} You can also follow and message the park on {link(site["instagram"], "Instagram", "text-link", True)}.</p>
    </div>
    <form class="contact-form panel" data-contact-form data-email="{attr_url(email)}" data-subject="{attr_url(support["contact_subject"])}" novalidate>
      <p class="form-note">All fields are required. Sending opens your email app with the message ready to go; nothing is sent until you press send there.</p>
      <div class="field">
        <label for="cf-name">Your name</label>
        <input id="cf-name" name="name" type="text" autocomplete="name" required aria-describedby="cf-name-error">
        <p class="field-error" id="cf-name-error" data-error-for="name"></p>
      </div>
      <div class="field">
        <label for="cf-email">Your email</label>
        <input id="cf-email" name="email" type="email" autocomplete="email" required aria-describedby="cf-email-error">
        <p class="field-error" id="cf-email-error" data-error-for="email"></p>
      </div>
      <div class="field">
        <label for="cf-message">Message</label>
        <textarea id="cf-message" name="message" rows="6" required aria-describedby="cf-message-error"></textarea>
        <p class="field-error" id="cf-message-error" data-error-for="message"></p>
      </div>
      <button class="btn btn-primary btn-block" type="submit">{ICONS["mail"]}<span>Write email</span></button>
      <div class="form-status" data-form-status role="status" aria-live="polite" hidden></div>
    </form>
  </div>
</section>"""


def render_support_page(data: dict) -> str:
    site, support = data["site"], data["support"]
    ways = "".join(
        f'<article class="way way-card" id="way-{escape(w["id"])}"><span class="way-num" aria-hidden="true">{i:02d}</span>'
        f'<h2 class="way-title">{escape(w["title"])}</h2><p>{escape(w["text"])}</p>'
        f'<a class="text-link" href="{attr_url(w["href"])}">{escape(w["link_label"])} {ICONS["arrow"]}</a></article>'
        for i, w in enumerate(support["ways"], start=1)
    )
    header = render_page_header(escape(support["title"]), support["description"], [("Support", None)], eyebrow="Get involved",
                                actions=buttons_row([{"label": "How to donate", "href": "donations.html", "variant": "primary"},
                                                     {"label": "Contact the Friends", "href": "#contact", "variant": "outline"}]))
    content = f"""{header}
<section class="section section-tight"><div class="container ways ways-3">{ways}</div></section>
{render_contact_form(site, support)}"""
    return wrap_page(site, "support", support["meta_title"], support["meta_description"], "page-interior page-support", content)


def render_donations_page(data: dict) -> str:
    site, d = data["site"], data["donations"]
    email = d["contact_email"]
    subject = quote("Longwood Mall donation")
    address = "<br>".join(escape(l) for l in d["mail_to"])
    copy_text = "\n".join(d["mail_to"])
    header = render_page_header(escape(d["title"]), d["description"], [("Support", "support.html"), ("Donate", None)], eyebrow="Give")
    content = f"""{header}
<section class="section section-tight">
  <div class="container donate-grid">
    <ol class="steps">
      <li class="step"><h2 class="step-title">Write a check payable to</h2><p class="step-value">{escape(d["check_payable"])}</p></li>
      <li class="step"><h2 class="step-title">Mail it to</h2><address class="step-value">{address}</address>
        <button class="btn btn-small btn-outline" type="button" data-copy="{attr_url(copy_text)}">{ICONS["copy"]}<span data-copy-label>Copy address</span></button></li>
      <li class="step"><h2 class="step-title">Let us know</h2><p>Email us after you give so we can track donations made for Longwood Mall. Ask us about donor-advised funds or any other questions.</p>
        <a class="btn btn-primary" href="mailto:{attr_url(email)}?subject={subject}">{ICONS["mail"]}<span>Email the Friends</span></a></li>
    </ol>
    <div class="prose donate-why"><h2 class="section-subtitle">Why your gift matters</h2>{render_paragraphs(d["paragraphs"][:2])}</div>
  </div>
</section>"""
    return wrap_page(site, "support", d["meta_title"], d["meta_description"], "page-interior page-donate", content)


# --------------------------------------------------------------------------- build


def build() -> None:
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    site = data["site"]
    site["visit_address"] = ", ".join(data["visit"]["address_lines"])

    for post in data["news"]["items"]:
        NEWS_LINKS[post["id"]] = news_href(post["id"])
        for alias in post.get("anchor_aliases", []):
            NEWS_LINKS[alias] = news_href(post["id"])

    home = render_home(data)
    outputs = {
        "index.html": home,
        "index-classic.html": home,
        "history.html": render_history_page(data),
        "latest-news.html": render_news_page(data),
        "photos.html": render_photos_overview(data),
        data["photos"]["drone_video"]["slug"]: render_drone_video_page(data),
        "beech-leaf-disease.html": render_bld_page(data),
        "visit.html": render_visit_page(data),
        "support.html": render_support_page(data),
        "donations.html": render_donations_page(data),
    }
    for article in data.get("history_articles", {}).values():
        outputs[article["slug"]] = render_history_article_page(site, article)
    for index, post in enumerate(data["news"]["items"]):
        outputs[news_href(post["id"])] = render_news_post_page(site, data["news"], index)

    for collection in data["photos"]["collections"]:
        if collection.get("id") == "inventory":
            groups = resolve_inventory_groups(collection)
            outputs[collection["slug"]] = render_inventory_index(site, collection, groups)
            for i, group in enumerate(groups):
                prev_g = groups[i - 1] if i > 0 else None
                next_g = groups[i + 1] if i + 1 < len(groups) else None
                pager = '<nav class="pager" aria-label="Other trees">'
                pager += f'<a class="btn btn-outline" href="{attr_url(prev_g["slug"])}">{ICONS["prev"]}<span>{escape(prev_g["label"])}</span></a>' if prev_g else "<span></span>"
                pager += f'<a class="btn btn-outline" href="{attr_url(collection["slug"])}"><span>All trees</span></a>'
                pager += f'<a class="btn btn-outline" href="{attr_url(next_g["slug"])}"><span>{escape(next_g["label"])}</span>{ICONS["next"]}</a>' if next_g else "<span></span>"
                pager += "</nav>"
                outputs[group["slug"]] = render_gallery_page(
                    site,
                    {**collection, "description": f'{group["label"]} in the November 2025 tree inventory. Photos by Emily Lyons.'},
                    items=group["items"],
                    page_title=group["page_title"],
                    page_description=group["page_description"],
                    title=group["label"],
                    trail=[("Photos", "photos.html"), ("Tree inventory", collection["slug"]), (group["label"], None)],
                    extra_buttons=[{"label": "All trees", "href": collection["slug"], "variant": "outline"}],
                    pager=pager,
                )
            continue
        outputs[collection["slug"]] = render_gallery_page(site, collection)

    for filename, markup in outputs.items():
        (ROOT / filename).write_text(markup, encoding="utf-8")


if __name__ == "__main__":
    build()
