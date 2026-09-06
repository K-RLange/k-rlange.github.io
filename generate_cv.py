#!/usr/bin/env python3
"""
Site Generator - Generates the landing page, CV and project page from JSON data.
Usage: python generate_cv.py

Input:  cv_data.json, landing_data.json, projects_data.json, portrait.png
Output: index.html, cv.html, projects.html, assets/

Pillow is optional. If it is installed the portrait gets resized for the web,
otherwise the original file is used.
"""

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import quote

# --- Configuration ---

PHOTO_WIDTHS = (280, 560)           # generated portrait sizes (CSS px @1x/@2x)
ASSET_DIR = "assets"

FONT_LINKS = """    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">"""


# --- Data helpers ---

def load_json(json_path) -> dict:
    """Load data from JSON file."""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def as_list(value) -> list:
    """Wrap a value in a list. Accepts string, list or None."""
    if not value:
        return []
    return value if isinstance(value, list) else [value]


def format_notes(notes) -> str:
    """Format notes as HTML. Accepts string or list of strings."""
    if not notes:
        return ""
    if isinstance(notes, list):
        return "<br>".join(notes)
    return notes


def format_description(desc) -> str:
    """Format a description as HTML.

    Accepts:
    - string: "Simple description"
    - list:   ["Item 1", "Item 2", {"Header": ["sub1", "sub2"]}]
    - dict:   {"text": "Header", "items": ["sub1", "sub2"]}
    """
    if not desc:
        return ""
    if isinstance(desc, str):
        return f"<p>{desc}</p>"
    if isinstance(desc, list):
        html = '<ul class="bullets">'
        for item in desc:
            if isinstance(item, dict):
                for key, subitems in item.items():
                    html += f"<li>{key}"
                    if isinstance(subitems, list):
                        html += "<ul>"
                        for sub in subitems:
                            html += f"<li>{sub}</li>"
                        html += "</ul>"
                    html += "</li>"
            else:
                html += f"<li>{item}</li>"
        html += "</ul>"
        return html
    if isinstance(desc, dict):
        html = f'<p>{desc.get("text", "")}</p>'
        if desc.get("items"):
            html += '<ul class="bullets">'
            for item in desc["items"]:
                html += f"<li>{item}</li>"
            html += "</ul>"
        return html
    return str(desc)


def clean_url(value: str) -> str:
    """Build a usable href from a doi or link field.

    Copes with bare DOIs, full URLs and the stray %0A that sometimes gets
    copied along with a DOI.
    """
    if not value:
        return ""
    url = str(value).strip().replace("%0A", "").replace("\n", "").strip()
    if url.startswith(("http://", "https://")):
        return url
    if url.startswith("doi:"):
        url = url[4:]
    if url.startswith("10."):
        return f"https://doi.org/{url}"
    return url


def link_label(url: str) -> str:
    """Label a link by its host, e.g. arXiv or ACL Anthology."""
    lowered = url.lower()
    if "arxiv.org" in lowered:
        return "arXiv"
    if "doi.org" in lowered:
        return "DOI"
    if "aclanthology.org" in lowered:
        return "ACL Anthology"
    if "ceur-ws.org" in lowered:
        return "PDF"
    if "github.com" in lowered:
        return "GitHub"
    if "pypi.org" in lowered:
        return "PyPI"
    return "Link"


def author_pattern(full_name: str):
    """Regex matching my own name in an author list."""
    parts = [p for p in full_name.split() if p]
    if not parts:
        return None
    surname = parts[-1]
    variants = [re.escape(full_name),
                rf"{re.escape(surname)},\s*[A-ZÄÖÜ]\.(?:\s*[-–]\s*[A-ZÄÖÜ]\.?)?"]
    return re.compile("(" + "|".join(variants) + ")")


def highlight_author(authors: str, pattern) -> str:
    """Wrap my own name in a span so it can be highlighted."""
    if not pattern:
        return authors
    return pattern.sub(r'<span class="me">\1</span>', authors)


def file_size(name: str) -> str:
    """File size as KB/MB, empty string if the file is not there."""
    path = Path(__file__).parent / name
    if not path.exists():
        return ""
    kb = path.stat().st_size / 1024
    return f"{kb / 1024:.1f} MB" if kb >= 1024 else f"{kb:.0f} KB"


def initials_of(full_name: str) -> str:
    parts = [p for p in re.split(r"[-\s]", full_name) if p]
    return (parts[0][0] + parts[-1][0]).upper() if parts else "?"


# --- Images ---

def prepare_photo(root: Path, photo: str) -> dict:
    """Resize the portrait for the web and return the paths to use.

    Only rebuilds when portrait.png is newer than the existing files.
    Without Pillow it just returns the original.
    """
    fallback = {"webp": "", "png": photo}
    src = root / photo
    if not photo or not src.exists():
        return fallback

    out_dir = root / ASSET_DIR
    stem = Path(photo).stem
    targets = {w: out_dir / f"{stem}-{w}.webp" for w in PHOTO_WIDTHS}
    png_target = out_dir / f"{stem}-{PHOTO_WIDTHS[0]}.png"

    needs_build = not png_target.exists() or any(not p.exists() for p in targets.values())
    if not needs_build:
        newest = max(p.stat().st_mtime for p in [*targets.values(), png_target])
        needs_build = src.stat().st_mtime > newest

    if needs_build:
        try:
            from PIL import Image
        except ImportError:
            print("  ! Pillow not installed - using the original portrait "
                  "(consider `pip install Pillow` to shrink it).")
            return fallback

        out_dir.mkdir(exist_ok=True)
        with Image.open(src) as im:
            im = im.convert("RGBA")
            box = im.getbbox()
            if box:
                im = im.crop(box)
            for width, target in targets.items():
                im.resize((width, round(im.height * width / im.width)), Image.LANCZOS) \
                  .save(target, "WEBP", quality=86, method=6)
                print(f"  -> {target.relative_to(root)}")
            small = im.resize(
                (PHOTO_WIDTHS[0], round(im.height * PHOTO_WIDTHS[0] / im.width)),
                Image.LANCZOS,
            )
            small.save(png_target, "PNG", optimize=True)
            print(f"  -> {png_target.relative_to(root)}")

    return {
        "webp": ", ".join(f"{ASSET_DIR}/{stem}-{w}.webp {w}w" for w in PHOTO_WIDTHS),
        "png": f"{ASSET_DIR}/{stem}-{PHOTO_WIDTHS[0]}.png",
    }


def photo_html(photo: dict, name: str, css_class: str, sizes: str) -> str:
    """Portrait as a <picture> element."""
    img = (f'<img class="{css_class}" src="{photo["png"]}" alt="{name}" '
           f'width="280" height="280" decoding="async">')
    if not photo.get("webp"):
        return img
    return (f'<picture><source type="image/webp" srcset="{photo["webp"]}" '
            f'sizes="{sizes}">{img}</picture>')


# --- Icons ---

ICONS = {
    "mail": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/></svg>',
    "github": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 19c-4 1.4-4-2.3-6-2.8m12 5.3v-3.6a3.1 3.1 0 0 0-.9-2.4c2.9-.3 6-1.4 6-6.5a5 5 0 0 0-1.4-3.5 4.7 4.7 0 0 0-.1-3.5s-1.1-.3-3.6 1.4a12.3 12.3 0 0 0-6.5 0C6 2.2 4.9 2.5 4.9 2.5a4.7 4.7 0 0 0-.1 3.5A5 5 0 0 0 3.4 9.5c0 5 3.1 6.2 6 6.5a3.1 3.1 0 0 0-.9 2.4V22"/></svg>',
    "linkedin": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-4 0v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/></svg>',
    "scholar": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4 2 9.2l10 5.2 10-5.2z"/><path d="M6 11.4V16c0 1.7 2.7 3.1 6 3.1s6-1.4 6-3.1v-4.6"/></svg>',
    "download": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/></svg>',
    "link": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></svg>',
    "print": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9V3h12v6"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><path d="M6 14h12v7H6z"/></svg>',
    "sun": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
    "moon": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>',
    "arrow": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>',
    "menu": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>',
    "close": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>',
}


def icon(name: str) -> str:
    return ICONS.get(name, "")


def favicon(name: str) -> str:
    """Favicon with my initials, as an inline SVG data URI."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<rect width="64" height="64" rx="10" fill="%23f8f4e6"/>'
        '<rect x="4" y="4" width="56" height="56" rx="7" fill="none" '
        'stroke="%23b26a34" stroke-width="3"/>'
        '<text x="32" y="43" font-family="Outfit,Avenir,Helvetica,sans-serif" '
        f'font-size="28" font-weight="700" fill="%23b26a34" text-anchor="middle">'
        f'{initials_of(name)}</text></svg>'
    )
    return "data:image/svg+xml," + quote(svg, safe="%")


# --- CSS ---

def css() -> str:
    return """
/* --- colours, fonts, sizes --- */
:root {
  --beige-0:#f8f4e6; --beige-1:#f1ead5; --beige-2:#ece4ca; --beige-3:#ded4b2; --beige-4:#c6ba93;
  --gray-0:#fbfbfb; --gray-1:#eee; --gray-3:#d4d4d8; --gray-5:#a1a1a8; --gray-55:#5a5a61;
  --gray-6:#4e4e55; --gray-7:#323239; --gray-8:#28282e; --gray-9:#202025;
  --gray-10:#1d1d22; --gray-11:#16161a; --gray-12:#0d0d11;

  --radius: 8px;
  --transition: .15s ease;
  --sidebar-width: 260px;
  --content-width: 760px;
  --navbar-height: 60px;

  --font: 'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  --font-heading: 'Outfit', -apple-system, BlinkMacSystemFont, Avenir, Helvetica, Arial, sans-serif;
  --font-mono: 'JetBrains Mono', Menlo, Consolas, ui-monospace, monospace;
}

:root, :root[data-theme="light"] {
  color-scheme: light;
  --bg: var(--beige-0);
  --bg-sidebar: var(--beige-0);
  --bg-card: var(--beige-1);
  --bg-code: var(--beige-2);
  --bg-hover: var(--beige-2);
  --border: var(--beige-3);
  --border-strong: var(--beige-4);
  --text: var(--gray-7);
  --text-strong: var(--gray-8);
  --text-muted: var(--gray-55);
  --primary: #b26a34;
  --primary-contrast: #fff;
  --highlight: #ffce64;
  --shadow-card: 0 4px 4px rgba(198,186,147,.14), 0 2px 2px rgba(198,186,147,.14);
}

:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: var(--gray-11);
  --bg-sidebar: var(--gray-12);
  --bg-card: var(--gray-8);
  --bg-code: var(--gray-10);
  --bg-hover: var(--gray-9);
  --border: var(--gray-7);
  --border-strong: var(--gray-6);
  --text: var(--gray-3);
  --text-strong: var(--gray-0);
  --text-muted: var(--gray-5);
  --primary: #fede91;
  --primary-contrast: var(--gray-10);
  --highlight: #ffd479;
  --shadow-card: 0 4px 7px rgba(0,1,2,.3), 0 2px 2px rgba(0,1,2,.3);
}

/* --- base --- */
*, *::before, *::after { box-sizing: border-box; }
* { margin: 0; padding: 0; }

html { scroll-behavior: smooth; scroll-padding-top: calc(var(--navbar-height) + 16px); }

body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font);
  font-size: 1rem;
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
}

h1, h2, h3, h4 { font-family: var(--font-heading); color: var(--text-strong); line-height: 1.2; }
h1 { font-size: 2rem; font-weight: 700; letter-spacing: -.01em; }
h2 { font-size: 1.6rem; font-weight: 600; }
h3 { font-size: 1.15rem; font-weight: 600; }

a { color: var(--primary); text-decoration: none; }
a:hover { text-decoration: underline; text-underline-offset: 4px; text-decoration-thickness: 1px; }
p a { font-weight: 500; }

:focus-visible { outline: 2px solid var(--primary); outline-offset: 3px; border-radius: 4px; }
img { max-width: 100%; display: block; }
svg { width: 1em; height: 1em; fill: none; stroke: currentColor; stroke-width: 1.8;
      stroke-linecap: round; stroke-linejoin: round; }
::selection { background: var(--highlight); color: var(--gray-9); }
mark, .mark { background: var(--highlight); color: var(--gray-9); padding: 0 .2em; border-radius: 3px; }

.skip {
  position: fixed; left: 1rem; top: -4rem; z-index: 200; background: var(--bg-card);
  color: var(--text-strong); padding: .5rem 1rem; border: 1px solid var(--border);
  border-radius: var(--radius); transition: top var(--transition);
}
.skip:focus { top: 1rem; }

/* --- layout --- */
.layout {
  display: grid;
  grid-template-columns: var(--sidebar-width) minmax(0, 1fr);
  width: min(1060px, 100%);
  margin-inline: auto;
  align-items: start;
}

.sidebar {
  position: sticky; top: 0; height: 100vh; overflow-y: auto;
  display: flex; flex-direction: column; gap: 1.5rem;
  padding: 1.5rem 1.25rem;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border);
  scrollbar-width: thin;
}
.sidebar-top { display: flex; align-items: center; justify-content: space-between; gap: .5rem; }
.site-name {
  display: flex; align-items: center; gap: .5rem;
  font-family: var(--font-heading); font-weight: 600; font-size: .95rem;
  line-height: 1.25; color: var(--text-strong);
}
.site-name:hover { text-decoration: none; color: var(--primary); }
.avatar {
  width: 26px; height: 26px; min-width: 26px; border-radius: 50%;
  object-fit: cover; background: var(--bg-card); border: 1px solid var(--border);
}
.sidebar-bio { font-size: .92rem; color: var(--text-muted); }
.sidebar-bio strong { color: var(--text); font-weight: 600; }

.sidebar-label {
  font-family: var(--font-mono); font-size: .72rem; font-weight: 500;
  letter-spacing: .06em; text-transform: uppercase; color: var(--text-muted);
  margin-bottom: .5rem;
}
.nav-links { display: flex; flex-direction: column; gap: .15rem; }
.nav-links a {
  display: flex; align-items: center; gap: .55rem;
  color: var(--text); font-size: .97rem; padding: 4px .5rem;
  margin-inline: -.5rem; border-radius: var(--radius);
  transition: background var(--transition), color var(--transition);
}
.nav-links a:hover, .nav-links a.active { background: var(--bg-hover); color: var(--text-strong); text-decoration: none; }
.nav-links a.active { font-weight: 600; }
.nav-links .emoji { font-size: .95rem; line-height: 1; width: 1.15rem; text-align: center; }

/* sections of the current page */
.nav-sub {
  display: flex; flex-direction: column; gap: .1rem;
  margin: .2rem 0 .35rem 1.15rem; padding-left: .6rem;
  border-left: 1px solid var(--border);
}
.nav-sub a {
  font-size: .88rem; color: var(--text-muted); padding: 2px .45rem;
  border-radius: var(--radius); position: relative;
}
.nav-sub a:hover { color: var(--text-strong); text-decoration: none; background: var(--bg-hover); }
.nav-sub a.active { color: var(--primary); font-weight: 600; }
.nav-sub a.active::before {
  content: ''; position: absolute; left: calc(-.6rem - 1px); top: 4px; bottom: 4px;
  width: 2px; border-radius: 2px; background: var(--primary);
}

.sidebar-bottom { margin-top: auto; display: flex; flex-direction: column; gap: .9rem; }
.social { display: flex; gap: .35rem; }
.social a {
  display: grid; place-items: center; width: 32px; height: 32px;
  border-radius: var(--radius); color: var(--text-muted); font-size: 1.05rem;
  transition: background var(--transition), color var(--transition);
}
.social a:hover { background: var(--bg-hover); color: var(--primary); }
.sub-links {
  display: flex; flex-wrap: wrap; align-items: center; gap: .5rem;
  font-size: .82rem; color: var(--text-muted);
}
.sub-links a { color: var(--text-muted); }
.sub-links a:hover { color: var(--primary); }
.sub-links .divider { width: 1px; height: 11px; background: var(--border-strong); }

.icon-btn {
  display: grid; place-items: center; width: 32px; height: 32px; flex: none;
  border: 1px solid transparent; border-radius: var(--radius); background: none;
  color: var(--text-muted); cursor: pointer; font-size: 1rem;
  transition: background var(--transition), color var(--transition), border-color var(--transition);
}
.icon-btn:hover { background: var(--bg-hover); color: var(--primary); }
.theme-toggle .moon { display: none; }
[data-theme="dark"] .theme-toggle .moon { display: block; }
[data-theme="dark"] .theme-toggle .sun { display: none; }

/* mobile top bar */
.navbar {
  display: none; position: sticky; top: 0; z-index: 50;
  height: var(--navbar-height); align-items: center; justify-content: space-between;
  gap: .5rem; padding: 0 1.25rem;
  background: var(--bg); border-bottom: 1px solid var(--border);
}
.navbar-actions { display: flex; align-items: center; gap: .25rem; }
.mobile-menu { display: none; padding: .75rem 1.25rem 1.25rem; border-bottom: 1px solid var(--border); }
.mobile-menu.open { display: block; }
.mobile-menu .nav-links { gap: .25rem; }
.mobile-menu .social { margin-top: .75rem; padding-top: .75rem; border-top: 1px solid var(--border); }

main { padding: 2.75rem 2rem 4rem; max-width: calc(var(--content-width) + 4rem); }

/* --- hero --- */
.hero { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2.25rem; align-items: start; }
.hero h1 { display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; }
.hero-tagline { font-size: 1.15rem; color: var(--text-muted); margin-top: .35rem; }
.hero-note { font-size: 1rem; color: var(--text-muted); margin-top: 1.1rem; max-width: 60ch; }

.hero-side { display: flex; flex-direction: column; align-items: center; width: 250px; }
.hero-image {
  width: 200px; height: 200px; border-radius: 50%; object-fit: cover;
  border: 1px solid var(--border); background: var(--bg-card);
}
.hero-bubble {
  position: relative; margin-top: 1.25rem; max-width: 250px;
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: .6rem .9rem;
  font-size: .88rem; line-height: 1.5; text-align: center; color: var(--text);
}
.hero-bubble::before {
  content: ''; position: absolute; top: -7px; left: 50%;
  width: 12px; height: 12px; background: var(--bg-card);
  border-left: 1px solid var(--border); border-top: 1px solid var(--border);
  transform: translateX(-50%) rotate(45deg);
}
.hero-bubble a { font-family: var(--font-mono); font-weight: 600; font-size: .84rem; }

.intro p + p { margin-top: .8rem; }

/* era timeline */
.eras { list-style: none; margin: 0; max-width: 680px; font-size: 1.02rem; }
.eras li { display: flex; gap: .9rem; margin-bottom: .9rem; align-items: baseline; }
.era-dates {
  font-family: var(--font-mono); font-size: .78rem; color: var(--text-muted);
  min-width: 92px; width: 92px; flex: none; padding-top: .18rem;
}
.eras strong { color: var(--text-strong); font-weight: 600; }

/* --- section headings --- */
.heading { margin-bottom: 1.25rem; }
.heading-row { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
.heading h2 { margin-right: auto; }
.heading.small { margin-top: 1.75rem; margin-bottom: .9rem; }
.heading.small h2 { font-size: 1.3rem; }
.heading .description { color: var(--text-muted); font-size: 1.02rem; max-width: 65ch; margin-top: .35rem; }
/* offset lives on html only, putting it here too doubles it */
.section { margin-top: 3rem; }
.section:first-of-type { margin-top: 2.75rem; }

/* --- buttons and tags --- */
.button {
  display: inline-flex; align-items: center; gap: .4rem;
  background: transparent; border: 1.5px solid var(--primary); border-radius: var(--radius);
  color: var(--primary); font-family: var(--font); font-weight: 600; font-size: .95rem;
  padding: .4rem .85rem; cursor: pointer; white-space: nowrap;
  transition: background var(--transition), color var(--transition);
}
.button:hover { background: var(--primary); color: var(--primary-contrast); text-decoration: none; }
.button.small { font-size: .85rem; padding: .25rem .6rem; }
.button-meta { font-family: var(--font-mono); font-size: .72rem; font-weight: 400; opacity: .7; }
.downloads { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .9rem; }
.button.secondary { border-color: var(--border-strong); color: var(--text); }
.button.secondary:hover { background: var(--bg-hover); color: var(--text-strong); border-color: var(--border-strong); }

.tags { display: flex; flex-wrap: wrap; gap: .35rem; }
.tag {
  display: inline-flex; align-items: center; gap: 1px;
  border: 1.5px solid var(--border); border-radius: var(--radius);
  color: var(--text); font-family: var(--font-mono); font-size: .78rem; font-weight: 500;
  line-height: 1; padding: .25rem .5rem;
}
.tag::before { content: '#'; color: var(--primary); }
.tag.plain::before { content: none; }
.tag.solid { background: var(--bg-code); }

/* --- entry lists --- */
.entries { display: flex; flex-direction: column; }
.entry {
  display: block; padding: .85rem 0; border-bottom: 1px solid var(--border);
  color: inherit;
}
.entry:first-child { border-top: 1px solid var(--border); }
.entry:hover { text-decoration: none; }
/* grid, so a long title wraps without pushing the date down */
.entry-head { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: .25rem .75rem; align-items: baseline; }
.entry-title {
  font-family: var(--font-heading); font-size: 1.08rem; font-weight: 600;
  color: var(--text-strong); line-height: 1.3;
}
a.entry:hover .entry-title, .entry-title a:hover {
  text-decoration: underline; text-decoration-color: var(--primary);
  text-decoration-thickness: 1px; text-underline-offset: 4px;
}
.entry-date, .entry-side {
  font-family: var(--font-mono); font-size: .78rem; color: var(--text-muted);
  white-space: nowrap; flex: none;
}
.entry-meta { font-size: .92rem; color: var(--text-muted); margin-top: .2rem; }
.entry-meta .me { color: var(--text-strong); font-weight: 600; }
.entry-meta em { font-style: italic; }
.entry-foot { display: flex; flex-wrap: wrap; align-items: center; gap: .35rem; margin-top: .5rem; }
.entry-body { margin-top: .4rem; font-size: .96rem; }
.entry-body p + p, .entry-body p + ul { margin-top: .4rem; }

.bullets { list-style: none; margin: .35rem 0 0; padding-left: 1.05rem; font-size: .96rem; }
.bullets li { position: relative; margin-bottom: .2rem; }
.bullets > li::before {
  content: ''; position: absolute; left: -.95rem; top: .66em;
  width: 5px; height: 5px; border-radius: 50%; background: var(--border-strong);
}
.bullets ul { list-style: none; margin: .2rem 0 .35rem; padding-left: 1.05rem; }
.bullets ul li::before {
  content: ''; position: absolute; left: -.95rem; top: .7em;
  width: 6px; height: 1.5px; background: var(--border-strong);
}

/* dates in the left column (CV experience / education) */
.dated { display: grid; grid-template-columns: 118px minmax(0, 1fr); gap: .75rem 1.25rem; }
.dated + .dated { margin-top: 1.4rem; padding-top: 1.4rem; border-top: 1px solid var(--border); }
.dated-when { font-family: var(--font-mono); font-size: .78rem; color: var(--text-muted); padding-top: .3rem; }
.dated-title { font-family: var(--font-heading); font-size: 1.08rem; font-weight: 600; color: var(--text-strong); }
.dated-org { color: var(--primary); font-weight: 500; font-size: .95rem; }

/* --- cards and tiles --- */
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: .9rem; }
.card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1rem 1.1rem;
  box-shadow: var(--shadow-card);
}
.card h3 { font-size: 1.02rem; margin-bottom: .3rem; }
.card p { font-size: .93rem; color: var(--text-muted); }
.card .tags { margin-top: .7rem; }
a.card { display: block; color: inherit; }
a.card:hover { text-decoration: none; border-color: var(--primary); }
a.card:hover h3 { color: var(--primary); }

/* project tiles */
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; }
.tile {
  display: flex; flex-direction: column;
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1.25rem;
  box-shadow: var(--shadow-card);
  transition: border-color var(--transition), transform var(--transition);
}
.tile:hover { border-color: var(--primary); transform: translateY(-2px); }
.tile .kicker {
  font-family: var(--font-mono); font-size: .72rem; letter-spacing: .06em;
  text-transform: uppercase; color: var(--primary); margin-bottom: .45rem;
}
.tile h3 { font-size: 1.12rem; margin-bottom: .45rem; }
.tile p { font-size: .93rem; color: var(--text-muted); }
.tile .tile-foot {
  margin-top: auto; padding-top: .9rem;
  display: flex; flex-wrap: wrap; align-items: flex-end; gap: .5rem;
}
.tile .tags { flex: 1; }

.stat-line { font-family: var(--font-mono); font-size: .8rem; color: var(--text-muted); }

/* skills */
.skill-row { display: flex; align-items: center; gap: .6rem; margin-top: .4rem; }
.skill-name { font-size: .95rem; min-width: 108px; }
.meter { display: flex; gap: 3px; }
.meter i { width: 22px; height: 5px; border-radius: 2px; background: var(--border); }
.meter i.on { background: var(--primary); }

/* --- footer --- */
footer.site-footer {
  margin-top: 3.5rem; padding-top: 1.25rem; border-top: 1px solid var(--border);
  font-size: .85rem; color: var(--text-muted);
  display: flex; flex-wrap: wrap; gap: .5rem 1rem; justify-content: space-between;
}

/* --- responsive --- */
@media (max-width: 900px) {
  .layout { grid-template-columns: minmax(0, 1fr); }
  .sidebar { display: none; }
  .navbar { display: flex; }
  main { padding: 1.75rem 1.25rem 3rem; }
  .hero { grid-template-columns: minmax(0, 1fr); gap: 1.5rem; }
  .hero-side { flex-direction: row; align-items: flex-start; gap: 1rem; width: auto; }
  .hero-side .hero-bubble { margin-top: 0; }
  .hero-side .hero-bubble::before { top: 14px; left: -7px; transform: rotate(-45deg); }
  .hero-image { width: 132px; height: 132px; }
}
@media (max-width: 620px) {
  h1 { font-size: 1.7rem; }
  h2 { font-size: 1.35rem; }
  .eras li { flex-direction: column; gap: .1rem; }
  .era-dates { width: auto; padding-top: 0; }
  .dated { grid-template-columns: minmax(0, 1fr); gap: .2rem; }
  .dated-when { padding-top: 0; }
  .hero-side { flex-direction: column; }
  .hero-side .hero-bubble { margin-top: 1rem; }
  .hero-side .hero-bubble::before { top: -7px; left: 50%; transform: translateX(-50%) rotate(45deg); }
}
"""


def css_print() -> str:
    """Print styles. Has to come last to override the rules above."""
    return """
@media print {
  :root, :root[data-theme="dark"], :root[data-theme="light"] {
    --bg: #fff; --bg-sidebar: #fff; --bg-card: #fff; --bg-code: #fff; --bg-hover: #fff;
    --border: #d9d9d9; --border-strong: #bbb;
    --text: #1a1a1a; --text-strong: #000; --text-muted: #555;
    --primary: #7a4a1f; --highlight: #fff; --shadow-card: none;
  }
  body { font-size: 10pt; line-height: 1.45; background: #fff; }
  .sidebar, .navbar, .mobile-menu, .skip, .no-print { display: none !important; }
  .layout { display: block; width: 100%; }
  main { padding: 0; max-width: 100%; }
  h1 { font-size: 20pt; }
  h2 { font-size: 14pt; }
  .section { margin-top: 1.1rem; }
  .heading { margin-bottom: .6rem; }
  .entry { padding: .45rem 0; }
  .entry-title, .dated-title { font-size: 10.5pt; }
  .dated { grid-template-columns: 100px minmax(0, 1fr); }
  .dated + .dated { margin-top: .7rem; padding-top: .7rem; }
  .card { padding: .5rem .65rem; box-shadow: none; }
  .cards { gap: .5rem; }
  .entry, .card, .dated, .skill-row, .eras li { break-inside: avoid; page-break-inside: avoid; }
  .heading { break-after: avoid; page-break-after: avoid; }
  a { color: inherit; }
  footer.site-footer { margin-top: 1.2rem; }
}
"""


# --- JavaScript ---

THEME_BOOT = """<script>
(function () {
  try {
    var s = localStorage.getItem('theme');
    var d = window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.setAttribute('data-theme', s || (d ? 'dark' : 'light'));
  } catch (e) {}
})();
</script>"""

SITE_JS = """<script>
(function () {
  var root = document.documentElement;

  /* theme toggle */
  document.querySelectorAll('.theme-toggle').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('theme', next); } catch (e) {}
    });
  });
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
    var stored = null;
    try { stored = localStorage.getItem('theme'); } catch (err) {}
    if (!stored) root.setAttribute('data-theme', e.matches ? 'dark' : 'light');
  });

  /* mobile menu */
  var burger = document.querySelector('.menu-toggle');
  var menu = document.getElementById('mobile-menu');
  if (burger && menu) {
    burger.addEventListener('click', function () {
      var open = menu.classList.toggle('open');
      burger.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  /* highlight the section currently being read */
  var subLinks = document.querySelectorAll('.nav-sub a[href^="#"]');
  if (subLinks.length) {
    var byId = {}, ids = [];
    subLinks.forEach(function (a) {
      var id = a.getAttribute('href').slice(1);
      if (!document.getElementById(id)) return;
      if (!byId[id]) { byId[id] = []; ids.push(id); }
      byId[id].push(a);
    });

    var top = function (id) {
      return document.getElementById(id).getBoundingClientRect().top + window.scrollY;
    };

    /* Line moves down the viewport as you scroll. With a fixed line near the
       top the last sections never reach it - the page runs out of scroll
       first - and they end up sharing a few pixels between them. */
    var readingLine = function () {
      var y = window.scrollY;
      var max = document.documentElement.scrollHeight - window.innerHeight;
      if (max <= 0) return y + window.innerHeight;
      return y + window.innerHeight * Math.min(1, Math.max(0, y / max));
    };

    var pinned = null, pinSettled = false, settleTimer = null;
    var spy = function () {
      if (!ids.length) return;
      var current = pinned;
      if (!current || !byId[current]) {
        var line = readingLine();
        current = ids[0];
        ids.forEach(function (id) { if (top(id) <= line) current = id; });
      }
      subLinks.forEach(function (a) { a.classList.remove('active'); });
      byId[current].forEach(function (a) { a.classList.add('active'); });
    };

    /* Clicking a section pins it, so the nav shows where you asked to go
       until the page settles and you scroll again. */
    var pin = function (id) {
      if (!byId[id]) return;
      pinned = id;
      pinSettled = false;
      spy();
    };
    var releasePin = function () {
      if (!pinned) return;
      if (pinSettled) { pinned = null; return; }
      clearTimeout(settleTimer);
      settleTimer = setTimeout(function () { pinSettled = true; }, 200);
    };
    subLinks.forEach(function (a) {
      a.addEventListener('click', function () { pin(a.getAttribute('href').slice(1)); });
    });
    if (location.hash) { try { pin(decodeURIComponent(location.hash.slice(1))); } catch (e) {} }

    var queued = false;
    var onScroll = function () {
      releasePin();
      if (queued) return;
      queued = true;
      window.requestAnimationFrame(function () { queued = false; spy(); });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });
    window.addEventListener('hashchange', onScroll);
    // fonts and images shift everything once they load
    window.addEventListener('load', onScroll);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(onScroll);
    spy();

    /* The browser jumps to a #fragment before the fonts have loaded, and the
       reflow afterwards leaves it in the wrong spot. So jump again. */
    if (location.hash) {
      var target = null;
      try { target = document.getElementById(decodeURIComponent(location.hash.slice(1))); }
      catch (e) { target = null; }
      if (target) {
        var settled = null;
        var realign = function () {
          if (settled !== null && Math.abs(window.scrollY - settled) > 4) return;
          target.scrollIntoView({ behavior: 'auto', block: 'start' });
          settled = window.scrollY;
          spy();
        };
        window.addEventListener('load', realign);
        if (document.fonts && document.fonts.ready) document.fonts.ready.then(realign);
      }
    }
  }
})();
</script>"""


# --- Shared chrome ---

NAV_ITEMS = [
    ("index.html", "🏠", "Home", "home"),
    ("cv.html", "📄", "CV", "cv"),
    ("projects.html", "🌐", "Web Projects", "projects"),
]


def head_html(title: str, description: str, data: dict, url_path: str) -> str:
    site = data.get("website", "")
    canonical = f"https://{site}/{url_path}" if site else ""
    og = f'\n    <meta property="og:url" content="{canonical}">' if canonical else ""
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <meta name="description" content="{description}">
    <meta name="author" content="{data['name']}">
    <meta name="color-scheme" content="light dark">
    <meta property="og:type" content="website">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{description}">{og}
    <meta name="twitter:card" content="summary">
    <link rel="icon" href="{favicon(data['name'])}">
{FONT_LINKS}
    {THEME_BOOT}
    <style>{css()}{css_print()}    </style>
</head>
<body>
    <a class="skip" href="#main">Skip to content</a>
"""


def nav_links_html(active: str, sections=()) -> str:
    """Nav links. The current page gets its sections listed underneath."""
    out = ""
    for href, emoji, label, key in NAV_ITEMS:
        is_here = bool(key) and key == active
        cls = ' class="active"' if is_here else ""
        out += (f'                    <a href="{href}"{cls}>'
                f'<span class="emoji" aria-hidden="true">{emoji}</span>{label}</a>\n')
        if is_here and sections:
            out += '                    <nav class="nav-sub">\n'
            for slug, sub_label in sections:
                out += f'                        <a href="#{slug}">{sub_label}</a>\n'
            out += "                    </nav>\n"
    return out


def social_html(data: dict) -> str:
    out = ""
    if data.get("email"):
        out += (f'                    <a href="mailto:{data["email"]}" '
                f'aria-label="Email">{icon("mail")}</a>\n')
    for l in data.get("links", []):
        out += (f'                    <a href="{l["url"]}" target="_blank" rel="noopener" '
                f'aria-label="{l["name"]}">{icon(l.get("icon", "link"))}</a>\n')
    return out


def theme_button() -> str:
    return (f'<button class="icon-btn theme-toggle" type="button" '
            f'aria-label="Toggle colour theme">'
            f'<span class="sun">{icon("sun")}</span>'
            f'<span class="moon">{icon("moon")}</span></button>')


def display_name(data: dict) -> str:
    """Name with the title in front, as shown in the header."""
    return f"{data.get('title', '')} {data['name']}".strip()


def sidebar_html(data: dict, photo: dict, active: str, sections: list) -> str:
    """Sidebar: name, short bio, navigation, social links."""
    name = display_name(data)
    bio = data.get("sidebar_bio", "")
    return f"""    <aside class="sidebar">
        <div class="sidebar-top">
            <a class="site-name" href="index.html">
                <img class="avatar" src="{photo['png']}" alt="" aria-hidden="true" width="26" height="26">
                {name}
            </a>
            {theme_button()}
        </div>

        <p class="sidebar-bio">{bio}</p>

        <nav class="nav-links">
{nav_links_html(active, sections)}        </nav>

        <div class="sidebar-bottom">
            <nav class="social">
{social_html(data)}            </nav>
            <nav class="sub-links">
                <a href="cv.html">CV</a>
                <span class="divider"></span>
                <a href="cv.html#publications">Publications</a>
                <span class="divider"></span>
                <a href="cv.html#teaching">Teaching</a>
            </nav>
        </div>
    </aside>
"""


def navbar_html(data: dict, photo: dict, active: str, sections=()) -> str:
    """Top bar. Replaces the sidebar on small screens."""
    return f"""    <header class="navbar">
        <a class="site-name" href="index.html">
            <img class="avatar" src="{photo['png']}" alt="" aria-hidden="true" width="26" height="26">
            {display_name(data)}
        </a>
        <div class="navbar-actions">
            {theme_button()}
            <button class="icon-btn menu-toggle" type="button" aria-expanded="false"
                    aria-controls="mobile-menu" aria-label="Open menu">{icon('menu')}</button>
        </div>
    </header>
    <div class="mobile-menu" id="mobile-menu">
        <nav class="nav-links">
{nav_links_html(active, sections)}        </nav>
        <nav class="social">
{social_html(data)}        </nav>
    </div>
"""


def footer_html(data: dict) -> str:
    year = date.today().year
    return f"""        <footer class="site-footer">
            <span>&copy; {year} {data['name']}</span>
            <span>Last updated {date.today():%B %Y}</span>
        </footer>
    </main>
    </div>
{SITE_JS}
</body>
</html>
"""


def heading(title: str, anchor: str = "", action: str = "",
            description: str = "", small: bool = False) -> str:
    cls = "heading small" if small else "heading"
    aid = f' id="{anchor}"' if anchor else ""
    desc = f'<p class="description">{description}</p>' if description else ""
    return f"""            <header class="{cls}"{aid}>
                <div class="heading-row">
                    <h2>{title}</h2>
                    {action}
                </div>
                {desc}
            </header>
"""


def link_pills(links) -> str:
    """Row of small link buttons."""
    return "".join(
        f'<a class="button secondary small" href="{url}" target="_blank" rel="noopener">'
        f'{label}</a>'
        for label, url in links
    )


def publication_links(pub: dict) -> list:
    seen, out = set(), []
    for key in ("doi", "link"):
        url = clean_url(pub.get(key, ""))
        if url and url not in seen:
            seen.add(url)
            label = pub.get("link_text") if key == "link" and pub.get("link_text") else link_label(url)
            out.append((label, url))
    for pdf in pub.get("pdfs", []):
        out.append((pdf.get("name", "PDF"), pdf["file"]))
    return out


def entry_html(title: str, when: str, meta: str = "", kind: str = "",
               notes=(), links=(), body: str = "") -> str:
    """One row of an entry list.

    kind becomes a #tag, notes become plain pills, links become buttons.
    """
    foot = ""
    if kind:
        foot += f'<span class="tag">{kind}</span>'
    foot += "".join(f'<span class="tag plain solid">{n}</span>' for n in notes if n)
    foot += link_pills(links)
    return f"""                <article class="entry">
                    <div class="entry-head">
                        <h3 class="entry-title">{title}</h3>
                        <span class="entry-date">{when}</span>
                    </div>
                    {f'<p class="entry-meta">{meta}</p>' if meta else ''}
                    {f'<p class="entry-body">{body}</p>' if body else ''}
                    {f'<div class="entry-foot">{foot}</div>' if foot else ''}
                </article>
"""


def publication_entry(pub: dict, me, kind: str = "") -> str:
    """A publication row."""
    authors = highlight_author(pub.get("authors", "").rstrip(), me)
    venue = f' <em>{pub["journal"]}</em>.' if pub.get("journal") else ""
    stop = "" if pub.get("authors", "").rstrip().endswith(".") else "."
    # venue is already in the meta line, so only notes and links go below
    return entry_html(
        pub["title"], pub["year"], meta=f"{authors}{stop}{venue}", kind=kind,
        notes=as_list(pub.get("notes")), links=publication_links(pub),
    )


def parse_when(value) -> tuple:
    """Sort key from a date, e.g. '09/2024' -> (2024, 9).

    A bare year counts as mid-year so it mixes in with the dated entries of
    that same year instead of sorting above all of them.
    """
    text = str(value or "")
    dated = re.search(r"(\d{1,2})/(\d{4})", text)
    if dated:
        return int(dated.group(2)), int(dated.group(1))
    year = re.search(r"(\d{4})", text)
    return (int(year.group(1)), 6) if year else (0, 0)


# order within the same date
KIND_RANK = {"award": 0, "grant": 0, "talk": 1, "publication": 2}


def latest_feed(cv: dict, me, limit: int) -> str:
    """Publications, talks, awards and grants in one list, newest first."""
    items = []

    def add(when, kind, markup):
        items.append((parse_when(when), KIND_RANK.get(kind, 9), markup))

    for pub in cv.get("publications", []):
        add(pub.get("year"), "publication", publication_entry(pub, me, kind="publication"))

    for talk in cv.get("talks", []):
        location = f' &middot; {talk["location"]}' if talk.get("location") else ""
        add(talk.get("year"), "talk", entry_html(
            talk["title"], talk["year"], meta=f'{talk.get("event", "")}{location}',
            kind="talk", notes=as_list(talk.get("notes")),
        ))

    for award in cv.get("awards", []):
        add(award.get("year"), "award", entry_html(
            award["name"], award["year"], meta=award.get("organization", ""),
            kind="award", body=format_notes(award.get("notes")),
        ))

    for grant in cv.get("grants", []):
        amount = f' &middot; {grant["amount"]}' if grant.get("amount") else ""
        add(grant.get("year"), "grant", entry_html(
            grant.get("name", grant.get("title", "")), grant["year"],
            meta=f'{grant.get("funder", grant.get("organization", ""))}{amount}',
            kind="grant", body=format_notes(grant.get("notes")),
        ))

    # newest first, KIND_RANK breaks the ties
    items.sort(key=lambda item: (-item[0][0], -item[0][1], item[1]))
    return "".join(markup for _, _, markup in items[:limit])


def software_card(sw: dict) -> str:
    links = [(l["name"], l["url"]) for l in sw.get("links", [])]
    return f"""                <article class="card">
                    <h3>{sw['name']}</h3>
                    <p>{sw['type']} &middot; released {sw['year']}</p>
                    <div class="entry-foot">{link_pills(links)}</div>
                </article>
"""


# --- CV page ---

CV_SECTIONS = [
    ("experience", "Experience"),
    ("education", "Education"),
    ("skills", "Skills"),
    ("publications", "Publications"),
    ("talks", "Talks"),
    ("teaching", "Teaching"),
    ("supervision", "Supervision"),
    ("software", "Software"),
    ("awards", "Awards & Grants"),
    ("service", "Service"),
]


def generate_cv(data: dict, landing: dict, photo: dict) -> str:
    name = data["name"]
    full_title = f"{data.get('title', '')} {name}".strip()
    me = author_pattern(name)

    present = {
        "experience": data.get("experience"),
        "education": data.get("education"),
        "publications": data.get("publications"),
        "talks": data.get("talks"),
        "teaching": data.get("teaching"),
        "supervision": data.get("theses"),
        "software": data.get("software"),
        "awards": data.get("awards") or data.get("grants"),
        "service": data.get("service"),
        "skills": data.get("skills"),
    }
    toc = [(key, label) for key, label in CV_SECTIONS if present.get(key)]

    chrome = dict(landing)
    chrome.setdefault("name", name)

    # PDF versions to download
    downloads = [d for d in data.get("downloads", []) if d.get("file")]
    downloads_note, downloads_html = "", ""
    if downloads:
        buttons = ""
        for i, doc in enumerate(downloads):
            size = file_size(doc["file"])
            meta = f' <span class="button-meta">{size}</span>' if size else ""
            style = "button" if i == 0 else "button secondary"
            buttons += (f'                <a class="{style}" href="{doc["file"]}" download>'
                        f'{icon("download")} {doc.get("name", doc["file"])}{meta}</a>\n')
        downloads_note = " Prefer a PDF?"
        downloads_html = f'                <div class="downloads no-print">\n{buttons}                </div>\n'

    html = head_html(
        f"CV — {full_title}",
        f"Academic CV of {full_title}: {data.get('position', '')}. "
        "Publications, talks, teaching, software and service.",
        chrome, "cv.html",
    )
    html += f"""    <div class="layout">
{navbar_html(chrome, photo, 'cv', toc)}{sidebar_html(chrome, photo, 'cv', toc)}    <main id="main">
        <header class="hero">
            <div>
                <h1>Curriculum Vitae</h1>
                <p class="hero-tagline">{data.get('position', '')}</p>
                <p class="hero-note">Everything below is generated from a single JSON file, so it
                    stays current.{downloads_note}
                </p>
{downloads_html}
            </div>
        </header>
"""

    # Experience
    if present["experience"]:
        html += '        <section class="section" id="experience">\n'
        html += heading("Experience")
        for exp in data["experience"]:
            html += f"""            <div class="dated">
                <div class="dated-when">{exp['year']}</div>
                <div>
                    <div class="dated-title">{exp['position']}</div>
                    <div class="dated-org">{exp['organization']}</div>
                    <div class="entry-body">{format_description(exp.get('description'))}</div>
                </div>
            </div>
"""
        html += "        </section>\n"

    # Education
    if present["education"]:
        html += '        <section class="section" id="education">\n'
        html += heading("Education")
        for edu in data["education"]:
            notes = as_list(edu.get("notes"))
            body = ('<ul class="bullets">' + "".join(f"<li>{n}</li>" for n in notes) + "</ul>") if notes else ""
            html += f"""            <div class="dated">
                <div class="dated-when">{edu['year']}</div>
                <div>
                    <div class="dated-title">{edu['degree']}</div>
                    <div class="dated-org">{edu['institution']}</div>
                    <div class="entry-body">{body}</div>
                </div>
            </div>
"""
        html += "        </section>\n"

    # Skills
    if present["skills"]:
        html += '        <section class="section" id="skills">\n'
        html += heading("Skills")
        html += '            <div class="cards">\n'
        for group in data["skills"]:
            rows = ""
            for item in group["items"]:
                level = int(item.get("level", 0))
                meter = "".join(
                    '<i class="on"></i>' if k < level else "<i></i>" for k in range(5)
                )
                rows += f"""                    <div class="skill-row">
                        <span class="skill-name">{item['name']}</span>
                        <span class="meter" role="img" aria-label="{level} out of 5">{meter}</span>
                    </div>
"""
            html += f"""                <div class="card skill-group">
                    <h3>{group['category']}</h3>
{rows}                </div>
"""
        html += "            </div>\n        </section>\n"

    # Publications
    if present["publications"]:
        pubs = data["publications"]
        html += '        <section class="section" id="publications">\n'
        html += heading("Publications",
                        action=f'<span class="stat-line">{len(pubs)} total</span>')
        html += '            <div class="entries">\n'
        for pub in pubs:
            html += publication_entry(pub, me)
        html += "            </div>\n        </section>\n"

    # Talks
    if present["talks"]:
        html += '        <section class="section" id="talks">\n'
        html += heading("Talks & presentations",
                        action=f'<span class="stat-line">{len(data["talks"])} total</span>')
        html += '            <div class="entries">\n'
        for talk in data["talks"]:
            notes = format_notes(talk.get("notes"))
            note_html = f'<div class="entry-foot"><span class="tag plain solid">{notes}</span></div>' if notes else ""
            html += f"""                <article class="entry">
                    <div class="entry-head">
                        <h3 class="entry-title">{talk['title']}</h3>
                        <span class="entry-date">{talk['year']}</span>
                    </div>
                    <p class="entry-meta">{talk['event']} &middot; {talk['location']}</p>
                    {note_html}
                </article>
"""
        html += "            </div>\n        </section>\n"

    # Teaching
    if present["teaching"]:
        html += '        <section class="section" id="teaching">\n'
        html += heading("Teaching")
        html += '            <div class="entries">\n'
        for course in data["teaching"]:
            html += f"""                <article class="entry">
                    <div class="entry-head">
                        <h3 class="entry-title">{course['title']}</h3>
                        <span class="entry-side">{', '.join(course['semesters'])}</span>
                    </div>
                    <p class="entry-meta">{course['institution']} &middot; {course['type']}</p>
                </article>
"""
        html += "            </div>\n        </section>\n"

    # Supervision
    if present["supervision"]:
        html += '        <section class="section" id="supervision">\n'
        html += heading("Thesis supervision",
                        description="Master's and bachelor's theses I supervised or co-supervised.")
        html += '            <div class="entries">\n'
        for thesis in data["theses"]:
            html += f"""                <article class="entry">
                    <div class="entry-head">
                        <h3 class="entry-title">{thesis['title']}</h3>
                        <span class="entry-date">{thesis['year']}</span>
                    </div>
                    <p class="entry-meta">{thesis['student']} &middot; {thesis['level']} thesis</p>
                </article>
"""
        html += "            </div>\n        </section>\n"

    # Software
    if present["software"]:
        html += '        <section class="section" id="software">\n'
        html += heading("Software & data")
        html += '            <div class="cards">\n'
        for sw in data["software"]:
            html += software_card(sw)
        html += "            </div>\n        </section>\n"

    # Awards and grants
    if present["awards"]:
        awards, grants = data.get("awards", []), data.get("grants", [])
        # only label them when both kinds are in the list
        label = bool(awards and grants)
        rows = []
        for award in awards:
            rows.append((parse_when(award.get("year")), entry_html(
                award["name"], award["year"], meta=award.get("organization", ""),
                kind="award" if label else "", body=format_notes(award.get("notes")),
            )))
        for grant in grants:
            amount = f' &middot; {grant["amount"]}' if grant.get("amount") else ""
            rows.append((parse_when(grant.get("year")), entry_html(
                grant.get("name", grant.get("title", "")), grant["year"],
                meta=f'{grant.get("funder", grant.get("organization", ""))}{amount}',
                kind="grant" if label else "", body=format_notes(grant.get("notes")),
            )))
        rows.sort(key=lambda row: (-row[0][0], -row[0][1]))

        html += '        <section class="section" id="awards">\n'
        html += heading("Awards and Grants")
        html += '            <div class="entries">\n'
        html += "".join(markup for _, markup in rows)
        html += "            </div>\n        </section>\n"

    # Service
    if present["service"]:
        html += '        <section class="section" id="service">\n'
        html += heading("Contributions to the research community")
        html += '            <ul class="bullets" style="font-size:1rem">\n'
        for item in data["service"]:
            html += f"                <li>{item}</li>\n"
        html += "            </ul>\n        </section>\n"

    html += footer_html(chrome)
    return html


# --- Landing page ---

def generate_landing(data: dict, cv: dict, photo: dict) -> str:
    name = data["name"]
    first = name.split(" ")[0]
    me = author_pattern(name)

    # sections listed under Home in the sidebar
    home_sections = [("introduction", "Introduction")]
    if data.get("timeline"):
        home_sections.append(("timeline", "A brief timeline"))
    if data.get("research"):
        home_sections.append(("research", "What I work on"))
    if cv.get("publications") or cv.get("talks") or cv.get("awards") or cv.get("grants"):
        home_sections.append(("latest", "Latest"))
    if cv.get("software"):
        home_sections.append(("software", "Open Source Software"))
    home_sections.append(("contact", "Get in touch"))

    html = head_html(
        f"{data.get('title', '')} {name}".strip(),
        data.get("meta_description")
        or f"{name} — {data.get('position', '')}. Natural language processing, "
           "political narratives and AI for society.",
        data, "index.html",
    )
    html += f"""    <div class="layout">
{navbar_html(data, photo, 'home', home_sections)}{sidebar_html(data, photo, 'home', home_sections)}    <main id="main">
"""

    # hero: greeting, introduction, portrait
    bubble = data.get("bubble", "")
    bubble_html = f'<aside class="hero-bubble">{bubble}</aside>' if bubble else ""
    about = as_list(data.get("about")) or as_list(cv.get("summary"))
    intro_html = ""
    if about:
        paragraphs = "".join(f"                    <p>{p}</p>\n" for p in about)
        intro_html = (heading("Introduction", small=True)
                      + f'                <div class="intro">\n{paragraphs}                </div>\n')

    html += f"""        <header class="hero" id="introduction">
            <div>
                <h1>Hey, I'm Kai!</h1>
                <p class="hero-tagline">{data.get('tagline', '')}</p>
{intro_html}            </div>
            <div class="hero-side">
                {photo_html(photo, name, 'hero-image', '(max-width: 900px) 132px, 200px')}
                {bubble_html}
            </div>
        </header>
"""

    # timeline (most recent first)
    eras = data.get("timeline", [])
    if eras:
        html += '        <section class="section" id="timeline">\n'
        html += heading("A brief timeline")
        html += '            <ul class="eras">\n'
        for era in eras:
            html += (f'                <li><span class="era-dates">{era["dates"]}</span>'
                     f'<span>{era["text"]}</span></li>\n')
        html += "            </ul>\n"
        if data.get("also"):
            html += f'            <p class="hero-note">{data["also"]}</p>\n'
        html += "        </section>\n"

    # research
    research = data.get("research", [])
    if research:
        html += '        <section class="section" id="research">\n'
        html += heading("What I work on",
                        description=data.get("research_intro", ""))
        html += '            <div class="cards">\n'
        for item in research:
            html += f"""                <article class="card">
                    <h3>{item['title']}</h3>
                    <p>{item['text']}</p>
                </article>
"""
        html += "            </div>\n        </section>\n"

    # latest: publications, talks, awards and grants in one feed
    limit = data.get("featured_count", data.get("featured_publications", 6))
    feed = latest_feed(cv, me, limit)
    if feed:
        action = '<a class="button secondary small" href="cv.html#publications">All publications</a>'
        html += '        <section class="section" id="latest">\n'
        html += heading("Latest", action=action,
                        description="Recent papers, talks and distinctions.")
        html += f'            <div class="entries">\n{feed}            </div>\n        </section>\n'

    # software
    software = cv.get("software", [])
    if software:
        github = next((l["url"] for l in data.get("links", []) if l.get("icon") == "github"), "")
        action = (f'<a class="button secondary small" href="{github}" target="_blank" '
                  f'rel="noopener">GitHub</a>') if github else ""
        html += '        <section class="section" id="software">\n'
        html += heading("Open Source Software", action=action,
                        description="Libraries and corpora anyone can use.")
        html += '            <div class="cards">\n'
        for sw in software:
            html += software_card(sw)
        html += "            </div>\n        </section>\n"

    # contact
    email = data.get("email", "")
    html += '        <section class="section" id="contact">\n'
    html += heading("Get in touch")
    html += f"""            <p>{data.get('contact', '')}</p>
            <div class="entry-foot" style="margin-top:1rem">
                <a class="button" href="mailto:{email}">{icon('mail')} {email}</a>
"""
    for l in data.get("links", []):
        html += (f'                <a class="button secondary" href="{l["url"]}" target="_blank" '
                 f'rel="noopener">{icon(l.get("icon", "link"))} {l["name"]}</a>\n')
    html += "            </div>\n        </section>\n"

    html += footer_html(data)
    return html


# --- Entry point ---

def generate_projects(data: dict, chrome: dict, photo: dict) -> str:
    """Projects page: one group of tiles per section."""
    groups = [g for g in data.get("groups", []) if g.get("projects")]
    sections = [(g["id"], g["title"]) for g in groups]

    html = head_html(
        f"{data.get('title', 'Web Projects')} — {chrome['name']}",
        data.get("meta_description")
        or "Interactive teaching resources and research visualisations built by "
           f"{chrome['name']} - all running in the browser.",
        chrome, "projects.html",
    )
    html += f"""    <div class="layout">
{navbar_html(chrome, photo, 'projects', sections)}{sidebar_html(chrome, photo, 'projects', sections)}    <main id="main">
        <header class="hero">
            <div>
                <h1>{data.get('title', 'Web Projects')}</h1>
                <p class="hero-tagline">{data.get('tagline', '')}</p>
            </div>
        </header>
"""

    for group in groups:
        html += f'        <section class="section" id="{group["id"]}">\n'
        html += heading(group["title"], description=group.get("description", ""))
        html += '            <div class="tiles">\n'
        for project in group["projects"]:
            tags = "".join(f'<span class="tag">{t}</span>' for t in as_list(project.get("tags")))
            external = project["url"].startswith("http")
            attrs = ' target="_blank" rel="noopener"' if external else ""
            html += f"""                <article class="tile">
                    <div class="kicker">{project.get('kicker', '')}</div>
                    <h3>{project['name']}</h3>
                    <p>{project['description']}</p>
                    <div class="tile-foot">
                        <span class="tags">{tags}</span>
                        <a class="button small" href="{project['url']}"{attrs}>
                            Open {icon('arrow')}
                        </a>
                    </div>
                </article>
"""
        html += "            </div>\n        </section>\n"

    html += footer_html(chrome)
    return html


def main():
    root = Path(__file__).parent

    cv_data = load_json(root / "cv_data.json")
    landing_data = load_json(root / "landing_data.json")

    print("Preparing images...")
    photo = prepare_photo(root, landing_data.get("photo") or cv_data.get("photo", "portrait.png"))

    print("Generating cv.html...")
    (root / "cv.html").write_text(generate_cv(cv_data, landing_data, photo), encoding="utf-8")
    print("  -> cv.html")

    print("Generating index.html...")
    (root / "index.html").write_text(
        generate_landing(landing_data, cv_data, photo), encoding="utf-8"
    )
    print("  -> index.html")

    projects_json = root / "projects_data.json"
    if projects_json.exists():
        print("Generating projects.html...")
        (root / "projects.html").write_text(
            generate_projects(load_json(projects_json), landing_data, photo), encoding="utf-8"
        )
        print("  -> projects.html")

    print("Done!")


if __name__ == "__main__":
    main()
