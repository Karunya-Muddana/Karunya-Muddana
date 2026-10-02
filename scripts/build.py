"""Build every image the profile README uses, in a light and a dark version.

    pip install fonttools brotli
    python3 scripts/build.py

Fonts (Mona Sans, Monaspace Neon; SIL OFL) are subset and embedded in each SVG, so the
images look the same everywhere and load nothing at render time. Icons come from GitHub
Octicons (MIT) and Simple Icons (CC0). Sources are downloaded once into .cache/.
"""
import ast
import base64
import datetime as dt
import io
import os
import re
import subprocess
import urllib.request
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "assets")
CACHE = os.path.join(ROOT, ".cache")
RAW = "https://raw.githubusercontent.com/"

FONT_SRC = {
    "sans-400": "github/mona-sans/main/fonts/static/ttf/MonaSans-Regular.ttf",
    "sans-500": "github/mona-sans/main/fonts/static/ttf/MonaSans-Medium.ttf",
    "sans-600": "github/mona-sans/main/fonts/static/ttf/MonaSans-SemiBold.ttf",
    "sans-700": "github/mona-sans/main/fonts/static/ttf/MonaSans-Bold.ttf",
    "mono-400": "githubnext/monaspace/main/fonts/Web%20Fonts/Static%20Web%20Fonts/Monaspace%20Neon/MonaspaceNeon-Regular.woff2",
}

# GitHub Primer colours
THEMES = {
    "dark": dict(canvas="#0d1117", panel="#151b23", border="#3d444d", fg="#f0f6fc", muted="#9198a1",
                 subtle="#656c76", green="#3fb950", greenBg="#2ea04326", blue="#4493f8", blueBg="#388bfd26",
                 orange="#f0883e", red="#f85149", redBg="#f8514926", hi="#388bfd1f"),
    "light": dict(canvas="#ffffff", panel="#f6f8fa", border="#d1d9e0", fg="#1f2328", muted="#59636e",
                  subtle="#818b98", green="#1a7f37", greenBg="#1a7f371f", blue="#0969da", blueBg="#0969da1a",
                  orange="#bc4c00", red="#d1242f", redBg="#d1242f1a", hi="#0969da14"),
}
LANG = {"Python": "#3572A5", "TypeScript": "#3178c6"}


def cached(path):
    local = os.path.join(CACHE, path.replace("/", "_").replace("%20", "_"))
    if not os.path.exists(local):
        os.makedirs(CACHE, exist_ok=True)
        with urllib.request.urlopen(RAW + path, timeout=30) as r, open(local, "wb") as f:
            f.write(r.read())
    return local


FONTS = {k: TTFont(cached(v)) for k, v in FONT_SRC.items()}


def measure(text, font, size, spacing=0.0):
    f = FONTS[font]
    cmap, hmtx, upm = f.getBestCmap(), f["hmtx"], f["head"].unitsPerEm
    w = sum(hmtx[cmap.get(ord(c), cmap[ord("?")])][0] for c in text)
    return w * size / upm + spacing * max(len(text) - 1, 0)


def icon(kind, name):
    path = (f"primer/octicons/main/icons/{name}-16.svg" if kind == "oct"
            else f"simple-icons/simple-icons/develop/icons/{name}.svg")
    svg = open(cached(path)).read()
    box = re.search(r'viewBox="([^"]+)"', svg).group(1)
    paths = "".join(re.findall(r"<path[^>]*/>", svg))
    return box, re.sub(r'\s(fill|fill-rule|clip-rule)="[^"]*"', "", paths)


class Svg:
    def __init__(self, w, h, theme):
        self.w, self.h, self.t = w, h, THEMES[theme]
        self.parts, self.css, self.used = [], [], {}

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, font="sans-400", size=14, fill="fg", anchor="start", spacing=0.0, cls="", extra=""):
        self.used.setdefault(font, set()).update(s)
        fam, wt = font.split("-")
        fill = self.t.get(fill, fill)
        ls = f' letter-spacing="{spacing}"' if spacing else ""
        c = f' class="{cls}"' if cls else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{fam}" font-weight="{wt}" font-size="{size}" '
                 f'fill="{fill}" text-anchor="{anchor}"{ls}{c}{extra}>{escape(s)}</text>')
        return measure(s, font, size, spacing)

    def icon(self, kind, name, x, y, size=16, fill="muted", cls=""):
        box, paths = icon(kind, name)
        c = f' class="{cls}"' if cls else ""
        self.add(f'<svg x="{x:.1f}" y="{y:.1f}" width="{size}" height="{size}" viewBox="{box}" fill="{self.t.get(fill, fill)}"{c}>{paths}</svg>')

    def rect(self, x, y, w, h, rx=0, fill="none", stroke=None, cls="", extra=""):
        fill = self.t.get(fill, fill)
        s = f' stroke="{self.t.get(stroke, stroke)}"' if stroke else ""
        c = f' class="{cls}"' if cls else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}"{s}{c}{extra}/>')

    def render(self, title):
        faces = []
        for font, chars in self.used.items():
            fam, wt = font.split("-")
            opts = subset.Options()
            opts.flavor, opts.layout_features, opts.name_IDs = "woff2", ["kern", "liga", "calt"], []
            f = TTFont(cached(FONT_SRC[font]), recalcTimestamp=False)
            sub = subset.Subsetter(opts)
            sub.populate(text="".join(sorted(chars)) + " ")
            sub.subset(f)
            buf = io.BytesIO()
            f.flavor = "woff2"
            f.save(buf)
            b64 = base64.b64encode(buf.getvalue()).decode()
            faces.append(f"@font-face{{font-family:{fam};font-weight:{wt};src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
        anim = "".join(self.css)
        style = "".join(faces) + (f"@media (prefers-reduced-motion:no-preference){{{anim}}}" if anim else "")
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" '
                f'role="img" aria-label="{escape(title)}"><title>{escape(title)}</title><style>{style}</style>'
                + "".join(self.parts) + "</svg>\n")


def save(name, build, title):
    for theme in THEMES:
        svg = build(theme)
        with open(os.path.join(OUT, f"{name}-{theme}.svg"), "w") as f:
            f.write(svg.render(title))


def wrap(text, font, size, width):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if measure(trial, font, size) > width and cur:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur]


# ─────────────────────────────── header ───────────────────────────────
def header(theme):
    s = Svg(840, 252, theme)
    t = s.t
    # status pill
    label = "Open to AI/ML internships"
    pw = measure(label, "sans-500", 13) + 44
    s.rect(0.5, 8.5, pw, 28, rx=14, fill="panel", stroke="border")
    s.add(f'<circle cx="18" cy="22.5" r="4" fill="{t["green"]}"/>'
          f'<circle cx="18" cy="22.5" r="4" fill="none" stroke="{t["green"]}" class="ping"/>')
    s.css.append(".ping{transform-origin:18px 22.5px;animation:ping 2.4s ease-out infinite}"
                 "@keyframes ping{0%{transform:scale(1);opacity:.8}80%,100%{transform:scale(2.6);opacity:0}}")
    s.text(32, 27, label, "sans-500", 13, "fg")
    s.text(0, 104, "Karunya Muddana", "sans-700", 50, "fg", spacing=-1.2)
    w = s.text(0, 146, "I build LLM agents that ", "sans-500", 21, "fg")
    s.text(w, 146, "cite their sources.", "sans-500", 21, "green")
    s.text(0, 180, "B.Tech CS (AI/ML) at GITAM  ·  Hyderabad, India", "sans-400", 15, "muted")
    s.text(0, 208, "Python  ·  MCP  ·  LangGraph  ·  FastAPI  ·  Vertex AI", "mono-400", 12.5, "subtle")

    # answer card: each claim lights up together with its source
    x0, y0, w0, h0 = 486, 6, 352, 240
    s.rect(x0 + .5, y0 + .5, w0 - 1, h0 - 1, rx=12, fill="panel", stroke="border")
    s.text(x0 + 18, y0 + 30, "ANSWER", "mono-400", 11, "muted", spacing=1)
    s.text(x0 + w0 - 18, y0 + 30, "2 claims · 2 cited", "mono-400", 11, "green", anchor="end")
    s.add(f'<path d="M{x0} {y0 + 44.5}H{x0 + w0}" stroke="{t["border"]}"/>')
    claims = [("Q3 dispatches rose 12% over Q2.", "dispatch_log.xlsx › Q3 › F18", "table"),
              ("Next hearing is on 14 March.", "order_sheet.pdf › page 2", "file")]
    for i, (claim, src, ic) in enumerate(claims, 1):
        cy = y0 + 52 + (i - 1) * 32
        s.rect(x0 + 10, cy, w0 - 20, 28, rx=6, fill="hi", cls=f"hl hl{i}", extra=' opacity="0"')
        tw = s.text(x0 + 18, cy + 19, claim, "sans-400", 15, "fg")
        s.rect(x0 + 22 + tw, cy + 6, 16, 16, rx=4, fill="blueBg")
        s.text(x0 + 30 + tw, cy + 18, str(i), "mono-400", 11, "blue", anchor="middle")
        sy = y0 + 150 + (i - 1) * 46
        s.text(x0 + 18, y0 + 136, "SOURCES", "mono-400", 11, "muted", spacing=1) if i == 1 else None
        s.rect(x0 + 10, sy - 4, w0 - 20, 40, rx=8, fill="hi", cls=f"hl hl{i}", extra=' opacity="0"')
        s.rect(x0 + 18.5, sy + .5, w0 - 37, 31, rx=6, fill="canvas", stroke="border")
        s.rect(x0 + 28, sy + 8, 16, 16, rx=4, fill="blueBg")
        s.text(x0 + 36, sy + 20, str(i), "mono-400", 11, "blue", anchor="middle")
        s.icon("oct", ic, x0 + 54, sy + 8, 16, "muted")
        s.text(x0 + 78, sy + 20.5, src, "mono-400", 12, "fg")
    s.css.append(".hl{animation:hl 7s ease-in-out infinite}.hl2{animation-delay:3.5s}"
                 "@keyframes hl{0%,4%{opacity:0}10%,42%{opacity:1}50%,100%{opacity:0}}")
    return s


# ─────────────────────────────── facts ───────────────────────────────
FACTS = [("9.15", "CGPA, B.Tech CS (AI/ML)", "at GITAM Hyderabad"),
         ("Since 2024", "freelancing: AI agents and", "websites for companies"),
         ("Lead", "of the Tareekh team at", "Hack with Hyderabad 3.0"),
         ("21", "workbooks in ExcelMCP's", "ground-truth eval")]


def facts(theme):
    s = Svg(840, 112, theme)
    s.rect(.5, .5, 839, 111, rx=12, fill="panel", stroke="border")
    cw = 840 / 4
    for i, (big, l1, l2) in enumerate(FACTS):
        x = i * cw + 24
        if i:
            s.add(f'<path d="M{i * cw:.1f} 20V92" stroke="{s.t["border"]}"/>')
        s.text(x, 50, big, "sans-700", 30, "fg", spacing=-.5)
        s.text(x, 74, l1, "sans-400", 13, "muted")
        s.text(x, 92, l2, "sans-400", 13, "muted")
    return s


# ─────────────────────────────── project cards ───────────────────────────────
def card(name, pill, desc, lang, proof, draw):
    def build(theme):
        s = Svg(412, 252, theme)
        t = s.t
        s.rect(.5, .5, 411, 251, rx=12, fill="panel", stroke="border")
        s.icon("oct", "repo", 20, 21, 16, "muted")
        s.text(44, 34, name, "sans-600", 17, "blue")
        pw = measure(pill, "sans-500", 11.5) + 20
        s.rect(392 - pw + .5, 19.5, pw, 22, rx=11, fill="none", stroke="border")
        s.text(392 - pw / 2, 34.5, pill, "sans-500", 11.5, "muted", anchor="middle")
        for i, line in enumerate(wrap(desc, "sans-400", 14, 372)[:2]):
            s.text(20, 64 + i * 20, line, "sans-400", 14, "muted")
        s.rect(20.5, 100.5, 371, 103, rx=8, fill="canvas", stroke="border")
        draw(s, t, 20, 100)
        s.add(f'<circle cx="26" cy="226" r="6" fill="{LANG[lang]}"/>')
        lw = s.text(38, 230.5, lang, "sans-400", 12.5, "muted")
        s.icon("oct", "check", 52 + lw, 218, 16, "green")
        s.text(74 + lw, 230.5, proof, "sans-500", 12.5, "fg")
        return s
    return build


def draw_tareekh(s, t, x, y):
    rows = [("12 JAN", "Adjourned; written reply due", "order p.1", "subtle"),
            ("03 FEB", "Party A claims a 70% share", "diary p.14", "subtle"),
            ("14 MAR", "Contradicts their claim in OS 41", "2 sources", "orange")]
    s.add(f'<path d="M{x + 26} {y + 22}V{y + 82}" stroke="{t["border"]}" stroke-width="2"/>')
    for i, (d, txt, cite, dot) in enumerate(rows):
        ry = y + 22 + i * 30
        s.rect(x + 8, ry - 12, 356, 24, rx=6, fill="hi", cls=f"row r{i}", extra=' opacity="0"')
        s.add(f'<circle cx="{x + 26}" cy="{ry}" r="4.5" fill="{t[dot]}" stroke="{t["canvas"]}" stroke-width="2"/>')
        s.text(x + 40, ry + 4, d, "mono-400", 10.5, "muted")
        s.text(x + 92, ry + 4.5, txt, "sans-400", 12.5, "fg")
        cw = measure(cite, "mono-400", 10) + 12
        s.rect(x + 360 - cw, ry - 8, cw, 16, rx=4, fill="blueBg")
        s.text(x + 360 - cw / 2, ry + 3.5, cite, "mono-400", 10, "blue", anchor="middle")
    s.css.append(".row{animation:row 6s infinite}.r1{animation-delay:2s}.r2{animation-delay:4s}"
                 "@keyframes row{0%,2%{opacity:0}8%,30%{opacity:1}36%,100%{opacity:0}}")


def draw_excel(s, t, x, y):
    tabs = ["sales.xlsx", "stock.xlsx", "hr.xlsx"]
    tx = x + 12
    for i, tab in enumerate(tabs):
        w = s.text(tx, y + 18, tab, "mono-400", 10.5, "fg" if i == 1 else "muted")
        if i == 1:
            s.rect(tx, y + 23, w, 2, fill="green")
        tx += w + 14
    s.text(x + 360, y + 18, "routed by embeddings", "sans-400", 11, "subtle", anchor="end")
    s.add(f'<path d="M{x} {y + 28.5}H{x + 372}" stroke="{t["border"]}"/>')
    gx, gy, cw, ch = x + 34, y + 30, 64, 17
    for c, col in enumerate("ABCDE"):
        s.text(gx + c * cw + cw / 2, gy + 9, col, "mono-400", 9, "subtle", anchor="middle")
    vals = [["Item", "Apr", "May", "Jun", "Δ"], ["Resin", "410", "388", "452", "+64"], ["Drums", "96", "104", "99", "−5"]]
    for r in range(3):
        ry = gy + 13 + r * ch
        s.text(x + 18, ry + 12, str(r + 1), "mono-400", 9.5, "subtle", anchor="middle")
        for c in range(5):
            s.rect(gx + c * cw + .5, ry + .5, cw, ch, fill="none", stroke="border")
            s.text(gx + c * cw + 6, ry + 12.5, vals[r][c], "mono-400", 10.5, "muted" if r == 0 else "fg")
    s.rect(gx + 3 * cw - .5, gy + 13 + ch - .5, cw + 2, ch + 2, rx=2, fill="greenBg", stroke="green", cls="cell")
    s.css.append(".cell{animation:cell 3s ease-in-out infinite}@keyframes cell{0%,100%{opacity:1}50%{opacity:.35}}")


def draw_native(s, t, x, y):
    def pill(px, py, label, tag, tagc, tagbg, strike=False):
        w = measure(label, "mono-400", 11) + 20
        s.rect(px + .5, py + .5, w, 24, rx=12, fill="panel", stroke="border")
        s.text(px + 10, py + 16.5, label, "mono-400", 11, "subtle" if strike else "fg")
        if strike:
            s.add(f'<path d="M{px + 8} {py + 12.5}H{px + w - 8}" stroke="{t["subtle"]}"/>')
        tw = measure(tag, "mono-400", 10) + 10
        s.rect(px + w + 6, py + 4, tw, 17, rx=4, fill=tagbg)
        s.text(px + w + 6 + tw / 2, py + 16, tag, "mono-400", 10, tagc, anchor="middle")
        return px + w + 6 + tw
    e1 = pill(x + 14, y + 14, "provider A", "429", "red", "redBg", strike=True)
    s.add(f'<path d="M{e1 + 10} {y + 26.5}H{e1 + 40}" stroke="{t["muted"]}" stroke-dasharray="3 3" class="flow"/>'
          f'<path d="M{e1 + 36} {y + 22.5}l4 4-4 4" fill="none" stroke="{t["muted"]}"/>')
    pill(e1 + 48, y + 14, "provider B", "ok", "green", "greenBg")
    s.css.append(".flow{animation:flow 1s linear infinite}@keyframes flow{to{stroke-dashoffset:-6}}")
    bx, by = x + 14, y + 52
    s.rect(bx + .5, by + .5, 343, 38, rx=8, fill="panel", stroke="border")
    s.icon("oct", "lock", bx + 12, by + 11, 16, "muted")
    s.text(bx + 36, by + 23.5, "sandbox", "mono-400", 11, "fg")
    s.text(bx + 96, by + 23.5, "python  ·  network off  ·  writes .docx", "mono-400", 10.5, "muted")


def draw_smith(s, t, x, y):
    def node(cx, cy, label, accent=False):
        w = measure(label, "mono-400", 10.5) + 18
        s.rect(cx - w / 2 + .5, cy - 11.5, w, 22, rx=6, fill="panel", stroke="green" if accent else "border")
        s.text(cx, cy + 3.5, label, "mono-400", 10.5, "fg", anchor="middle")
        return w / 2
    cy = y + 52
    pts = {"plan": (x + 44, cy), "search": (x + 150, cy - 28), "fetch": (x + 150, cy), "calc": (x + 150, cy + 28),
           "merge": (x + 254, cy), "trace": (x + 330, cy)}
    for a, b in [("plan", "search"), ("plan", "fetch"), ("plan", "calc"), ("search", "merge"), ("fetch", "merge"),
                 ("calc", "merge"), ("merge", "trace")]:
        (x1, y1), (x2, y2) = pts[a], pts[b]
        x1 += 26
        x2 -= 26
        mx = (x1 + x2) / 2
        s.add(f'<path d="M{x1} {y1}C{mx} {y1} {mx} {y2} {x2} {y2}" fill="none" stroke="{t["border"]}" stroke-width="1.5"/>'
              f'<path d="M{x1} {y1}C{mx} {y1} {mx} {y2} {x2} {y2}" fill="none" stroke="{t["green"]}" stroke-width="1.5" '
              f'stroke-dasharray="6 120" class="pulse"/>')
    for k, (px, py) in pts.items():
        node(px, py, k + (" ✓" if k == "trace" else ""), accent=k == "trace")
    s.css.append(".pulse{animation:pulse 2.6s linear infinite}@keyframes pulse{from{stroke-dashoffset:6}to{stroke-dashoffset:-120}}")


CARDS = {
    "card-tareekh": card("tareekh", "Hackathon · team lead",
                         "Practice memory for Indian litigators. One memory per hearing, every sentence cited.",
                         "Python", "28 automated tests", draw_tareekh),
    "card-excelmcp": card("ExcelMCP", "MIT",
                          "MCP server for live Excel data. Values are fetched live; only sheet structure is cached.",
                          "Python", "21-workbook ground-truth eval", draw_excel),
    "card-native": card("Native", "Apache-2.0",
                        "Agent runtime that runs code in a sealed container and falls back across model providers.",
                        "Python", "LangGraph · FastAPI · Docker", draw_native),
    "card-smith": card("project-smith", "Agent runtime",
                       "Zero-trust agent runtime. Drop in tools; the planner builds and runs the DAG.",
                       "Python", "parallel DAG · traced runs", draw_smith),
}


# ─────────────────────────────── stack ───────────────────────────────
STACK = [
    ("Languages", [("si", "python", "Python"), ("oct", "database", "SQL"), ("si", "typescript", "TypeScript"),
                   ("si", "cplusplus", "C++")]),
    ("AI / ML", [("si", "modelcontextprotocol", "MCP"), ("si", "langchain", "LangGraph"), ("oct", "search", "RAG, embeddings"),
                 ("si", "scikitlearn", "scikit-learn"), ("oct", "git-branch", "XGBoost"), ("si", "pandas", "Pandas, NumPy")]),
    ("Backend", [("si", "fastapi", "FastAPI"), ("si", "postgresql", "PostgreSQL"), ("si", "sqlite", "SQLite"),
                 ("oct", "graph", "Microsoft Graph"), ("si", "pytest", "pytest")]),
    ("Cloud & tools", [("si", "googlecloud", "Google Cloud"), ("oct", "cpu", "Vertex AI"), ("si", "docker", "Docker"),
                       ("si", "git", "Git"), ("si", "nextdotjs", "Next.js")]),
]


def stack(theme):
    s = Svg(840, 222, theme)
    s.rect(.5, .5, 839, 221, rx=12, fill="panel", stroke="border")
    cw = 840 / 4
    for i, (head, items) in enumerate(STACK):
        x = i * cw + 24
        if i:
            s.add(f'<path d="M{i * cw:.1f} 20V202" stroke="{s.t["border"]}"/>')
        s.text(x, 38, head.upper(), "mono-400", 11, "muted", spacing=1)
        for j, (kind, ic, label) in enumerate(items):
            iy = 58 + j * 26
            s.icon(kind, ic, x, iy, 15, "muted")
            s.text(x + 24, iy + 12, label, "sans-400", 14, "fg")
    return s


# ─────────────────────────────── repo stats (graphs) ───────────────────────────────
# Oldest first; this is also the stacking order of the growth chart.
REPOS = [("project-smith", "project-smith", "purple"), ("ExcelMCP", "ExcelMCP", "green"),
         ("Native", "Native", "orange"), ("tareekh", "Tareekh", "blue")]
SERIES = {"dark": dict(purple="#ab7df8", green="#3fb950", orange="#db6d28", blue="#4493f8"),
          "light": dict(purple="#8250df", green="#1a7f37", orange="#bc4c00", blue="#0969da")}
CODE_EXT = {".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript", ".jsx": "JavaScript",
            ".html": "HTML", ".css": "CSS", ".sql": "SQL", ".sh": "Shell"}
LANG.update({"HTML": "#e34c26", "CSS": "#663399", "JavaScript": "#f1e05a", "Other": "#8b949e"})


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=True).stdout


def checkout(name):
    path = os.path.join(CACHE, "repos", name)
    if os.path.isdir(os.path.join(path, ".git")):
        git(path, "pull", "-q", "--ff-only")
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        subprocess.run(["git", "clone", "-q", f"https://github.com/Karunya-Muddana/{name}", path], check=True)
    return path


def count_tests(path):
    """Tests as pytest collects them: test functions and Test* methods, times literal parametrize cases."""
    def cases(fn):
        k = 1
        for d in fn.decorator_list:
            if (isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "parametrize" and len(d.args) >= 2
                    and isinstance(d.args[1], (ast.List, ast.Tuple))):
                k *= len(d.args[1].elts)
        return k
    tree, n = ast.parse(open(path, encoding="utf-8").read()), 0
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            n += cases(node)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            n += sum(cases(m) for m in node.body
                     if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name.startswith("test"))
    return n


def collect():
    stats = {}
    for name, label, _ in REPOS:
        path = checkout(name)
        # net lines of code over time, from every commit's numstat (lockfiles excluded)
        growth, day, net = [], None, 0
        for line in git(path, "log", "--reverse", "--numstat", "--format=@%ad", "--date=short").splitlines():
            if line.startswith("@"):
                if day:
                    growth.append((day, net))
                day = line[1:]
            elif line.strip():
                a, d, f = line.split("\t", 2)
                f = f.split(" => ")[-1].rstrip("}")
                if a != "-" and "lock" not in f.lower() and os.path.splitext(f)[1].lower() in CODE_EXT:
                    net += int(a) - int(d)
        growth.append((day, net))
        langs, tests = {}, 0
        for f in git(path, "ls-files").split():
            lang = CODE_EXT.get(os.path.splitext(f)[1].lower())
            if lang and "lock" not in f.lower():
                with open(os.path.join(path, f), encoding="utf-8", errors="ignore") as fh:
                    langs[lang] = langs.get(lang, 0) + sum(1 for l in fh if l.strip())
            if f.endswith(".py") and "tests/" in f and os.path.basename(f).startswith("test_"):
                tests += count_tests(os.path.join(path, f))
        stats[label] = dict(growth=growth, lines=net, langs=langs, tests=tests)
    return stats


def k(n):
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def growth_chart(stats):
    def build(theme):
        s = Svg(840, 300, theme)
        t, col = s.t, SERIES[theme]
        s.rect(.5, .5, 839, 299, rx=12, fill="panel", stroke="border")
        total = sum(v["lines"] for v in stats.values())
        s.text(24, 38, "Code written", "sans-600", 16, "fg")
        start = min(dt.date.fromisoformat(v["growth"][0][0]) for v in stats.values()).replace(day=1)
        end = dt.date.today()
        s.text(24, 58, f"Lines of code across {len(stats)} public projects, {start:%b %Y} – {end:%b %Y}", "sans-400", 12.5, "muted")
        s.text(816, 42, k(total), "sans-700", 28, "fg", anchor="end", spacing=-.5)
        s.text(816, 60, "lines of code", "sans-400", 12, "muted", anchor="end")
        x0, x1, y0, y1 = 64, 816, 92, 236
        top = max(20000, -(-total // 20000) * 20000)
        days = (end - start).days
        X = lambda d: x0 + (x1 - x0) * (d - start).days / days
        Y = lambda v: y1 - (y1 - y0) * v / top
        for v in range(0, top + 1, 20000 if top > 40000 else 10000):
            s.add(f'<path d="M{x0} {Y(v):.1f}H{x1}" stroke="{t["border"]}" stroke-dasharray="{"0" if v == 0 else "2 4"}"/>')
            s.text(x0 - 8, Y(v) + 3.5, f"{v // 1000}k" if v else "0", "mono-400", 10.5, "subtle", anchor="end")
        m = start
        while m <= end:
            if X(m) < x1 - 20:
                s.text(X(m), y1 + 18, m.strftime("%b") if m.month != 1 else m.strftime("%b %y"), "mono-400", 10.5, "subtle", anchor="middle")
            m = (m.replace(day=28) + dt.timedelta(days=4)).replace(day=1)

        def value(series, day):
            v = 0
            for d, n in series:
                if dt.date.fromisoformat(d) <= day:
                    v = n
            return max(v, 0)
        steps = [start + dt.timedelta(days=i) for i in range(0, days + 1, 2)] + [end]
        base = [0] * len(steps)
        paths = []
        for label, (_, _, c) in zip(stats, REPOS):
            vals = [b + value(stats[label]["growth"], d) for b, d in zip(base, steps)]
            first = dt.date.fromisoformat(stats[label]["growth"][0][0])
            own = [(d, v) for d, v in zip(steps, vals) if d >= first]
            up = " ".join(f"{X(d):.1f},{Y(v):.1f}" for d, v in zip(steps, vals))
            down = " ".join(f"{X(d):.1f},{Y(v):.1f}" for d, v in reversed(list(zip(steps, base))))
            edge = " ".join(f"{X(d):.1f},{Y(v):.1f}" for d, v in own)
            paths.append(f'<polygon points="{up} {down}" fill="{col[c]}" fill-opacity=".8"/>'
                         f'<polyline points="{edge}" fill="none" stroke="{col[c]}" stroke-width="1.6" stroke-linejoin="round"/>')
            base = vals
        s.add(f'<clipPath id="reveal"><rect x="{x0}" y="{y0 - 10}" width="{x1 - x0}" height="{y1 - y0 + 12}" class="rv"/></clipPath>'
              f'<g clip-path="url(#reveal)">{"".join(paths)}</g>')
        s.css.append(f".rv{{animation:rv 1.6s cubic-bezier(.3,.7,.2,1)}}@keyframes rv{{from{{width:0}}to{{width:{x1 - x0}px}}}}")
        lx = 24
        for label, (_, _, c) in zip(stats, REPOS):
            s.add(f'<circle cx="{lx + 5}" cy="274" r="5" fill="{col[c]}"/>')
            w = s.text(lx + 16, 278.5, label, "sans-500", 12.5, "fg")
            w += s.text(lx + 22 + w, 278.5, k(stats[label]["lines"]), "mono-400", 11.5, "muted")
            lx += w + 44
        return s
    return build


def bars_card(stats, title, key, note, fmt=k):
    rows = sorted(((lab, stats[lab][key], c) for lab, (_, _, c) in zip(stats, REPOS) if stats[lab][key]),
                  key=lambda r: -r[1])

    def build(theme):
        s = Svg(412, 252, theme)
        col = SERIES[theme]
        s.rect(.5, .5, 411, 251, rx=12, fill="panel", stroke="border")
        s.text(20, 36, title, "sans-600", 16, "fg")
        total = sum(r[1] for r in rows)
        s.text(392, 38, fmt(total), "sans-700", 24, "fg", anchor="end", spacing=-.5)
        mx = max(r[1] for r in rows)
        for i, (lab, v, c) in enumerate(rows):
            y = 68 + i * 30
            s.text(20, y + 12, lab, "sans-400", 13, "fg")
            w = max(4, 196 * v / mx)
            s.rect(124, y + 2, 196, 12, rx=6, fill="canvas")
            s.rect(124, y + 2, w, 12, rx=6, fill=col[c], cls="bar", extra=f' style="animation-delay:{i * .12:.2f}s"')
            s.text(392, y + 12.5, fmt(v), "mono-400", 11.5, "muted", anchor="end")
        s.css.append(".bar{transform-box:fill-box;transform-origin:left;animation:bar 1s cubic-bezier(.3,.7,.2,1) backwards}"
                     "@keyframes bar{from{transform:scaleX(0)}}")
        note(s, theme)
        return s
    return build


def languages_note(stats):
    langs = {}
    for v in stats.values():
        for lang, n in v["langs"].items():
            langs[lang] = langs.get(lang, 0) + n
    total = sum(langs.values())
    top = sorted(langs.items(), key=lambda kv: -kv[1])
    shown = [(l, n) for l, n in top if n / total >= .02][:3]
    rest = total - sum(n for _, n in shown)
    bar = shown + ([("Other", rest)] if rest else [])

    def note(s, theme):
        s.text(20, 196, "Languages", "sans-600", 13, "fg")
        x = 20
        s.add('<clipPath id="lb"><rect x="20" y="204" width="372" height="8" rx="4"/></clipPath><g clip-path="url(#lb)">')
        for lang, n in bar:
            w = 372 * n / total
            s.rect(x, 204, w + .5, 8, fill=LANG[lang])
            x += w
        s.add("</g>")
        x = 20
        for lang, n in shown:
            s.add(f'<circle cx="{x + 4}" cy="230" r="4" fill="{LANG[lang]}"/>')
            w = s.text(x + 13, 234, lang, "sans-500", 12, "fg")
            w += s.text(x + 17 + w, 234, f"{100 * n / total:.1f}%", "sans-400", 12, "muted")
            x += w + 30
    return note


def tests_note(s, theme):
    s.add(f'<path d="M20 {176.5}H392" stroke="{s.t["border"]}"/>')
    s.icon("oct", "check", 20, 192, 16, "green")
    s.text(44, 204.5, "Plus a 21-workbook ground-truth eval for ExcelMCP", "sans-500", 12.5, "fg")
    s.text(20, 232, "Counted the way pytest collects them, from each tests/ folder", "sans-400", 11.5, "muted")


# ─────────────────────────────── contact buttons ───────────────────────────────
def button(ic, label):
    def build(theme):
        w = round(measure(label, "sans-500", 14) + 52)
        s = Svg(w, 36, theme)
        s.rect(.5, .5, w - 1, 35, rx=6, fill="panel", stroke="border")
        s.icon("oct", ic, 14, 10, 16, "muted")
        s.text(38, 23, label, "sans-500", 14, "fg")
        return s
    return build


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    save("header", header, "Karunya Muddana. I build LLM agents that cite their sources.")
    save("facts", facts, "9.15 CGPA; freelancing since 2024; Tareekh team lead at Hack with Hyderabad 3.0; 21-workbook eval")
    for name, build in CARDS.items():
        save(name, build, name.replace("card-", ""))
    save("stack", stack, "Tech stack")
    stats = collect()
    total, tests = sum(v["lines"] for v in stats.values()), sum(v["tests"] for v in stats.values())
    save("graph-growth", growth_chart(stats), f"{k(total)} lines of code written across four public projects")
    save("graph-code", bars_card(stats, "Lines of code", "lines", languages_note(stats)), "Lines of code by project and languages")
    save("graph-tests", bars_card(stats, "Automated tests", "tests", tests_note, fmt=str), f"{tests} automated tests")
    save("btn-portfolio", button("globe", "Portfolio"), "Portfolio")
    save("btn-linkedin", button("person", "LinkedIn"), "LinkedIn")
    save("btn-email", button("mail", "Email"), "Email")
    for f in sorted(os.listdir(OUT)):
        if f.endswith(".svg"):
            print(f"{f:28s} {os.path.getsize(os.path.join(OUT, f)) / 1024:6.1f} KB")
