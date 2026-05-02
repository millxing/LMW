# Longwood Mall Site Agent Guide

## Project at a glance

- This repo holds the active static website for **Longwood Mall** in Brookline, Massachusetts.
- The site is now a **small multi-page informational site**, not a single-page homepage.
- The current emphasis is on:
  - latest news and stewardship updates
  - historical and contemporary photo collections
  - Beech Leaf Disease background and treatment context
  - support and community action

## Current stack

- `src/site.json`: main source of truth for content, links, page metadata, and collection data
- `build_site.py`: Python generator that renders the root-level HTML pages
- `style.css`: shared styling, layout, and motion system
- `script.js`: mobile navigation and scroll/reveal behavior
- `assets/`: active images and supporting files used by the generated pages

There is no frontend framework, no bundler, and no server-side runtime in the active site.

## Pages generated today

- `index.html`
- `latest-news.html`
- `photos.html`
- `historical-photos.html`
- `contemporary-photos.html`
- `beech-leaf-disease.html`
- `support.html`

Treat those root HTML files as generated output, not the primary editing surface.

## Hosting

- The intended host is **GitHub Pages**.
- Relative paths matter. Keep assets referenced like `./assets/file.jpg` unless the publish model changes.
- If deployment is automated later, `python3 build_site.py` needs to run before publishing, or the generated HTML files need to be committed.

## Editing workflow

For normal updates:

1. Edit content in `src/site.json`
2. Edit presentation in `style.css`
3. Edit interaction or motion in `script.js` if needed
4. Rebuild with `python3 build_site.py`
5. Preview locally with `python3 -m http.server 8000`

## Content map

The largest editable sections in `src/site.json` are:

- `site`: shared nav, footer, brand, and metadata
- `home`: homepage hero, stats, section intros, CTA
- `news`: latest-news page hero and post entries
- `photos`: photo overview page plus both collections
- `bld`: Beech Leaf Disease page content
- `support`: support page content and partner info

## Important project rules

- Prefer editing `src/site.json` instead of hand-editing generated HTML.
- Running `python3 build_site.py` will overwrite the generated root HTML files.
- Keep copy aligned with the current IA: avoid reintroducing generic one-page sections like the older `about` or `visit` content unless the user explicitly wants them back.
- The user specifically does **not** want “archive” language in the public site. Use phrasing like “more updates,” “earlier posts,” or “full collection” instead.
- Be careful with absolute-root URLs and asset paths because the site is meant for GitHub Pages.

## Known gotchas

- The generator is page-specific rather than fully abstract. Adding a brand-new page usually means touching both `src/site.json` and `build_site.py`.
- The site now includes light JavaScript for the mobile nav and reveal/header motion. If something looks static or broken on mobile, check `script.js`.
- Legacy material lives in `older stuff/`. It is reference material, not the active production source.
- The active assets folder already includes selected images copied forward from legacy drafts. Prefer reusing those before adding duplicate files.

## Repo layout notes

- `older stuff/WIX/`: raw exported legacy content
- `older stuff/site/`: cleaned static draft that was useful as a transfer source
- `older stuff/longwood-mall/`: React/Vite experiment, not the active site

If a task is about the live site, start with the root files and only consult `older stuff/` when you need legacy content.

## Good first reads for a new agent

- `README.md`
- `src/site.json`
- `build_site.py`
- `style.css`
- `script.js`

Those files are enough to understand how the current site is assembled.
