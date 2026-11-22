from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    key: str
    bg: str
    panel: str
    panel_alt: str
    text: str
    muted: str
    accent: str
    accent_text: str
    border: str
    success: str
    danger: str
    warning: str


THEMES: dict[str, Theme] = {
    "dark": Theme("Dark", "dark", "#111111", "#1a1a1a", "#222222", "#f3f3f3", "#a0a0a0", "#ff6a00", "#111111", "#333333", "#4caf50", "#ff4d4d", "#ffb300"),
    "light": Theme("Light", "light", "#f5f5f5", "#ffffff", "#efefef", "#1a1a1a", "#555555", "#ff6a00", "#ffffff", "#d0d0d0", "#2e7d32", "#d32f2f", "#ef6c00"),
    "orange": Theme("Orange", "orange", "#17120f", "#211812", "#2b2018", "#fff3e8", "#d7b9a0", "#ff6a00", "#1a120c", "#4a3528", "#6fdc8c", "#ff5a5a", "#ffb74d"),
    "blue": Theme("Blue", "blue", "#0f141b", "#171e28", "#1d2633", "#eaf2ff", "#9fb3c8", "#4da3ff", "#0f141b", "#2e3d52", "#5bd6a0", "#ff6f6f", "#ffd166"),
    "purple": Theme("Purple", "purple", "#15101b", "#1d1627", "#261c33", "#f3ecff", "#b8a6d6", "#b06cff", "#15101b", "#3d2d52", "#6fdc8c", "#ff6f8d", "#ffd166"),
    "green": Theme("Green", "green", "#101612", "#17201a", "#1e2921", "#ecfff1", "#a6c4ae", "#54d686", "#101612", "#2e4335", "#54d686", "#ff6f6f", "#ffd166"),
    "red": Theme("Red", "red", "#1a1111", "#241717", "#2f1d1d", "#fff0f0", "#d3aaaa", "#ff5f5f", "#1a1111", "#523030", "#6fdc8c", "#ff5f5f", "#ffb74d"),
    "mono": Theme("Monochrome", "mono", "#111111", "#1b1b1b", "#242424", "#f0f0f0", "#b0b0b0", "#ffffff", "#111111", "#444444", "#d0d0d0", "#ffffff", "#d0d0d0"),
}

THEME_ORDER = ["auto", "dark", "light", "orange", "blue", "purple", "green", "red", "mono"]


def resolve_theme(key: str, system_dark: bool = True) -> Theme:
    if key == "auto":
        return THEMES["dark"] if system_dark else THEMES["light"]
    return THEMES.get(key, THEMES["dark"])


def theme_css(theme: Theme) -> str:
    return f"""
Screen {{
  background: {theme.bg};
  color: {theme.text};
}}
#main-panel, .panel, ModalScreen > .dialog {{
  background: {theme.panel};
  border: solid {theme.border};
}}
Button {{
  background: {theme.panel_alt};
  color: {theme.text};
  border: solid {theme.border};
}}
Button:hover {{
  border: solid {theme.accent};
  color: {theme.accent};
}}
Button.-primary {{
  background: {theme.accent};
  color: {theme.accent_text};
  border: solid {theme.accent};
}}
Button.-danger {{
  background: {theme.panel_alt};
  color: {theme.danger};
  border: solid {theme.danger};
}}
Button.-danger:hover {{
  background: {theme.danger};
  color: white;
}}
.accent {{ color: {theme.accent}; }}
.muted {{ color: {theme.muted}; }}
"""
