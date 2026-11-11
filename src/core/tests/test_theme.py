"""Tests for the light/dark theme readability and wiring.

These guard the two things that regress most often with theming:

1. Contrast: the palette's body/muted/primary colors must meet WCAG AA
   (4.5:1) against the page background in both themes.
2. Wiring: fixed-color Bootstrap utilities that would otherwise ignore
   ``data-bs-theme`` have dark-mode overrides, and the base template still
   ships the bootstrap script + ``theme-toggle.js``.
"""
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

CSS_PATH = Path(settings.BASE_DIR) / "static" / "css" / "custom.css"
BASE_TEMPLATE = Path(settings.BASE_DIR) / "templates" / "base.html"


def _luminance(hex_color: str) -> float:
    hex_color = hex_color.strip().lstrip("#")
    r = int(hex_color[0:2], 16) / 255
    g = int(hex_color[2:4], 16) / 255
    b = int(hex_color[4:6], 16) / 255

    def linear(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = linear(r), linear(g), linear(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def wcag_contrast(foreground: str, background: str) -> float:
    fg = _luminance(foreground)
    bg = _luminance(background)
    lighter, darker = (fg, bg) if fg > bg else (bg, fg)
    return (lighter + 0.05) / (darker + 0.05)


def _extract_hex_vars(block_text: str) -> dict[str, str]:
    variables = {}
    for name in (
        "--bs-body-bg",
        "--bs-body-color",
        "--bs-muted",
        "--bs-primary",
        "--bs-tertiary",
    ):
        match = re.search(rf"{re.escape(name)}\s*:\s*([^;]+);", block_text)
        if match:
            value = match.group(1).strip()
            if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                variables[name] = value
    return variables


def _theme_palettes() -> tuple[dict[str, str], dict[str, str]]:
    css = CSS_PATH.read_text()
    light_match = re.search(r":root\s*\{([^}]*)\}", css)
    dark_match = re.search(r':root\[data-bs-theme="dark"\]\s*\{([^}]*)\}', css)

    light = _extract_hex_vars(light_match.group(1)) if light_match else {}
    dark = _extract_hex_vars(dark_match.group(1)) if dark_match else {}
    # Undefined dark values inherit the light value (e.g. --bs-muted before it
    # was overridden), which is exactly what the CSS cascade does.
    return light, {**light, **dark}


class ThemeContrastTests(SimpleTestCase):
    def test_palette_meets_wcag_aa_contrast(self):
        light, dark = _theme_palettes()

        for label, palette in (("light", light), ("dark", dark)):
            body_bg = palette["--bs-body-bg"]

            pairs = {
                "body text": palette["--bs-body-color"],
                "muted text": palette["--bs-muted"],
                "primary (links/headings)": palette["--bs-primary"],
            }
            for description, foreground in pairs.items():
                ratio = wcag_contrast(foreground, body_bg)
                self.assertGreaterEqual(
                    ratio,
                    4.5,
                    f"{label}: {description} ({foreground} on {body_bg}) has "
                    f"contrast {ratio:.2f}, below WCAG AA 4.5",
                )


class ThemeDarkOverrideTests(SimpleTestCase):
    def test_fixed_color_utilities_have_dark_overrides(self):
        css = CSS_PATH.read_text()

        for selector in (".bg-white", ".text-dark", ".text-secondary"):
            self.assertIn(
                f'[data-bs-theme="dark"] {selector}',
                css,
                f"Missing dark-mode override for {selector}",
            )

    def test_colored_badges_keep_dark_text(self):
        css = CSS_PATH.read_text()
        self.assertIn(
            '[data-bs-theme="dark"] .badge.bg-warning.text-dark', css
        )
        self.assertIn(
            '[data-bs-theme="dark"] .badge.bg-info.text-dark', css
        )

    def test_dark_muted_is_defined(self):
        css = CSS_PATH.read_text()
        self.assertIn("--bs-muted: #9aa5ad", css)

    def test_button_text_colors_swap_in_dark_mode(self):
        css = CSS_PATH.read_text()
        # Light: orange secondary button uses navy text.
        self.assertIn("--bs-btn-color: #003255", css)
        # Dark: orange primary button uses navy text, navy secondary uses white.
        self.assertIn('[data-bs-theme="dark"] .btn-primary', css)
        self.assertIn('[data-bs-theme="dark"] .btn-secondary', css)
        # Light: secondary text is a darker, readable orange.
        self.assertIn(".text-secondary { color: #c2410c", css)


class ThemeWiringTests(TestCase):
    def test_login_page_includes_theme_bootstrap_and_toggle(self):
        response = self.client.get(reverse("account_login"))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode()
        self.assertIn("/static/js/theme-toggle.js", content)
        self.assertIn("data-bs-theme", content)
