"""Build every image the profile README uses, in a light and a dark version.

    pip install fonttools brotli
    python3 scripts/build.py

Fonts (Mona Sans, Monaspace Neon; SIL OFL) are subset and embedded in each SVG, so the
images look the same everywhere and load nothing at render time. Icons come from GitHub
Octicons (MIT). Sources are downloaded once into .cache/.
"""
import ast
import base64
import datetime as dt
import io
import json
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

# Tonal surfaces with no outlines; four accents (teal, coral, amber, indigo) of my own
THEMES = {
    "dark": dict(canvas="#0d1117", panel="#161b22", raised="#1f2630", border="#2b323c", fg="#eef1f5", muted="#9aa3ad",
                 subtle="#6b7480", green="#4fd1b5", greenBg="#4fd1b51f", blue="#8c9bff", blueBg="#8c9bff1f",
                 orange="#ffb35c", red="#ff8a6b", redBg="#ff8a6b1f", hi="#8c9bff1a"),
    "light": dict(canvas="#ffffff", panel="#f4f5f7", raised="#e9ecf0", border="#dde1e6", fg="#16191d", muted="#5a626c",
                  subtle="#8a929c", green="#0b8a74", greenBg="#0b8a7414", blue="#4c5bd4", blueBg="#4c5bd414",
                  orange="#c97a12", red="#d4553a", redBg="#d4553a14", hi="#4c5bd40f"),
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
        with open(os.path.join(OUT, f"{name}-{theme}.svg"), "w", encoding="utf-8", newline="\n") as f:
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


# ─────────────────────────────── project cards ───────────────────────────────
# Laid out like GitHub's pinned repositories. The drawing on each card uses real
# content from that repo (tool names, test cases, a saved run), never sample data.
def card(name, desc, footer, draw):
    def build(theme):
        s = Svg(412, 236, theme)
        s.rect(.5, .5, 411, 235, rx=20, fill="panel")
        s.icon("oct", "repo", 20, 21, 16, "muted")
        s.text(44, 34, name, "sans-600", 16, "blue")
        for i, line in enumerate(wrap(desc, "sans-400", 13.5, 372)[:2]):
            s.text(20, 62 + i * 20, line, "sans-400", 13.5, "muted")
        draw(s, s.t, 20, 98)
        s.add(f'<circle cx="26" cy="212" r="6" fill="{LANG["Python"]}"/>')
        x = 38 + s.text(38, 216.5, "Python", "sans-400", 12.5, "muted") + 18
        for item in footer:
            x += s.text(x, 216.5, item, "sans-400", 12.5, "muted") + 18
        return s
    return build


def draw_tareekh(s, t, x, y):
    # straight from tareekh/backend/tests/test_offline.py
    rows = [('"OS 214/24 - Harinath sought time"', "case C1"),
            ('"O.S. No. 57 of 2025"', "case C2"),
            ('"IMG_20260812_171906.jpg"', "hearing 2026-08-12")]
    for i, (src, out) in enumerate(rows):
        ry = y + 18 + i * 26
        w = s.text(x, ry, src, "mono-400", 11.5, "muted")
        s.text(x + w + 10, ry, "→", "mono-400", 11.5, "subtle")
        s.text(x + w + 30, ry, out, "mono-400", 11.5, "fg")


def draw_excel(s, t, x, y):
    # the 14 @mcp.tool functions in ExcelMCP/main.py
    tools = ["scan_workspace", "get_workspace_graph", "inspect_file", "sheet_layout", "query", "lookup", "get_cell",
             "filter_sheet", "fetch_sheet_rows", "fetch_region_rows", "aggregate", "cross_file_aggregate",
             "join_sheets", "derive"]
    for i, name in enumerate(tools):
        col, row = divmod(i, 5)
        s.text(x + col * 124, y + 14 + row * 18, name, "mono-400", 10, "fg" if col == 0 and row == 0 else "muted")


def draw_native(s, t, x, y):
    # app/config/providers.py: "Five lanes ... the point of the road is that traffic
    # keeps moving when a lane closes." Ollama is always last: it works offline.
    lanes = ["groq", "gemini", "openrouter", "nvidia", "ollama"]
    lx = x + 92
    for i, name in enumerate(lanes):
        ly = y + 10 + i * 17
        s.text(x, ly + 4, name, "mono-400", 11, "fg" if i == 1 else "muted")
        dash = ' stroke-dasharray="3 4"' if i == 0 else ""
        s.add(f'<path d="M{lx} {ly}H{x + 372}" stroke="{t["border"]}" stroke-width="1.5"{dash}/>')
    s.text(x + 372, y + 6, "rate-limited", "sans-400", 11, "subtle", anchor="end")
    s.text(x + 372, y + 74, "works offline", "sans-400", 11, "subtle", anchor="end")
    y0, y1 = y + 10, y + 27
    s.add(f'<path d="M{lx} {y0}H{lx + 70}C{lx + 100} {y0} {lx + 100} {y1} {lx + 130} {y1}H{x + 280}" '
          f'fill="none" stroke="{t["green"]}" stroke-width="2"/>'
          f'<circle cx="{x + 280}" cy="{y1}" r="3.5" fill="{t["green"]}"/>')


def draw_smith(s, t, x, y):
    # a saved run from the repo: smith_dag_1776680299.json
    def node(cx, cy, tool, note):
        w = max(measure(tool, "mono-400", 11), measure(note, "sans-400", 11)) + 20
        s.rect(cx - w / 2 + .5, cy - 17.5, w, 35, rx=10, fill="canvas")
        s.text(cx, cy - 2, tool, "mono-400", 11, "fg", anchor="middle")
        s.text(cx, cy + 12, note, "sans-400", 11, "muted", anchor="middle")
        return w / 2
    cy = y + 46
    a = (x + 56, cy - 22, "google_search", "AMD news")
    b = (x + 56, cy + 22, "google_search", "Intel news")
    c = (x + 190, cy, "deep_summarizer", "compare")
    d = (x + 314, cy, "llm_caller", "report")
    for (x1, y1, *_), (x2, y2, *_) in [(a, c), (b, c), (c, d)]:
        x1 += 54
        x2 -= 60 if x2 == c[0] else 44
        mx = (x1 + x2) / 2
        s.add(f'<path d="M{x1} {y1}C{mx} {y1} {mx} {y2} {x2} {y2}" fill="none" stroke="{t["muted"]}" stroke-width="1.2"/>')
    for n in (a, b, c, d):
        node(*n)


# ─────────────────────────────── repo stats (graphs) ───────────────────────────────
# Oldest first; this is also the stacking order of the growth chart.
REPOS = [("project-smith", "project-smith", "purple"), ("ExcelMCP", "ExcelMCP", "green"),
         ("Native", "Native", "orange"), ("tareekh", "Tareekh", "blue")]
SERIES = {"dark": dict(purple="#8c9bff", green="#4fd1b5", orange="#ffb35c", blue="#ff8a6b"),
          "light": dict(purple="#4c5bd4", green="#0b8a74", orange="#c97a12", blue="#d4553a")}
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
        s.rect(.5, .5, 839, 299, rx=24, fill="panel")
        total = sum(v["lines"] for v in stats.values())
        s.text(24, 38, f"{k(total)} lines of code", "sans-600", 16, "fg")
        start = min(dt.date.fromisoformat(v["growth"][0][0]) for v in stats.values()).replace(day=1)
        end = dt.date.today()
        s.text(24, 58, f"Written across {len(stats)} public projects, {start:%B %Y} to {end:%B %Y}", "sans-400", 12.5, "muted")
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
                s.text(X(m), y1 + 18, m.strftime("%b") if m.month != 1 else m.strftime("%b %Y"), "sans-400", 11, "subtle", anchor="middle")
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
        s.add("".join(paths))
        lx = 24
        for label, (_, _, c) in zip(stats, REPOS):
            s.add(f'<circle cx="{lx + 5}" cy="274" r="5" fill="{col[c]}"/>')
            w = s.text(lx + 16, 278.5, label, "sans-500", 12.5, "fg")
            w += s.text(lx + 22 + w, 278.5, k(stats[label]["lines"]), "sans-400", 12.5, "muted")
            lx += w + 44
        return s
    return build




def tests_and_languages(stats):
    """One panel, two halves: tests per project and the language split, no repeated totals."""
    langs = {}
    for v in stats.values():
        for lang, n in v["langs"].items():
            langs[lang] = langs.get(lang, 0) + n
    total_l = sum(langs.values())
    top = sorted(langs.items(), key=lambda kv: -kv[1])
    shown = [(l, n) for l, n in top if n / total_l >= .02][:3]
    rest = total_l - sum(n for _, n in shown)
    bar = shown + ([("Other", rest)] if rest else [])
    rows = sorted(((lab, stats[lab]["tests"], c) for lab, (_, _, c) in zip(stats, REPOS) if stats[lab]["tests"]),
                  key=lambda r: -r[1])

    def build(theme):
        s = Svg(840, 196, theme)
        col = SERIES[theme]
        s.rect(.5, .5, 839, 195, rx=24, fill="panel")
        s.add(f'<path d="M440 24V172" stroke="{s.t["border"]}"/>')
        s.text(24, 38, f"{sum(r[1] for r in rows)} automated tests", "sans-600", 16, "fg")
        s.text(24, 58, "As pytest collects them from each tests/ folder", "sans-400", 12.5, "muted")
        mx = max(r[1] for r in rows)
        for i, (lab, v, c) in enumerate(rows):
            y = 86 + i * 28
            s.text(24, y + 11, lab, "sans-400", 13, "fg")
            s.rect(128, y + 1, 220 * v / mx, 12, rx=3, fill=col[c])
            s.text(128 + 220 * v / mx + 8, y + 11.5, str(v), "mono-400", 11.5, "muted")
        s.text(464, 38, "Languages", "sans-600", 16, "fg")
        s.text(464, 58, "Share of lines of code", "sans-400", 12.5, "muted")
        s.add('<clipPath id="lb"><rect x="464" y="86" width="352" height="10" rx="3"/></clipPath><g clip-path="url(#lb)">')
        x = 464
        for lang, n in bar:
            w = 352 * n / total_l
            s.rect(x, 86, max(w - 2, 1), 10, fill=LANG[lang])
            x += w
        s.add("</g>")
        for i, (lang, n) in enumerate(bar):
            ly = 124 + i * 22
            if ly > 180:
                break
            s.add(f'<circle cx="469" cy="{ly - 4}" r="5" fill="{LANG[lang]}"/>')
            s.text(482, ly, lang, "sans-400", 13, "fg")
            s.text(816, ly, f"{100 * n / total_l:.1f}%", "mono-400", 11.5, "muted", anchor="end")
        return s
    return build


# ─────────────────────────────── header, timeline, upstream ───────────────────────────────
STATS = [("9.15", "CGPA", "B.Tech CS (AI & ML)"), ("2", "Fixes merged upstream", "IPython · git-cola"),
         ("600+", "Students served", "by the CBSE analyzer"), ("2", "Countries with clients", "India · Germany"),
         ("2", "Hackathon builds", "SIH 2026 · HwH 3.0")]


def header():
    def build(theme):
        s = Svg(840, 268, theme)
        t, col = s.t, SERIES[theme]
        s.rect(0, 0, 840, 268, rx=28, fill="panel")
        # a small cluster of flat shapes on the right, one per accent
        gx, gy, c = 676, 36, 56
        s.add(f'<circle cx="{gx + c / 2}" cy="{gy + c / 2}" r="{c / 2}" fill="{col["green"]}"/>'
              f'<path d="M{gx + c + 10} {gy + c}V{gy}A{c} {c} 0 0 1 {gx + 2 * c + 10} {gy + c}Z" fill="{col["blue"]}"/>'
              f'<rect x="{gx}" y="{gy + c + 10}" width="{c}" height="{c}" rx="16" fill="{col["orange"]}"/>'
              f'<path d="M{gx + c + 10} {gy + c + 10}H{gx + 2 * c + 10}A{c / 2} {c / 2} 0 0 1 {gx + c + 10} {gy + c + 10}Z" '
              f'fill="{col["purple"]}" class="spin"/>')
        s.css.append(f"@keyframes r{{0%,70%{{transform:rotate(0)}}100%{{transform:rotate(180deg)}}}}"
                     f".spin{{transform-origin:{gx + c * 1.5 + 10}px {gy + c * 1.5 + 10}px;animation:r 6s cubic-bezier(.2,0,0,1) infinite alternate}}")
        s.text(36, 66, "Karunya Muddana", "sans-600", 34, "fg", spacing=-.6)
        s.text(36, 94, "AI engineer. I build LLM agents that work on real data", "sans-400", 15, "muted")
        s.text(36, 114, "and cite where every answer came from.", "sans-400", 15, "muted")
        chip = "Open to AI/ML internships"
        w = measure(chip, "sans-500", 12.5) + 40
        s.rect(36, 132, w, 30, rx=15, fill="greenBg")
        s.add(f'<circle cx="54" cy="147" r="7" fill="{t["green"]}" class="pulse" opacity="0"/>'
              f'<circle cx="54" cy="147" r="4" fill="{t["green"]}"/>')
        s.css.append("@keyframes p{0%{opacity:.5;transform:scale(.6)}100%{opacity:0;transform:scale(1.7)}}"
                     ".pulse{transform-box:fill-box;transform-origin:center;animation:p 2.4s ease-out infinite}")
        s.text(66, 151.5, chip, "sans-500", 12.5, "green")
        x = 36 + w + 20
        for name, label in [("location", "Hyderabad, India"), ("mortar-board", "GITAM, class of 2029")]:
            s.icon("oct", name, x, 140, 14, "subtle")
            x += 20 + s.text(x + 20, 151.5, label, "sans-400", 12.5, "muted") + 20
        # stats as tonal tiles
        n, gap, x0 = len(STATS), 10, 24
        tw = (840 - 2 * x0 - gap * (n - 1)) / n
        accents = ["green", "blue", "orange", "purple", "green"]
        for i, (num, label, note) in enumerate(STATS):
            x = x0 + i * (tw + gap)
            s.rect(x, 180, tw, 64, rx=16, fill="raised")
            s.add(f'<circle cx="{x + tw - 16:.1f}" cy="196" r="4" fill="{col[accents[i]]}"/>')
            s.text(x + 16, 210, num, "sans-600", 21, "fg", spacing=-.3)
            s.text(x + 16, 230, label, "sans-400", 11.5, "muted")
        return s
    return build


# newest first: (when, title, tag, where, detail)
TIMELINE = [
    ("Oct 2026 – now", "AI engineer, contract", "work", "Healthcare certification project · Germany (remote)",
     "Document review that checks uploaded certificates against the application form. Caught valid phone scans "
     "being read as expired, and added a second independent reading backed by a 33-case test set with tampered files."),
    ("Oct 2026 – now", "Open-source contributor", "upstream", "IPython · git-cola · icalendar · scikit-learn",
     "Two fixes merged within two weeks of the first PR, two more in review."),
    ("Sep 2026", "Led the Tareekh team", "hackathon", "Hack with Hyderabad 3.0",
     "Turns a lawyer's diary photos, notes and court orders into one cited memory per hearing."),
    ("Sep 2026", "Built Native", "hackathon", "Smart India Hackathon 2026",
     "A local-first agent workbench with 22 tools that keeps running through rate limits and works offline."),
    ("Aug 2026", "Published engraph on PyPI", "release", "pip install engraph",
     "Long-term memory for AI coding assistants, so the next session doesn't start from zero."),
    ("Aug 2026", "Open-sourced ExcelMCP", "release", "MCP server · MIT",
     "The engine behind the manufacturer's assistant: live Excel answers with the file, sheet and cell behind each number."),
    ("2024 – now", "Freelance AI engineer", "work", "Chemical manufacturer · Hyderabad",
     "Built an assistant that let staff question their Excel data in plain English. Used daily until the company moved to an ERP."),
    ("2025", "House price prediction", "ml", "Ames housing dataset",
     "Benchmarked 11 models; a tuned XGBoost reached 0.1002 log-RMSE and priced 79% of houses within 10%."),
    ("Jun 2025", "CBSE result analyzer", "tool", "Used by teachers at two schools",
     "Turns the board's raw gazette files into Excel and PDF reports for 600 students' results."),
    ("2025 – 2029", "B.Tech, Computer Science (AI & ML)", "edu", "GITAM University, Hyderabad", "CGPA 9.15 / 10."),
]
TAGS = {"work": "green", "upstream": "purple", "hackathon": "orange", "release": "blue", "ml": "purple", "tool": "green",
        "edu": "orange"}


def timeline():
    def build(theme):
        rows = [(e, wrap(e[4], "sans-400", 12.5, 700)) for e in TIMELINE]
        h = 70 + sum(54 + 18 * len(lines) for _, lines in rows) - 10
        s = Svg(840, h, theme)
        t, col = s.t, SERIES[theme]
        s.rect(.5, .5, 839, h - 1, rx=24, fill="panel")
        s.text(28, 38, "$", "mono-400", 12, "green")
        s.text(42, 38, "git log --graph --author=karunya", "mono-400", 12, "subtle")
        y, rail = 70, 40
        last = y + sum(54 + 18 * len(lines) for _, lines in rows[:-1])
        s.add(f'<path d="M{rail} {y}V{last}" stroke="{t["border"]}" stroke-width="2"/>')
        for i, ((when, title, tag, where, _), lines) in enumerate(rows):
            c = col[TAGS[tag]]
            if i == 0:
                s.add(f'<circle cx="{rail}" cy="{y}" r="7" fill="{t["panel"]}" stroke="{c}" stroke-width="2"/>'
                      f'<circle cx="{rail}" cy="{y}" r="3" fill="{c}"/>')
            else:
                s.add(f'<circle cx="{rail}" cy="{y}" r="5" fill="{t["panel"]}" stroke="{c}" stroke-width="2"/>')
            w = s.text(64, y + 5, title, "sans-600", 15, "fg")
            tw = measure(tag, "mono-400", 10.5) + 14
            s.add(f'<rect x="{64 + w + 10:.1f}" y="{y - 8}" width="{tw:.1f}" height="18" rx="9" fill="{c}" fill-opacity=".14"/>')
            s.text(64 + w + 17, y + 4.5, tag, "mono-400", 10.5, c)
            s.text(816, y + 5, when, "mono-400", 11.5, "subtle", anchor="end")
            s.text(64, y + 25, where, "sans-500", 12.5, "fg")
            for j, line in enumerate(lines):
                s.text(64, y + 44 + j * 18, line, "sans-400", 12.5, "muted")
            y += 54 + 18 * len(lines)
        return s
    return build


# Fixes sent to other people's projects. Title and state are refreshed from the GitHub API;
# the values here are what the image shows if that call fails.
UPSTREAM = [("ipython/ipython", 15431, "Fix WebP detection and size parsing in display.Image", "merged"),
            ("git-cola/git-cola", 1654, "cmds: report errors when opening a repository fails", "merged"),
            ("collective/icalendar", 1886, "Fix vUTCOffset.from_ical reading unsigned offsets wrongly", "open"),
            ("scikit-learn/scikit-learn", 35124, "FIX make Bunch.copy return a Bunch instead of a dict", "open")]


def fetch_prs():
    prs = []
    for repo, n, title, state in UPSTREAM:
        req = urllib.request.Request(f"https://api.github.com/repos/{repo}/pulls/{n}",
                                     headers={"Accept": "application/vnd.github+json"})
        if os.environ.get("GITHUB_TOKEN"):
            req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                pr = json.load(r)
            title, state = pr["title"], "merged" if pr.get("merged_at") else pr["state"]
        except Exception as e:
            print(f"keeping saved state for {repo}#{n}: {e}")
        prs.append((repo, n, title, state))
    return prs


def upstream(prs):
    label = {"merged": "Merged", "open": "In review", "closed": "Closed"}

    def build(theme):
        h = 76 + 58 * len(prs)
        s = Svg(840, h, theme)
        t = s.t
        s.rect(.5, .5, 839, h - 1, rx=24, fill="panel")
        merged = sum(p[3] == "merged" for p in prs)
        s.text(24, 38, f"{merged} merged, {sum(p[3] == 'open' for p in prs)} in review", "sans-600", 16, "fg")
        s.text(24, 58, "Pull requests to libraries I use", "sans-400", 12.5, "muted")
        for i, (repo, n, title, state) in enumerate(prs):
            y = 76 + i * 58
            if i:
                s.add(f'<path d="M24 {y + .5}H816" stroke="{t["border"]}"/>')
            c = {"merged": SERIES[theme]["purple"], "open": SERIES[theme]["orange"]}.get(state, t["red"])
            s.icon("oct", "git-merge" if state == "merged" else "git-pull-request", 24, y + 14, 16, c)
            w = s.text(52, y + 26, repo, "sans-600", 13.5, "fg")
            s.text(52 + w + 8, y + 26, f"#{n}", "mono-400", 12, "subtle")
            s.text(52, y + 45, title, "sans-400", 12.5, "muted")
            lab = label.get(state, state)
            lw = measure(lab, "sans-500", 11.5) + 20
            s.rect(816 - lw, y + 17, lw, 23, rx=11.5, fill=c, extra=' fill-opacity=".14"')
            s.text(816 - lw / 2, y + 32.5, lab, "sans-500", 11.5, c, anchor="middle")
        return s
    return build


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith(".svg"):
            os.remove(os.path.join(OUT, f))
    stats = collect()
    tests = {lab: v["tests"] for lab, v in stats.items()}
    cards = {
        "card-tareekh": card("tareekh", "Turns a lawyer's diary photos, notes and court orders into one cited memory per hearing.",
                             ["Built at Hack with Hyderabad 3.0", f"{tests['Tareekh']} tests"], draw_tareekh),
        "card-excelmcp": card("ExcelMCP", "An MCP server that answers questions about live Excel files in OneDrive through 14 tools.",
                              ["MIT", f"{tests['ExcelMCP']} tests", "21-workbook eval"], draw_excel),
        "card-native": card("Native", "An agent runtime that runs code in a sandbox and switches model provider when one is rate-limited.",
                            ["Apache-2.0", "LangGraph", "Docker"], draw_native),
        "card-smith": card("project-smith", "The planner turns a request into a graph of tool calls and runs independent steps in parallel.",
                           ["MIT", f"{tests['project-smith']} tests"], draw_smith),
    }
    for name, build in cards.items():
        save(name, build, name.replace("card-", ""))
    total = sum(v["lines"] for v in stats.values())
    save("graph-growth", growth_chart(stats), f"{k(total)} lines of code written across four public projects")
    save("graph-tests-languages", tests_and_languages(stats), "Automated tests per project, and languages")
    save("header", header(), "Karunya Muddana, AI engineer. Open to AI/ML internships.")
    save("timeline", timeline(), "Timeline of work, releases and hackathons")
    save("upstream", upstream(fetch_prs()), "Pull requests merged into and in review at open-source libraries")
    for f in sorted(os.listdir(OUT)):
        print(f"{f:32s} {os.path.getsize(os.path.join(OUT, f)) / 1024:6.1f} KB")
