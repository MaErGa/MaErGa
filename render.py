#!/usr/bin/env python3
"""SVG layout for the profile panel.

Rows are built as lists of (text, colour-role) tokens; this module turns them
into a monospace SVG. Nothing here is positioned per-character - each row is a
single <text> with xml:space="preserve" and flowing <tspan>s, so alignment is
carried by the dot leaders and holds for whatever monospace font the viewer
happens to have.

Layout and concept after Andrew Grant (@Andrew6rant); see CREDITS.md.
"""

from xml.sax.saxutils import escape

FONT_SIZE = 14
CHAR_W = 8.4          # approximate advance width of a 14px monospace cell
LINE_H = 16
PAD = 20
GUTTER = 64
# Slack on the right edge: CHAR_W is the 0.6em advance of a typical monospace
# font, but the viewer's fallback font may be a shade wider. A little unused
# canvas is invisible; a clipped last column is not.
SLACK = 24

# Terminal-style palette. The discipline here is a real shell's: one accent
# colour for keys, plain foreground for values, and hierarchy carried by
# brightness rather than by adding more hues. Green for the user@host line is
# the shell-prompt convention; green/red on the stat counts is the diff
# convention. Everything else is foreground or dim.
PALETTES = {
    "dark": {
        "bg": "#0d1117", "border": "#30363d",
        "title": "#98c379",     # prompt green - user@host
        "section": "#e6edf3",   # bright white, i.e. a terminal's "bold"
        "rule": "#3e4451",      # dim
        "key": "#56b6c2",       # accent cyan - neofetch's key colour
        "value": "#abb2bf",     # plain stdout
        "dots": "#3e4451",      # dim
        "add": "#98c379", "del": "#e06c75", "num": "#abb2bf",
        "ascii": "#8b949e",
    },
    "light": {
        "bg": "#ffffff", "border": "#d0d7de",
        "title": "#2f7d32",
        "section": "#1f2328",
        "rule": "#d0d7de",
        "key": "#0b7285",
        "value": "#3b4252",
        "dots": "#d0d7de",
        "add": "#1a7f37", "del": "#cf222e", "num": "#3b4252",
        "ascii": "#57606a",
    },
}

# Roles a terminal would render with the bold attribute.
BOLD = {"title", "section"}

FONT_STACK = ("ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, "
              "'DejaVu Sans Mono', monospace")


def justify(label, value, width):
    """`- Label: ..... value` padded so the value ends at column `width`."""
    left = f"- {label}:"
    gap = width - len(left) - len(value) - 2
    dots = "." * max(gap, 1)
    return [(left, "key"), (f" {dots} ", "dots"), (value, "value")]


def section(title, width):
    """`- Title ------------------------` filling the panel width."""
    head = f"- {title} "
    return [(head, "section"), ("-" * max(width - len(head), 1), "rule")]


def _row_svg(x, y, tokens, palette):
    spans = "".join(
        f'<tspan fill="{palette[role]}"'
        f'{" font-weight=\"600\"" if role in BOLD else ""}>'
        f'{escape(text)}</tspan>'
        for text, role in tokens if text
    )
    return (f'<text x="{x}" y="{y:.0f}" xml:space="preserve">{spans}</text>')


def build_svg(ascii_lines, rows, theme, ascii_cols, panel_cols):
    palette = PALETTES[theme]

    x_ascii = PAD
    x_panel = PAD + ascii_cols * CHAR_W + GUTTER
    width = round(x_panel + panel_cols * CHAR_W + PAD + SLACK)
    n = max(len(ascii_lines), len(rows))
    # Centre the shorter of the two columns against the taller one, so a tall
    # portrait does not leave the panel stranded at the top.
    art_top = (n - len(ascii_lines)) // 2
    panel_top = (n - len(rows)) // 2
    height = round(PAD * 2 + n * LINE_H)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" '
        f'font-family="{FONT_STACK}" font-size="{FONT_SIZE}">',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" '
        f'rx="8" fill="{palette["bg"]}" stroke="{palette["border"]}"/>',
    ]

    baseline = PAD + FONT_SIZE
    for i, line in enumerate(ascii_lines):
        out.append(_row_svg(x_ascii, baseline + (art_top + i) * LINE_H,
                            [(line, "ascii")], palette))
    for i, tokens in enumerate(rows):
        out.append(_row_svg(round(x_panel), baseline + (panel_top + i) * LINE_H,
                            tokens, palette))

    out.append("</svg>")
    return "\n".join(out) + "\n"
