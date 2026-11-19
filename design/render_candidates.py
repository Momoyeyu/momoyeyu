#!/usr/bin/env python3
"""Render original header candidates as self-contained, GitHub-safe SVG images."""
import os
import re
from pathlib import Path
from urllib.request import urlopen
from xml.sax.saxutils import escape

try:
    import pyfiglet
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont
except ImportError as error:
    raise SystemExit("This design tool needs fonttools and pyfiglet in an isolated Python environment.") from error

ROOT = Path(__file__).resolve().parent
FONT_DIR = Path(os.environ.get("FONT_CACHE", ROOT.parent / ".cache" / "fonts"))
FONT_BASE_URL = "https://raw.githubusercontent.com/google/fonts/47d54ca1ebb14fd864695f1d39dc734f39017c33/ofl/"
FONT_SOURCES = {
    "JetBrainsMono.ttf": "jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf",
    "SourceSerif4.ttf": "sourceserif4/SourceSerif4%5Bopsz,wght%5D.ttf",
    "NotoSansSC.ttf": "notosanssc/NotoSansSC%5Bwght%5D.ttf",
    "NotoSansSymbols2.ttf": "notosanssymbols2/NotoSansSymbols2-Regular.ttf",
    "NotoMusic.ttf": "notomusic/NotoMusic-Regular.ttf",
}
WIDTH = 788
DURATION = 16
CONTENT_X = 34
CONTENT_TOP = 70

PALETTES = {
    "shell": {
        "light": dict(paper="#edf3f9", panel="#e5edf6", text="#334d68", muted="#7c92aa", line="#d0dfec", blue="#6689ae", lilac="#9a85b1", gold="#c5a474", tag="#d7e5f2", shadow="#c4d3e3"),
        "dark": dict(paper="#182636", panel="#203247", text="#d4e3f2", muted="#91a8c1", line="#3b536d", blue="#b8cee6", lilac="#c6afd8", gold="#d7ba88", tag="#91abc7", shadow="#304961"),
    },
    "midnight": {
        "light": dict(paper="#edf2f8", panel="#e3ebf4", text="#293d58", muted="#8193ac", line="#c8d5e4", blue="#819bbc", lilac="#a990ba", gold="#bc9a6c", tag="#c5d5e7", shadow="#c8d5e4"),
        "dark": dict(paper="#142033", panel="#1d2e44", text="#e1e9f4", muted="#93a9c3", line="#384e6a", blue="#9db9d6", lilac="#c1a5cf", gold="#d2b783", tag="#b4c8e1", shadow="#30435e"),
    },
    "score": {
        "light": dict(paper="#f2f0f7", panel="#e7e6f0", text="#464b66", muted="#8a8da8", line="#cecbdd", blue="#87a6b9", lilac="#a491ba", gold="#b596aa", tag="#c9bfda", shadow="#cec9dd"),
        "dark": dict(paper="#202233", panel="#2a2e43", text="#e0e2f2", muted="#a3a9c2", line="#474c67", blue="#abcbd7", lilac="#c4abd5", gold="#c8a9c1", tag="#b9a7d0", shadow="#41465f"),
    },
}

PALETTES["winter-score"] = PALETTES["shell"]
for scheme in PALETTES.values():
    scheme["light"]["mint"] = "#91ab9c"
    scheme["dark"]["mint"] = "#a6c6b3"

FONT_SPECS = {
    "mono": ("JetBrainsMono.ttf", {"wght": 480}),
    "bold": ("JetBrainsMono.ttf", {"wght": 700}),
    "serif": ("SourceSerif4.ttf", {"wght": 500, "opsz": 40}),
    "cjk": ("NotoSansSC.ttf", {"wght": 480}),
    "symbol": ("NotoSansSymbols2.ttf", None),
    "music": ("NotoMusic.ttf", None),
}


def num(value):
    return f"{value:.3f}".rstrip("0").rstrip(".")


class Font:
    def __init__(self, filename, location):
        path = FONT_DIR / filename
        if not path.exists():
            FONT_DIR.mkdir(parents=True, exist_ok=True)
            print(f"Downloading {filename} from pinned Google Fonts sources", flush=True)
            with urlopen(FONT_BASE_URL + FONT_SOURCES[filename], timeout=90) as response:
                data = response.read()
            temporary = path.with_suffix(".part")
            temporary.write_bytes(data)
            temporary.replace(path)
        self.tt = TTFont(path, lazy=True)
        self.cmap = self.tt.getBestCmap()
        self.upm = self.tt["head"].unitsPerEm
        self.glyphs = self.tt.getGlyphSet(location=location) if location else self.tt.getGlyphSet()


FONTS = {}


def resolve(char, family="mono"):
    order = [family, "mono", "cjk", "symbol"] if family == "serif" else [family, "cjk", "symbol"]
    for key in dict.fromkeys(order):
        if key not in FONTS:
            FONTS[key] = Font(*FONT_SPECS[key])
        font = FONTS[key]
        if ord(char) in font.cmap:
            return key, font, font.cmap[ord(char)]
    raise ValueError(f"No glyph for {char!r} (U+{ord(char):04X})")


class Canvas:
    def __init__(self, variant, theme, height=326):
        self.variant, self.theme = variant, theme
        self.p = PALETTES[variant][theme]
        self.w, self.h = WIDTH, height
        self.body, self.styles, self.defs = [], [], {}

    def add(self, markup):
        self.body.append(markup)

    def style(self, css):
        self.styles.append(css)

    def color(self, role):
        return self.p.get(role, role)

    def rect(self, x, y, w, h, fill, rx=0, extra=""):
        self.add(f'<rect x="{num(x)}" y="{num(y)}" width="{num(w)}" height="{num(h)}" rx="{num(rx)}" fill="{self.color(fill)}"{extra}/>')

    def line(self, x1, y1, x2, y2, color="line", width=1, extra=""):
        self.add(f'<path d="M{num(x1)} {num(y1)}H{num(x2)}" fill="none" stroke="{self.color(color)}" stroke-width="{width}"{extra}/>')

    def glyph(self, char, x, y, size, family="mono"):
        key, font, name = resolve(char, family)
        scale = size / font.upm
        gid = f'{key}-{re.sub(r"[^a-zA-Z0-9_-]", "_", name)}-{int(size * 10)}'
        if gid not in self.defs:
            pen = SVGPathPen(font.glyphs, ntos=num)
            font.glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, 0, 0)))
            self.defs[gid] = f'<path id="{gid}" d="{pen.getCommands()}"/>'
        advance = font.glyphs[name].width * scale
        return f'<use href="#{gid}" x="{num(x)}" y="{num(y)}"/>', advance

    def measure(self, text, size, family="mono"):
        return sum(self.glyph(char, 0, 0, size, family)[1] for char in text)

    def text(self, text, x, y, size=12, fill="text", anchor="start", family="mono", extra=""):
        text = str(text)
        if anchor == "middle":
            x -= self.measure(text, size, family) / 2
        elif anchor == "end":
            x -= self.measure(text, size, family)
        uses = []
        for char in text:
            use, advance = self.glyph(char, x, y, size, family)
            uses.append(use)
            x += advance
        self.add(f'<g fill="{self.color(fill)}"{extra}>{"".join(uses)}</g>')

    def terminal(self, command, output, x, y, size=12, accent="lilac", anchor="start"):
        cw = size * .6
        prefix_width = self.measure("momoyeyu@winter", size, "bold") + self.measure("➜", size) + self.measure("~", size) + cw * 3
        if anchor == "middle":
            x -= (prefix_width + len(command) * cw) / 2
        cursor = x
        for label, color, family in [("momoyeyu@winter", "lilac", "bold"), ("➜", "mint", "mono"), ("~", "blue", "mono")]:
            self.text(label, cursor, y, size, color, family=family)
            cursor += self.measure(label, size, family) + cw
        command_x = x + prefix_width
        for index, char in enumerate(command):
            start = .6 + index * .065
            end = DURATION * .81
            cls = f"typed-{self.variant}-{index}"
            self.style(f'@keyframes {cls}{{0%,{start / DURATION * 100:.3f}%{{opacity:0}}{(start + .01) / DURATION * 100:.3f}%,{end / DURATION * 100:.3f}%{{opacity:1}}{(end + .01) / DURATION * 100:.3f}%,100%{{opacity:0}}}}.{cls}{{opacity:0;animation:{cls} {DURATION}s step-end infinite}}')
            use, _ = self.glyph(char, command_x + index * cw, y, size)
            self.add(f'<g class="{cls}" fill="{self.color("text")}">{use}</g>')
            cursor_end = start + .065 if index + 1 < len(command) else end
            cursor_cls = f"cursor-{self.variant}-{index}"
            self.style(f'@keyframes {cursor_cls}{{0%,{start / DURATION * 100:.3f}%{{opacity:0}}{(start + .01) / DURATION * 100:.3f}%,{cursor_end / DURATION * 100:.3f}%{{opacity:1}}{(cursor_end + .01) / DURATION * 100:.3f}%,100%{{opacity:0}}}}.{cursor_cls}{{opacity:0;animation:{cursor_cls} {DURATION}s step-end infinite}}')
            self.add(f'<g class="{cursor_cls}"><rect class="cursor" x="{num(command_x + (index + 1) * cw + 1)}" y="{num(y - size + 2)}" width="{num(cw)}" height="{num(size + 2)}" fill="{self.color(accent)}"/></g>')
        self.add(f'<g class="motion response">{self.capture_text(output, command_x, y + 26, size - 1, "muted")}</g>')
        self.add(f'<g class="reduced">{self.capture_text(command, command_x, y, size, "text")}{self.capture_text(output, command_x, y + 26, size - 1, "muted")}</g>')

    def capture_text(self, text, x, y, size, fill, anchor="start", family="mono"):
        self.text(text, x, y, size, fill, anchor, family)
        return self.body.pop()

    def feather(self, x, y, scale=1):
        shape = "M542 77C534 48 560 20 599 20C596 51 573 73 542 77Z"
        shaft = "M524 92C553 74 572 48 599 20"
        veins = "M549 71V48M560 61L563 37M572 49L580 29M559 62L579 58M548 71L564 69M580 40L590 38"
        self.add(f'<g transform="translate({num(x)},{num(y)}) scale({num(scale)})" fill="none" stroke="{self.color("blue")}" stroke-width="1" stroke-linecap="round" opacity=".8"><path d="{shape}{shaft}{veins}"/>')
        for i, row in enumerate(["01 // + *", "10 // . :", "// + 01 *", ": . // +", "+ * 01 //"]):
            self.add(f'<g transform="translate(0,{i * 10})">{self.capture_text(row, 548, 39, 5.8, "blue")}</g>')
        self.add('</g>')

    def window(self, x, y, scale=1):
        self.add(f'<g transform="translate({num(x)},{num(y)}) scale({num(scale)})" shape-rendering="crispEdges"><path d="M0 89H94" stroke="{self.color("line")}"/><path d="M12 17H82V86H12Z" fill="{self.color("shadow")}"/><path d="M8 13H86V19H8Z" fill="{self.color("blue")}"/><path d="M18 23H76V75H18Z" fill="{self.color("gold")}" class="lamp"/><path d="M45 23H49V75M18 47H76V51" stroke="{self.color("blue")}" stroke-width="3"/><path d="M8 78H86V85H8Z" fill="{self.color("paper")}" stroke="{self.color("line")}"/><path d="M24 61H34V73H24Z" fill="{self.color("blue")}"/><path d="M61 64H69V73H61Z" fill="{self.color("lilac")}"/></g>')

    def chrome(self, title, right=None):
        for x, color in [(30, "#cfa4b3"), (50, "#d5c092"), (70, "#a4c3ac")]:
            self.add(f'<circle cx="{x}" cy="27" r="5" fill="{color}"/>')
        self.text(title, 394, 31, 11, "muted", "middle")
        if right:
            self.text(right, 754, 30, 8, "muted", "end")

    def snow(self, count=12):
        flake = "M0-4V4M-3.46-2 3.46 2M-3.46 2 3.46-2M0-4l-1 1M0-4l1 1M0 4l-1-1M0 4l1-1"
        for i in range(count):
            x = 42 + (i * 79) % 700
            y = 53 + (i * 37) % 178
            delay = -(i * 1.7)
            duration = 14 + i % 6
            scale = .65 + (i % 3) * .2
            color = "blue" if i % 2 else "lilac"
            self.add(f'<g transform="translate({x} {y}) scale({scale})"><g class="snow" style="animation-duration:{duration}s;animation-delay:{delay}s"><path d="{flake}" fill="none" stroke="{self.color(color)}" stroke-width=".8" stroke-linecap="round"/></g></g>')

    def finish(self, title):
        css = "".join(self.styles)
        css += '.snow{animation:snowfall 14s linear infinite}.lamp{animation:lamp 8s ease-in-out infinite}.cursor{animation:blink 1s step-end infinite}.response{opacity:0;animation:response 16s ease-in-out infinite}.reduced{display:none}@keyframes snowfall{0%{transform:translate(0,-9px) rotate(0deg);opacity:0}15%,65%{opacity:.55}100%{transform:translate(-18px,44px) rotate(140deg);opacity:0}}@keyframes lamp{50%{opacity:.7}}@keyframes blink{50%{opacity:0}}@keyframes response{0%,20%{opacity:0;transform:translateY(3px)}24%,80%{opacity:1;transform:translateY(0)}85%,100%{opacity:0;transform:translateY(0)}}@media(prefers-reduced-motion:reduce){*{animation:none!important}.motion{display:none!important}.reduced{display:inline!important}.snow{opacity:.45}}'
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{escape(title)}"><title>{escape(title)}</title><style>{css}</style><defs>{"".join(self.defs.values())}</defs>{"".join(self.body)}</svg>\n'


GLYPHS = {
    "M": ["█   █", "██ ██", "█ █ █", "█ █ █", "█   █", "█   █", "█   █"],
    "O": [" ███ ", "█   █", "█   █", "█   █", "█   █", "█   █", " ███ "],
    "Y": ["█   █", "█   █", " █ █ ", "  █  ", "  █  ", "  █  ", "  █  "],
    "E": ["█████", "█    ", "█    ", "████ ", "█    ", "█    ", "█████"],
    "U": ["█   █", "█   █", "█   █", "█   █", "█   █", "█   █", " ███ "],
}


def pixel_name(canvas, word, center, top, cell=9, row_height=12, split=False):
    width = (len(word) * 6 - 1) * cell
    left = center - width / 2
    paths = []
    for letter_index, letter in enumerate(word):
        color = "blue" if letter_index < 4 else "lilac"
        d = []
        for row, line in enumerate(GLYPHS[letter]):
            for col, pixel in enumerate(line):
                if pixel == "█":
                    x, y = left + (letter_index * 6 + col) * cell, top + row * row_height
                    d.append(f'M{num(x)} {num(y)}h{num(cell + .08)}v{num(row_height + .08)}h-{num(cell + .08)}Z')
        paths.append(f'<path d="{"".join(d)}" fill="{canvas.color(color)}"/>')
    if split:
        canvas.add(f'<g opacity=".2" transform="translate(2 2)">{"".join(paths)}</g>')
    canvas.add("".join(paths))


def figlet_name(canvas, word, center, top, size=10.5):
    rows = pyfiglet.figlet_format(word, font="ansi_shadow", width=200).rstrip().splitlines()
    cw, lh = size * .6, size * 1.32
    width = max(map(len, rows)) * cw
    left = center - width / 2
    gradient = f'name-gradient-{word.lower()}'
    canvas.defs[gradient] = f'<linearGradient id="{gradient}" gradientUnits="userSpaceOnUse" x1="{num(left)}" y1="0" x2="{num(left + width)}" y2="0"><stop offset="0" stop-color="{canvas.color("blue")}"/><stop offset="1" stop-color="{canvas.color("lilac")}"/></linearGradient>'
    blocks, shadows = [], []
    for row, line in enumerate(rows):
        for col, char in enumerate(line):
            x, y = left + col * cw, top + row * lh
            if char == "█":
                blocks.append(f'M{num(x)} {num(y)}h{num(cw + .08)}v{num(lh + .08)}h-{num(cw + .08)}Z')
            elif char != " ":
                use, _ = canvas.glyph(char, x, y + size * 1.02, size)
                shadows.append(use)
    canvas.add(f'<g fill="{canvas.color("muted")}" opacity=".72">{"".join(shadows)}</g>')
    canvas.add(f'<path d="{"".join(blocks)}" fill="url(#{gradient})"/>')


def base(canvas, radius=12, title="momoyeyu@winter — zsh", right=None, panel=False, snow=True):
    x, y, w, h, header = 10, 10, canvas.w - 20, canvas.h - 20, 34
    canvas.defs["window-shadow"] = f'<filter id="window-shadow" x="-6%" y="-8%" width="112%" height="125%"><feDropShadow dx="0" dy="4" stdDeviation="5" flood-color="{canvas.color("shadow")}" flood-opacity="{.18 if canvas.theme == "light" else .45}"/></filter>'
    canvas.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{canvas.color("paper")}" filter="url(#window-shadow)"/>')
    canvas.add(f'<path d="M{x} {y + header}V{y + 12}a12 12 0 0 1 12-12H{x + w - 12}a12 12 0 0 1 12 12V{y + header}Z" fill="{canvas.color("panel")}"/>')
    canvas.add(f'<path d="M{x} {y + header}H{x + w}" stroke="{canvas.color("line")}"/>')
    canvas.add(f'<rect x="{x + .5}" y="{y + .5}" width="{w - 1}" height="{h - 1}" rx="11.5" fill="none" stroke="{canvas.color("line")}"/>')
    canvas.chrome(title, right)
    if snow:
        canvas.snow()


def shell(theme):
    c = Canvas("shell", theme)
    base(c)
    c.text("Welcome back. A little winter, a little wonder.", 394, 59, 10, "muted", "middle")
    pixel_name(c, "MOMOYEYU", 394, 78, 9, 11, True)
    c.text("墨末夜羽  /  AI SYSTEMS ENGINEER", 394, 181, 11, "text", "middle")
    c.text("Making intelligence work efficiently.", 394, 205, 14, "text", "middle", "serif")
    c.text("ヾ(＾∇＾)  ❄", 394, 232, 15, "lilac", "middle")
    c.feather(-394, 110, .87)
    c.window(655, 115, .96)
    c.line(40, 250, 748, 250)
    c.terminal("kimi whoami", "agent harness  /  inference  /  post-training", CONTENT_X, 276, 11)
    c.text("exit 0", 735, 302, 9, "muted", "end")
    return c.finish("Momoyeyu · 墨末夜羽 · 浅冬终端")


def midnight(theme):
    c = Canvas("midnight", theme, 334)
    base(c, 4)
    for x, y, sx, sy in [(17, 54, 1, 1), (771, 54, -1, 1), (17, 316, 1, -1), (771, 316, -1, -1)]:
        c.add(f'<path d="M{x} {y + 9 * sy}V{y}H{x + 9 * sx}" fill="none" stroke="{c.color("muted")}"/>')
    c.text("Momoyeyu", 394, 101, 47, "text", "middle", "serif")
    c.text("(/˘◡˘)/  ❄", 394, 133, 16, "lilac", "middle")
    c.text("墨末夜羽  /  AI SYSTEMS ENGINEER", 394, 158, 10, "muted", "middle")
    c.text("Making intelligence work efficiently.", 394, 184, 15, "text", "middle", "serif")
    c.feather(-349, 60, .8)
    c.window(653, 55, .95)
    c.rect(48, 209, 692, 86, "panel", 4)
    c.line(48, 229, 740, 229)
    c.text("winter — zsh", 65, 222, 8, "muted")
    c.text("● online", 722, 222, 8, "gold", "end")
    c.terminal("kimi run ./make-ideas-fly", "a little intelligence, with care.", CONTENT_X, 254, 11)
    c.text("from the other side of the screen", 394, 318, 9, "muted", "middle", "serif")
    return c.finish("Momoyeyu · 墨末夜羽 · 雪夜信笺")


SNOWFLAKE = [
    "     .  |  .     ",
    "      \\ | /      ",
    "   . -- + -- .   ",
    "     \\ \\|/ /     ",
    "------  +  ------",
    "     / /|\\ \\     ",
    "   ´ -- + -- `   ",
    "      / | \\      ",
    "     ´  |  `     ",
]


def pitch_y(pitch):
    letter, octave = pitch[0], int(pitch[-1])
    steps = "CDEFGAB".index(letter) + (octave - 4) * 7
    return 272 - steps * 3.5


def music_note(canvas, x, pitch, duration, beamed=False):
    y = pitch_y(pitch)
    up = y >= 258
    stem_x = x + 3.5 if up else x - 3.5
    stem_y = y - 16 if up else y + 16
    canvas.add(f'<ellipse cx="{num(x)}" cy="{num(y)}" rx="3.8" ry="2.5" transform="rotate(-18 {num(x)} {num(y)})" fill="{canvas.color("lilac")}"/>')
    canvas.add(f'<path d="M{num(stem_x)} {num(y)}V{num(stem_y)}" stroke="{canvas.color("lilac")}" stroke-width="1.1"/>')
    if duration == "dq":
        canvas.add(f'<circle cx="{num(x + 7)}" cy="{num(y - 1)}" r=".9" fill="{canvas.color("lilac")}"/>')
    if not beamed and duration in {"8", "16"}:
        direction = 1 if up else -1
        for i in range(2 if duration == "16" else 1):
            flag_y = stem_y + direction * i * 4
            canvas.add(f'<path d="M{num(stem_x)} {num(flag_y)}q{direction * 7} {direction * 2} {direction * 5} {direction * 8}" fill="none" stroke="{canvas.color("lilac")}" stroke-width="1"/>')
    if y < 244:
        ledger_y = 237 if y <= 237 else 230
        canvas.add(f'<path d="M{num(x - 6)} {ledger_y}h12" stroke="{canvas.color("line")}"/>')
    return stem_x, stem_y, up


def music_stream(canvas):
    canvas.defs["phrase-fade-gradient"] = '<linearGradient id="phrase-fade-gradient" x1="0" x2="1"><stop offset="0" stop-color="white" stop-opacity="0"/><stop offset=".14" stop-color="white" stop-opacity="1"/><stop offset=".86" stop-color="white" stop-opacity="1"/><stop offset="1" stop-color="white" stop-opacity="0"/></linearGradient>'
    canvas.defs["phrase-mask"] = '<mask id="phrase-mask" maskUnits="userSpaceOnUse" x="144" y="228" width="500" height="64" style="mask-type:alpha"><rect x="144" y="228" width="500" height="64" fill="url(#phrase-fade-gradient)"/></mask>'
    phrases = [
        ("WHITE ALBUM PIANO · I", True, [("Eb5", "q"), ("C5", "8"), ("B4", "8"), ("Ab4", "8"), ("G4", "8"), ("C5", "q")], [(1, 2), (3, 4)]),
        ("WHITE ALBUM PIANO · II", True, [("D5", "dq"), ("B4", "8"), ("C5", "q"), ("Ab4", "q")], []),
        ("ぬくもり", False, [("D5", "8"), ("E5", "8"), ("F5", "8"), ("A5", "dq")], [(0, 1, 2)]),
    ]
    canvas.add('<g mask="url(#phrase-mask)"><g class="phrase-rail">')
    for y in [244, 251, 258, 265, 272]:
        canvas.add(f'<path d="M174 {y}H1494" stroke="{canvas.color("line")}" stroke-width=".65"/>')
    for repeat in range(2):
        for index, (title, flats, notes, beams) in enumerate(phrases):
            left = 174 + (repeat * 3 + index) * 220
            if flats:
                for x, y in [(left + 25, 260), (left + 32, 249.5), (left + 39, 263.5)]:
                    canvas.text("♭", x, y, 10, "muted")
            offsets = [48, 78, 98, 118, 138, 166] if len(notes) == 6 else [48, 82, 120, 157]
            beamed = {i for beam in beams for i in beam}
            stems = [music_note(canvas, left + offset, pitch, duration, i in beamed) for i, (offset, (pitch, duration)) in enumerate(zip(offsets, notes))]
            for beam in beams:
                points = [stems[i] for i in beam]
                (x1, y1, up), (x2, y2, _) = points[0], points[-1]
                canvas.add(f'<path d="M{num(x1)} {num(y1)}L{num(x2)} {num(y2)}" stroke="{canvas.color("lilac")}" stroke-width="1.5"/>')
                if any(notes[i][1] == "16" for i in beam):
                    offset = 3 if up else -3
                    canvas.add(f'<path d="M{num(x1)} {num(y1 + offset)}L{num(x2)} {num(y2 + offset)}" stroke="{canvas.color("lilac")}" stroke-width="1.2"/>')
            canvas.text(title, left + 96, 287, 9, "muted", "middle", "serif")
            canvas.text("✧", left + 207, 261, 9, "gold", "middle")
    canvas.add('</g></g>')
    canvas.style('.phrase-rail{transform:translateX(-660px);animation:phrase-stream 27s linear infinite}@keyframes phrase-stream{from{transform:translateX(-660px)}to{transform:translateX(0)}}@media(prefers-reduced-motion:reduce){.phrase-rail{animation:none;transform:translateX(-660px)}}')


def score(theme, variant="score"):
    c = Canvas(variant, theme)
    base(c, 12, "momoyeyu@winter", "utf-8 / tty01")
    c.terminal("kimi compose --season=winter", "", CONTENT_X, CONTENT_TOP, 10, "blue")
    if variant == "winter-score":
        figlet_name(c, "MOMO", 225, 82)
        figlet_name(c, "YEYU", 563, 82)
    else:
        pixel_name(c, "MOMO", 249, 93, 9, 11)
        pixel_name(c, "YEYU", 539, 93, 9, 11)
    for row, line in enumerate(SNOWFLAKE):
        for col, char in enumerate(line):
            if char == " ":
                continue
            x, y = 354 + col * 4.6, 96 + row * 11
            use, _ = c.glyph(char, x, y, 9)
            dx, dy = ((row * 7 + col * 3) % 11 - 5) * 4, ((row * 3 + col * 5) % 9 - 4) * 4
            delay = (row + col) * .05
            c.add(f'<g class="glyph-gather" style="--dx:{dx}px;--dy:{dy}px;animation-delay:{delay}s" fill="{c.color("blue")}">{use}</g>')
    c.style('.glyph-gather{opacity:0;animation:gather 16s ease-in-out infinite}@keyframes gather{0%{opacity:0;transform:translate(var(--dx),var(--dy))}12%,83%{opacity:1;transform:translate(0,0)}90%,100%{opacity:0;transform:translate(0,0)}}@media(prefers-reduced-motion:reduce){.glyph-gather{opacity:1;transform:none;animation:none}}')
    c.text("墨末夜羽  /  AI SYSTEMS ENGINEER", 394, 196, 11, "text", "middle")
    c.text("Code, then play.  (｡•̀◡-)✧", 394, 224, 14, "text", "middle", "serif")
    music_stream(c)
    c.text("softly, efficiently.", 394, 302, 10, "muted", "middle")
    title = "冬日乐谱" if variant == "winter-score" else "字符间奏"
    return c.finish(f"Momoyeyu · 墨末夜羽 · {title}")


ICONS = {
    "blog": '<path d="M2 13V6l5-4 5 4v7H2Zm3 0V8h4v5"/>',
    "red": '<path d="M3 1h8v12H3Zm3 0v12M1 4h2M1 7h2M1 10h2m8-6h2m-2 3h2m-2 3h2"/>',
    "bilibili": '<rect x="1" y="4" width="13" height="9" rx="3"/><path d="m4 1 2 3m4-3-2 3M5 7v2m5-2v2"/>',
}


def badge(slug, label, value, variant, theme):
    p = PALETTES[variant][theme]
    c = Canvas(variant, theme, 32)
    left = 27 + c.measure(label, 11) + 10
    right = c.measure(value + " ↗", 11) + 23
    width = left + right
    c.w = width
    c.rect(2 if variant == "score" else 0, 2 if variant == "score" else 0, width, 32, "shadow", 3)
    c.rect(0, 0, width, 32, "panel", 4 if variant != "score" else 1)
    c.add(f'<path d="M4 0H{num(left)}V32H4a4 4 0 0 1-4-4V4a4 4 0 0 1 4-4Z" fill="{p["tag"]}"/>')
    c.add(f'<g transform="translate(8 9)" fill="none" stroke="#293e56" stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round">{ICONS[slug]}</g>')
    c.text(label, 27, 21, 11, "#293e56")
    c.text(value + " ↗", left + 11, 21, 11, "text")
    title = f"{label}: {value}"
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{num(width)}" height="32" viewBox="0 0 {num(width)} 32" role="img" aria-label="{escape(title)}"><title>{escape(title)}</title><defs>{"".join(c.defs.values())}</defs>{"".join(c.body)}</svg>\n'


def validate():
    import xml.etree.ElementTree as ET
    for path in ROOT.glob("candidates/*.svg"):
        art = ET.parse(path).getroot()
        if not path.name.startswith("badge-"):
            assert art.attrib["width"] == "788", path
        assert not art.findall(".//{http://www.w3.org/2000/svg}image"), path
        assert not art.findall(".//{http://www.w3.org/2000/svg}script"), path
        assert not art.findall(".//{http://www.w3.org/2000/svg}foreignObject"), path
        for use in art.findall(".//{http://www.w3.org/2000/svg}use"):
            ref = use.attrib["href"][1:]
            assert art.find(f'.//*[@id="{ref}"]') is not None, (path, ref)
    for variant, themes in PALETTES.items():
        for theme, palette in themes.items():
            svg = (ROOT / "candidates" / f"{variant}-{theme}.svg").read_text()
            assert f'fill="{palette["paper"]}"' in svg, (variant, theme, "wrong palette")
    for theme in ["light", "dark"]:
        svg = (ROOT / "candidates" / f"winter-score-{theme}.svg").read_text()
        assert 'fill="url(#name-gradient-momo)"' in svg, theme
        assert 'fill="url(#name-gradient-yeyu)"' in svg, theme


def main():
    dest = ROOT / "candidates"
    dest.mkdir(exist_ok=True)
    for variant, render in [("shell", shell), ("midnight", midnight), ("score", score), ("winter-score", lambda theme: score(theme, "winter-score"))]:
        for theme in ["light", "dark"]:
            (dest / f"{variant}-{theme}.svg").write_text(render(theme))
            for slug, label, value in [("blog", "blog", "文字与碎片"), ("red", "red", "日常手记"), ("bilibili", "bilibili", "墨末夜羽")]:
                (dest / f"badge-{variant}-{slug}-{theme}.svg").write_text(badge(slug, label, value, variant, theme))
    validate()
    print("Rendered 8 README-safe headers and 24 vector social tags.")


if __name__ == "__main__":
    main()
