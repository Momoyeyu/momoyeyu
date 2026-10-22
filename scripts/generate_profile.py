#!/usr/bin/env python3
"""Render self-contained profile SVGs from GitHub's public contribution calendar."""
import argparse
import calendar
import json
import re
import time
from datetime import date, datetime, timedelta
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PALETTES = {
    "light": dict(paper="#ffffff", ink="#27394b", muted="#73869a", line="#dce4ee", wash="#f3f6fa", cells=["#e9eef5", "#c4d3e3", "#9fb6d0", "#7e9bb9", "#5c7b9d"]),
    "dark": dict(paper="#0d1117", ink="#d4dfea", muted="#8093a8", line="#2a3747", wash="#131e2b", cells=["#1c2b3b", "#334d68", "#516e8f", "#7998b9", "#a9c1d9"]),
}


class CalendarParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cells = {}
        self.tips = {}
        self.tip_id = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "data-date" in attrs and "data-level" in attrs:
            self.cells[attrs["id"]] = {"date": attrs["data-date"], "level": int(attrs["data-level"])}
        if tag == "tool-tip":
            self.tip_id = attrs.get("for")
            if self.tip_id:
                self.tips[self.tip_id] = ""

    def handle_data(self, data):
        if self.tip_id:
            self.tips[self.tip_id] += data

    def handle_endtag(self, tag):
        if tag == "tool-tip":
            self.tip_id = None

    def days(self, as_of):
        result = []
        for key, cell in self.cells.items():
            if not f"{as_of.year}-01-01" <= cell["date"] <= as_of.isoformat():
                continue
            tip = self.tips.get(key, "").strip()
            match = re.match(r"([\d,]+) contributions?\b", tip)
            if match:
                count = int(match[1].replace(",", ""))
            elif tip.startswith("No contributions"):
                count = 0
            else:
                raise ValueError(f"Missing or unrecognized contribution tooltip: {cell['date']}")
            if bool(count) != bool(cell["level"]):
                raise ValueError(f"Contribution level/count mismatch: {cell['date']}")
            result.append(dict(cell, count=count))
        result.sort(key=lambda d: d["date"])
        expected = (as_of - date(as_of.year, 1, 1)).days + 1
        if len(result) != expected or len({d["date"] for d in result}) != expected:
            raise ValueError(f"Incomplete calendar: expected {expected} unique dates, got {len(result)}")
        return result


def summarize(days):
    run = longest = 0
    longest_end = None
    for day in days:
        run = run + 1 if day["count"] else 0
        if run > longest:
            longest, longest_end = run, day["date"]
    # A day still in progress does not break yesterday's active streak.
    active = days if days[-1]["count"] else days[:-1]
    current = 0
    for day in reversed(active):
        if not day["count"]:
            break
        current += 1
    end = date.fromisoformat(active[-1]["date"]) if active and current else None
    return dict(total=sum(d["count"] for d in days), currentStreak=current,
                longestStreak=longest, activeDays=sum(bool(d["count"]) for d in days),
                currentStart=(end - timedelta(days=current - 1)).isoformat() if end else None,
                currentEnd=end.isoformat() if end else None, longestEnd=longest_end)


def fetch_calendar(username, as_of):
    url = f"https://github.com/users/{username}/contributions?from={as_of.year}-01-01&to={as_of.isoformat()}"
    for attempt in range(3):
        try:
            req = Request(url, headers={"User-Agent": "Momoyeyu-profile/1.0", "Accept-Language": "en-US,en;q=0.9"})
            with urlopen(req, timeout=30) as response:
                parser = CalendarParser()
                parser.feed(response.read().decode("utf-8"))
            days = parser.days(as_of)
            return dict(source=url, asOf=as_of.isoformat(), days=days, summary=summarize(days))
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def text(x, y, value, size=12, color="var(--ink)", anchor=None, extra=""):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}"' + (f' text-anchor="{anchor}"' if anchor else '') + f' {extra}>{escape(str(value))}</text>'


def box(x, y, w, h, fill="none", stroke="var(--line)", radius=5):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>'


def svg(w, h, body, theme, styles=""):
    p = PALETTES[theme]
    tokens = ";".join(f"--{k}:{v}" for k, v in p.items() if k != "cells")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">
<style>:root{{{tokens}}}text{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,"PingFang SC",sans-serif}}{styles}</style>{body}</svg>'''


def render_header(theme, mobile=False):
    w, h = (360, 196) if mobile else (788, 214)
    art = (ROOT / "scripts/header-art.svg").read_text()
    art = re.sub(r"^<svg[^>]*>|</svg>$", "", art.strip())
    if mobile:
        art = re.sub(r'<g class="wing".*?</g>', '', art, flags=re.S)
        art = f'<g transform="translate(-208,55) scale(.7)">{art}</g>'
    x, y, size = (20, 59, 34) if mobile else (29, 72, 49)
    title = text(x, y, "Momoyeyu", size, extra='font-weight="600" letter-spacing="-2"')
    title += text(x, y + 30, "墨末夜羽", 13, "#7188a2", extra='letter-spacing="4"')
    title += text(x if mobile else x + 116, y + (49 if mobile else 30), "AI Systems Engineer", 10 if mobile else 12, "#748ba3")
    title += text(x, y + (78 if mobile else 97), "Making intelligence work efficiently.", 9 if mobile else 12, "#748ba3")
    for offset, width, color in [(0, 20, "#aec0d3"), (25, 11, "#c0b5cb"), (41, 6, "#d6b67c")]:
        title += box(x + offset, y + (91 if mobile else 115), width, 3, color, "none", 0)
    styles = '''.flurry{animation:snow 8s linear infinite}.two{animation-delay:-3s}.three{animation-delay:-6s}.wing{transform-origin:600px 40px;animation:wing 9s ease-in-out infinite}.window-light{animation:glow 9s ease-in-out infinite}@keyframes snow{0%{transform:translate(0,-7px);opacity:0}20%,70%{opacity:.9}100%{transform:translate(-5px,15px);opacity:0}}@keyframes wing{50%{transform:translateY(-2px) rotate(-2deg)}}@keyframes glow{50%{opacity:.65}}@media(prefers-reduced-motion:reduce){*{animation:none!important}}'''
    if theme == "dark":
        styles += '.scene-ground{fill:#30445a}'
    return svg(w, h, box(.5, .5, w-1, h-1, "var(--wash)") + '<g fill="none">' + art + '</g>' + title, theme, styles)


def render_focus(theme, mobile=False):
    w, h = (360, 138) if mobile else (788, 80)
    body = f'<path d="M0 .5H{w}M0 {h-.5}H{w}" stroke="var(--line)"/>'
    lanes = [("Agent Harness", "tools / context / evaluation", "#7e9bb9"), ("AI Infra", "serving / efficiency / scale", "#98a597"), ("Post-training", "SFT / RL / alignment", "#aa9fba")]
    for i, (name, detail, color) in enumerate(lanes):
        x, y = (0, 27+i*43) if mobile else (i*w/3 + (17 if i else 0), 33)
        if i and not mobile:
            body += f'<path d="M{i*w/3} 17V63" stroke="var(--line)"/>'
        body += box(x, y-9, 8, 8, "none", color, 1)
        body += text(x+19, y, name, 12 if mobile else 13, extra='font-weight="600"')
        body += text(w-2 if mobile else x, y if mobile else y+24, detail, 8.5 if mobile else 10, "var(--muted)", "end" if mobile else None)
    return svg(w, h, body, theme)


def render_tools(theme, mobile=False):
    tools = [("Py", "Python"), ("++", "C++"), ("Go", "Go"), ("◒", "PyTorch"), ("λ", "Linux"), ("▤", "Docker"), ("◇", "Git")]
    body, x, y = "", 0, 2
    for mark, label in tools:
        width = 35 + len(label)*5.5
        if mobile and x+width > 360:
            x, y = 0, 32
        body += box(x+.5, y, width, 23, "var(--paper)", radius=4)
        body += box(x+5, y+4, 15, 15, "var(--wash)", "none", 3)
        body += text(x+12.5, y+15, mark, 9, "#718ca8", "middle", 'font-weight="600"')
        body += text(x+25, y+15, label, 10, "var(--muted)")
        x += width+7
    return svg(360 if mobile else 788, 58 if mobile else 29, body, theme)


def render_stats(data, theme, mobile=False):
    w, h = (360, 178) if mobile else (788, 183)
    s, year = data["summary"], data["asOf"][:4]
    as_of = date.fromisoformat(data["asOf"])
    body = text(0, 15, "On GitHub", 13, extra='font-weight="600"') + text(w, 15, f"{year} · 截至 {as_of.month:02d}/{as_of.day:02d}", 8 if mobile else 10, "var(--muted)", "end")
    body += box(.5, 30.5, w-1, h-31, "var(--paper)")
    centers = [w/6, w/2, w*5/6]
    for x in [w/3, w*2/3]:
        body += f'<path d="M{x} 51V{h-23}" stroke="var(--line)"/>'
    for x, value, label, foot in [(centers[0], f'{s["total"]:,}', "Contributions", year), (centers[2], s["longestStreak"], "Longest streak", "in "+year)]:
        body += text(x, 107, value, 27 if mobile else 31, anchor="middle")
        body += text(x, 132, label, 9 if mobile else 11, "var(--muted)", "middle")
        body += text(x, 151, foot, 8 if mobile else 9, "var(--muted)", "middle")
    x = centers[0]
    body += f'<g stroke="#99adc2" fill="none" stroke-width="1.2" transform="translate({x-7},55)"><rect width="5" height="5" rx="1"/><rect x="8" width="5" height="5" rx="1"/><rect y="8" width="5" height="5" rx="1"/><rect x="8" y="8" width="5" height="5" rx="1"/></g>'
    x = centers[2]
    body += f'<path d="M{x-3} 55H{x+3}V59C{x+3} 64 {x-3} 64 {x-3} 59ZM{x-3} 56H{x-6}V58C{x-6} 61 {x-3} 61 {x-3} 61M{x+3} 56H{x+6}V58C{x+6} 61 {x+3} 61 {x+3} 61M{x} 63V67M{x-3} 67H{x+3}" stroke="#99adc2" fill="none" stroke-width="1.2"/>'
    cx = centers[1]
    body += f'<circle cx="{cx}" cy="91" r="29" fill="none" stroke="#94aac4" stroke-width="2"/><rect x="{cx-32}" y="88" width="6" height="6" rx="1" fill="#d6b67c" stroke="var(--paper)" stroke-width="2"/>'
    body += text(cx, 101, s["currentStreak"], 27, anchor="middle") + text(cx, 132, "Current streak", 9 if mobile else 11, "#6582a1", "middle")
    if s["currentStart"]:
        start, end = map(date.fromisoformat, [s["currentStart"], s["currentEnd"]])
        span = f"{calendar.month_abbr[start.month]} {start.day:02d} – {calendar.month_abbr[end.month]} {end.day:02d}"
    else:
        span = "No active streak"
    body += text(cx, 151, span, 7 if mobile else 9, "var(--muted)", "middle")
    return svg(w, h, body, theme)


def render_snake(data, theme):
    w, h, x0, y0 = 788, 225, 50, 65
    days = data["days"]
    first = date.fromisoformat(days[0]["date"])
    origin = first - timedelta(days=(first.weekday()+1) % 7)
    last = date.fromisoformat(days[-1]["date"])
    weeks = (last-origin).days//7+1
    step = min(16, (w-90)/weeks)
    cell = step*.75
    body = box(.5, .5, w-1, h-1, "var(--wash)")
    body += box(21, 24, 5, 5, "#d6b67c", "none", 1) + text(32, 30, "Contribution trail", 11)
    body += text(w-21, 30, f"Jan 01 — {calendar.month_abbr[last.month]} {last.day:02d}, {last.year}", 9, "var(--muted)", "end")
    styles = ''
    month = None
    for i, day in enumerate(days):
        d = date.fromisoformat(day["date"])
        col, row = divmod((d-origin).days, 7)
        x, y = x0+col*step, y0+row*step
        eat = (col*7+(6-row if col % 2 else row))/(weeks*7)*100
        anim = f' style="animation:eat{i} 34s linear infinite"' if day["count"] else ''
        body += f'<rect x="{x:.2f}" y="{y:.2f}" width="{cell:.2f}" height="{cell:.2f}" rx="2" fill="{PALETTES[theme]["cells"][day["level"]]}"{anim}><title>{day["date"]}: {day["count"]} contributions</title></rect>'
        if day["count"]:
            styles += f'@keyframes eat{i}{{0%,{max(0,eat-.12):.3f}%{{opacity:1}}{eat+.12:.3f}%,91%{{opacity:.17}}100%{{opacity:1}}}}'
        if d.month != month:
            month = d.month
            body += text(x, 53, calendar.month_abbr[month], 9, "var(--muted)")
    for label, row in [("M", 1), ("W", 3), ("F", 5)]:
        body += text(27, y0+row*step+9, label, 8, "var(--muted)")
    points = [(x0+col*step+cell/2, y0+(6-j if col % 2 else j)*step+cell/2) for col in range(weeks) for j in range(7)]
    path = 'M'+' L'.join(f'{x:.2f},{y:.2f}' for x,y in points)
    for i in range(6, -1, -1):
        fill = "#726789" if i == 0 else "#9e94b3"
        body += f'<rect class="snake" x="-5" y="-5" width="10" height="10" rx="2" fill="{fill}" opacity="{1-i*.07}"><animateMotion dur="34s" repeatCount="indefinite" path="{path}" begin="{-1-i*.095}s" calcMode="linear"/></rect>'
    body += text(21, h-17, "Keep building, one square at a time.", 9, "var(--muted)")
    body += text(w-124, h-17, "Less", 9, "var(--muted)")
    for i,color in enumerate(PALETTES[theme]["cells"]):
        body += box(w-98+i*10, h-24, 7, 7, color, "none", 1)
    body += text(w-21, h-17, "More", 9, "var(--muted)", "end")
    styles += '@media(prefers-reduced-motion:reduce){*{animation:none!important}.snake{display:none}}'
    return svg(w, h, body, theme, styles)


def write_assets(data):
    dest = ROOT / "assets"
    dest.mkdir(exist_ok=True)
    for theme in PALETTES:
        for mobile in [False, True]:
            suffix = f'{theme}{"-mobile" if mobile else ""}.svg'
            for name, value in [("header", render_header(theme, mobile)), ("focus", render_focus(theme, mobile)), ("tools", render_tools(theme, mobile)), ("stats", render_stats(data, theme, mobile))]:
                (dest / f'{name}-{suffix}').write_text(value+'\n')
        (dest / f'snake-{theme}.svg').write_text(render_snake(data, theme)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=date.fromisoformat, default=datetime.now(ZoneInfo("Asia/Shanghai")).date())
    parser.add_argument("--snapshot", type=Path, help="Render a previously saved public calendar without network access")
    args = parser.parse_args()
    if args.snapshot:
        data = json.loads(args.snapshot.read_text())
        data["asOf"] = data.get("asOf") or data["days"][-1]["date"]
        data["summary"] = summarize(data["days"])
    else:
        data = fetch_calendar("Momoyeyu", args.as_of)
    write_assets(data)
    dest = ROOT / "data"
    dest.mkdir(exist_ok=True)
    (dest / "contributions.json").write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    print(f'Rendered profile assets: {data["asOf"]}, {data["summary"]["total"]} contributions')


if __name__ == "__main__":
    main()
