"""Build the README badges as local SVGs (for-the-badge style), so the profile
never depends on a badge service being up.

    python3 scripts/badges.py

Logos: Simple Icons (CC0) and GitHub Octicons (MIT), fetched at build time.
"""
import os
import re
import urllib.request

OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "badges")
SI = "https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/{}.svg"
OCTICON = "https://raw.githubusercontent.com/primer/octicons/main/icons/{}-16.svg"

# (file, label, background, icon source or None)
BADGES = [
    # contact
    ("portfolio", "Portfolio", "1F2328", ("oct", "globe")),
    ("linkedin", "LinkedIn", "0A66C2", None),
    ("email", "Email", "1F2328", ("oct", "mail")),
    # stack, straight from the résumé
    ("python", "Python", "3776AB", ("si", "python")),
    ("fastapi", "FastAPI", "009688", ("si", "fastapi")),
    ("langgraph", "LangGraph", "1C3C3C", ("si", "langchain")),
    ("mcp", "MCP", "111111", ("si", "modelcontextprotocol")),
    ("scikit-learn", "scikit-learn", "F7931E", ("si", "scikitlearn")),
    ("pandas", "Pandas", "150458", ("si", "pandas")),
    ("postgresql", "PostgreSQL", "4169E1", ("si", "postgresql")),
    ("sqlite", "SQLite", "003B57", ("si", "sqlite")),
    ("docker", "Docker", "2496ED", ("si", "docker")),
    ("pytest", "pytest", "0A9EDC", ("si", "pytest")),
    ("google-cloud", "Google Cloud", "4285F4", ("si", "googlecloud")),
    ("nextjs", "Next.js", "000000", ("si", "nextdotjs")),
]

# Rough Verdana Bold advance widths at 10px; textLength pins the final width anyway.
NARROW = set("IJ1.,:;'!|ijlft")
WIDE = set("MW@")


def text_width(s):
    w = 0.0
    for ch in s:
        if ch == " ":
            w += 3.6
        elif ch in NARROW:
            w += 4.2
        elif ch in WIDE:
            w += 9.8
        else:
            w += 7.3
    return w + 1.25 * (len(s) - 1)


def fetch_icon(src):
    kind, name = src
    url = (SI if kind == "si" else OCTICON).format(name)
    svg = urllib.request.urlopen(url, timeout=20).read().decode()
    box = re.search(r'viewBox="([^"]+)"', svg).group(1)
    paths = "".join(re.findall(r"<path[^>]*/>", svg))
    paths = re.sub(r'\s(fill|fill-rule|clip-rule)="[^"]*"', "", paths)
    return box, paths


def text_color(hex6):
    r, g, b = (int(hex6[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#1F2328" if lum > 0.6 else "#FFFFFF"


def build(name, label, bg, icon):
    label = label.upper()
    fg = text_color(bg)
    pad, h = 12, 28
    x = pad
    logo = ""
    if icon:
        box, paths = fetch_icon(icon)
        logo = (f'<svg x="{pad}" y="7" width="14" height="14" viewBox="{box}" fill="{fg}">{paths}</svg>')
        x = pad + 14 + 8
    tw = text_width(label)
    w = round(x + tw + pad)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{label}">'
        f"<title>{label}</title>"
        f'<rect width="{w}" height="{h}" rx="3" fill="#{bg}"/>{logo}'
        f'<text x="{x}" y="18" fill="{fg}" font-family="Verdana,\'DejaVu Sans\',Geneva,sans-serif" font-size="10" '
        f'font-weight="700" textLength="{tw:.1f}" lengthAdjust="spacingAndGlyphs">{label}</text></svg>\n'
    )
    with open(os.path.join(OUT, f"{name}.svg"), "w") as f:
        f.write(svg)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for b in BADGES:
        build(*b)
        print("built", b[0])
