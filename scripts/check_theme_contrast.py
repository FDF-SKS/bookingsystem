#!/usr/bin/env python3
"""Scan rendered pages for WCAG text-contrast violations in light and dark mode.

This uses a real (headless) browser so it sees the *computed* styles after the
``data-bs-theme`` bootstrap and ``custom.css`` overrides are applied — which a
pure Django/HTML test cannot do.

Requirements
------------
- Playwright + a browser::

    pip install playwright
    playwright install chromium

Usage
-----
::

    python scripts/check_theme_contrast.py [BASE_URL] [ROUTE ...]

Defaults to the public pages of the production site. Add ``--username`` /
``--password`` to log in first and scan authenticated pages too.

Exit code is 1 if any text fails the WCAG AA threshold (4.5:1 for normal text,
3:1 for large text).
"""
from __future__ import annotations

import argparse
import json
import sys

from playwright.sync_api import sync_playwright

NORMAL_MIN_RATIO = 4.5
LARGE_TEXT_MIN_RATIO = 3.0

DEFAULT_ROUTES = [
    "/",
    "/organization/login_user",
    "/organization/register_user",
    "/organization/password-reset",
]

# JS that walks every visible text node and computes its effective background
# (walking up past transparent ancestors) and the resulting contrast ratio.
CONTRAST_JS = """
() => {
  function parseColor(color) {
    const m = color.match(/rgba?\\(([^)]+)\\)/);
    if (!m) return null;
    const parts = m[1].split(',').map(s => parseFloat(s.trim()));
    return [parts[0], parts[1], parts[2], parts.length > 3 ? parts[3] : 1];
  }
  function luminance(r, g, b) {
    const f = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  }
  function ratio(fg, bg) {
    const l1 = luminance(fg[0], fg[1], fg[2]);
    const l2 = luminance(bg[0], bg[1], bg[2]);
    const lighter = Math.max(l1, l2), darker = Math.min(l1, l2);
    return (lighter + 0.05) / (darker + 0.05);
  }
  function composite(over, under) {
    const a = over[3];
    return [
      Math.round(over[0] * a + under[0] * (1 - a)),
      Math.round(over[1] * a + under[1] * (1 - a)),
      Math.round(over[2] * a + under[2] * (1 - a)),
    ];
  }
  function effectiveBg(node) {
    const layers = [];
    let el = node;
    while (el && el !== document.documentElement) {
      const bg = parseColor(getComputedStyle(el).backgroundColor);
      if (bg && bg[3] > 0.001) layers.push(bg);
      el = el.parentElement;
    }
    let acc = [255, 255, 255];
    for (let i = layers.length - 1; i >= 0; i--) {
      const layer = layers[i];
      acc = layer[3] >= 1 ? [layer[0], layer[1], layer[2]] : composite(layer, acc);
    }
    return acc;
  }
  function selector(el) {
    if (el.id) return '#' + el.id;
    let s = el.tagName.toLowerCase();
    if (el.className && typeof el.className === 'string') {
      s += '.' + el.className.trim().split(/\\s+/).slice(0, 3).join('.');
    }
    return s;
  }

  const out = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const text = node.textContent.replace(/\\s+/g, ' ').trim();
    if (!text || text.length < 2) continue;
    const el = node.parentElement;
    if (!el) continue;
    const style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
    let fg = parseColor(style.color);
    if (!fg || fg[3] <= 0.001) continue;
    const bg = effectiveBg(el);
    if (fg[3] < 1) fg = composite(fg, bg);
    const r = ratio(fg, bg);
    const size = parseFloat(style.fontSize);
    const weight = parseInt(style.fontWeight || '400', 10);
    const isLarge = size >= 24 || (size >= 18.66 && weight >= 700);
    const threshold = isLarge ? 3.0 : 4.5;
    if (r < threshold) {
      out.push({
        text: text.slice(0, 80),
        selector: selector(el),
        fg: 'rgb(' + fg.slice(0,3).join(',') + ')',
        bg: 'rgb(' + bg.join(',') + ')',
        ratio: Number(r.toFixed(2)),
        threshold,
        fontSize: style.fontSize,
        fontWeight: style.fontWeight,
      });
    }
  }
  return out;
}
"""


def scan_page(page, base_url, route, theme):
    url = base_url.rstrip("/") + route
    page.goto(url, wait_until="load", timeout=60000)

    # Force the theme via the same storage key the app uses, then reload so the
    # bootstrap script applies it before paint.
    page.evaluate(f"localStorage.setItem('site-theme', {json.dumps(theme)})")
    page.reload(wait_until="load", timeout=60000)
    page.wait_for_timeout(1200)

    return page.evaluate(CONTRAST_JS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", nargs="?", default="https://booking.seniorkursussletten.dk")
    parser.add_argument("routes", nargs="*", default=DEFAULT_ROUTES)
    parser.add_argument("--username")
    parser.add_argument("--password")
    args = parser.parse_args()

    failures = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        if args.username and args.password:
            # Log in once so authenticated routes can be scanned.
            page.goto(args.base_url.rstrip("/") + "/organization/login_user", wait_until="load")
            page.fill('input[name="login"]', args.username)
            page.fill('input[name="password"]', args.password)
            page.click('button[type="submit"]')
            page.wait_for_load_state("load")

        for route in args.routes:
            for theme in ("light", "dark"):
                violations = scan_page(page, args.base_url, route, theme)
                if violations:
                    print(f"\n=== {theme:5s} {route} ({len(violations)} issues) ===")
                    for v in violations:
                        failures += 1
                        print(
                            f"  ratio {v['ratio']:.2f} (needs {v['threshold']}) "
                            f"fg={v['fg']} bg={v['bg']} {v['selector']} "
                            f"[{v['fontSize']}/{v['fontWeight']}]\n    {v['text']!r}"
                        )

        context.close()
        browser.close()

    if failures:
        print(f"\n{ failures } contrast violations found.")
        return 1
    print("\nNo WCAG AA contrast violations found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
