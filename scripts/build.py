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


# ─────────────────────────────── project cards ───────────────────────────────
# Laid out like GitHub's pinned repositories. The drawing on each card uses real
# content from that repo (tool names, test cases, a saved run), never sample data.
def card(name, desc, footer, draw):
    def build(theme):
        s = Svg(412, 236, theme)
        s.rect(.5, .5, 411, 235, rx=8, fill="panel", stroke="border")
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
        s.rect(cx - w / 2 + .5, cy - 17.5, w, 35, rx=6, fill="canvas", stroke="border")
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
        s.rect(.5, .5, 839, 195, rx=12, fill="panel", stroke="border")
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
    for f in sorted(os.listdir(OUT)):
        print(f"{f:32s} {os.path.getsize(os.path.join(OUT, f)) / 1024:6.1f} KB")
