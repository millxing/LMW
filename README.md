# Longwood Mall Static Site

This repo contains the active static website for Longwood Mall in Brookline, Massachusetts.

The site is generated from structured content in `src/site.json` and currently publishes these pages:

- `index.html`
- `latest-news.html`
- `photos.html`
- `historical-photos.html`
- `contemporary-photos.html`
- `beech-leaf-disease.html`
- `support.html`

## Editing workflow

The generated HTML files in the repo root are build artifacts.

For normal edits:

1. Update content, links, metadata, and page structure in `src/site.json`
2. Update presentation in `style.css`
3. Update interaction behavior in `script.js` if needed
4. Rebuild with `python3 build_site.py`

## Common tasks

### Change text

Most copy now lives in page-specific sections inside `src/site.json`:

- `home`
- `news`
- `photos`
- `bld`
- `support`

### Change photos

Images live in `assets/` and are referenced with relative paths like `./assets/photo.jpg`.

Common places to update:

- Home hero: `home.hero.background_image`
- News hero: `news.hero.image`
- Photo collections: `photos.collections[*].image` and `photos.collections[*].items`
- BLD page: `bld.hero.image` and `bld.media.image`
- Support page: `support.hero.image` and `support.partner.image`

### Change navigation or footer

Edit `site.navigation` and `site.footer` in `src/site.json`.

### Add a page or section

Add the content to `src/site.json`, then extend the relevant render function in `build_site.py`.

## Local preview

From this folder:

```bash
python3 build_site.py
python3 -m http.server 8000
```

Then open [http://localhost:8000](http://localhost:8000).

## Hosting

This site is intended to work well on GitHub Pages, so keep local asset paths relative and avoid server-side assumptions.
