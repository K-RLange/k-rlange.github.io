# krlange.de

Personal website of Dr. Kai-Robin Lange — a static site hosted on GitHub Pages.

## Building

Everything on the site is generated from two JSON files:

| File | Feeds |
| --- | --- |
| `cv_data.json` | `cv.html` — and the stats, selected publications and software cards on the landing page |
| `landing_data.json` | `index.html` — hero, about, research focus, contact |

Edit the JSON, then regenerate:

```bash
python generate_cv.py
```

This writes `index.html`, `cv.html` and web-sized portraits into `assets/`.
Commit all of them — GitHub Pages serves the generated files directly.

### Requirements

- Python 3.9+
- [Pillow](https://pypi.org/project/Pillow/) (optional): downsizes `portrait.png` into the
  WebP/PNG derivatives in `assets/`. Without it the site falls back to the full-size
  original, which is much slower to load. Derivatives are rebuilt only when
  `portrait.png` changes.

## Notes

- The design adapts to the visitor's light/dark preference and remembers the toggle.
- `cv.html` has a print stylesheet, so "Print / save as PDF" produces a clean CV.
