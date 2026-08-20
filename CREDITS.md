# Credits

## Original concept

The neofetch-style profile README — an ASCII portrait beside a dot-leadered
panel of live GitHub statistics, rendered as a theme-aware SVG and refreshed by
a scheduled Action — is **Andrew Grant's** design.

- Author: Andrew Grant ([@Andrew6rant](https://github.com/Andrew6rant))
- Original: <https://github.com/Andrew6rant/Andrew6rant>

This repository is an independent reimplementation of that idea, not a fork.
The layout, the framing of the stats, and the `<picture>`-based light/dark
switch all follow Andrew's original; the code here was written from scratch and
shares no source with it. Check the original repository for its licence terms
before reusing anything from it directly.

## This implementation

- `render.py` — SVG layout and the terminal-style colour palettes
- `today.py` — GitHub GraphQL queries, uptime, LOC accounting
- `ascii_art.py` — photo-to-ASCII converter (unused if you supply your own art)
