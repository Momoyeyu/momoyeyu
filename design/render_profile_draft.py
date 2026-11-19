#!/usr/bin/env python3
"""Render a complete README draft in the Winter score direction."""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from render_candidates import Canvas, CONTENT_X, CONTENT_TOP, PALETTES, base

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "scripts"))
import generate_profile

NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)
CELLS = {
    "light": ["#e2eaf2", "#c1d2e3", "#9db6d0", "#7f9fbe", "#5d82a5"],
    "dark": ["#23384c", "#3b5873", "#5c7c9e", "#8aa8c6", "#b7cbe0"],
}


def prompt(canvas, command, y=CONTENT_TOP, size=10, x=CONTENT_X):
    cw = size * .6
    for label, color, family in [("momoyeyu@winter", "lilac", "bold"), ("➜", "mint", "mono"), ("~", "blue", "mono")]:
        canvas.text(label, x, y, size, color, family=family)
        x += canvas.measure(label, size, family) + cw
    canvas.text(command, x, y, size, "text")


def directory_text(canvas, text, x, y, size, highlight=False):
    family = "bold" if highlight else "mono"
    if highlight:
        width = canvas.measure(text, size, family)
        opacity = .11 if canvas.theme == "light" else .16
        canvas.rect(x - 5, y - size * 1.15, width + 10, size + 7, "lilac", 3, extra=f' opacity="{opacity}"')
    canvas.text(text[:-1], x, y, size, "blue", family=family)
    canvas.text("/", x + canvas.measure(text[:-1], size, family), y, size, "gold", family=family)
    return canvas.measure(text, size, family)


def workspace(theme):
    c = Canvas("winter-score", theme, 350)
    base(c, 12, "momoyeyu@winter — workspace", snow=False)
    prompt(c, "ls ~/focus")
    entries = [
        ("agent-harness/", "tools / context / evaluation"),
        ("ai-infra/", "serving / efficiency / scale"),
        ("post-training/", "SFT / RL / alignment"),
    ]
    for i, (name, detail) in enumerate(entries):
        y = 104 + i * 25
        directory_text(c, name, 58, y, 12, highlight=True)
        c.text(detail, 288, y, 10, "muted")
    prompt(c, "ls ~/tools", y=185)
    x = 58
    for tool in ["python/", "go/", "ts/", "react/", "tauri/", "electron/", "linux/", "docker/", "git/"]:
        x += directory_text(c, tool, x, 214, 11) + c.measure("  ", 11)
    prompt(c, "cat ~/offline.txt", y=250)
    c.text("sport: 乒乓球 / 骑行 / 露营", 58, 280, 12, "text")
    c.text("music: 古典吉他 / 指弹 / 电吉他", 58, 305, 11, "muted")
    c.text("Code, then play.  ♪", 58, 329, 12, "gold", family="serif")
    return c.finish("Agent Harness, AI Infra, Post-training. Python, Go, TypeScript, React, Tauri, Electron, Linux, Docker, Git. sport: 乒乓球、骑行、露营. music: 古典吉他、指弹、电吉他. Code, then play.")


def recolor(svg, theme):
    old = generate_profile.PALETTES[theme]
    new = PALETTES["shell"][theme]
    replacements = {
        old["ink"]: new["text"], old["muted"]: new["muted"], old["line"]: new["line"],
        old["paper"]: new["paper"], old["wash"]: new["paper"],
        "#7188a2": new["blue"], "#748ba3": new["blue"], "#6582a1": new["blue"],
        "#94aac4": new["blue"], "#99adc2": new["blue"], "#d6b67c": new["gold"],
        "#726789": new["lilac"], "#9e94b3": new["lilac"],
    }
    replacements.update(zip(old["cells"], CELLS[theme]))
    for before, after in replacements.items():
        svg = svg.replace(before, after)
    return svg


def vectorize_text(svg, canvas):
    root = ET.fromstring(svg)
    for node in list(root.iter(f"{{{NS}}}text")):
        x, y = float(node.attrib.get("x", 0)), float(node.attrib.get("y", 0))
        size = float(node.attrib.get("font-size", 12))
        family = "bold" if int(node.attrib.get("font-weight", 400)) >= 600 else "mono"
        value = node.text or ""
        anchor = node.attrib.get("text-anchor", "start")
        if anchor == "middle":
            x -= canvas.measure(value, size, family) / 2
        elif anchor == "end":
            x -= canvas.measure(value, size, family)
        uses = []
        for char in value:
            use, advance = canvas.glyph(char, x, y, size, family)
            uses.append(use)
            x += advance
        fill = node.attrib.get("fill", "var(--ink)")
        fill = {"var(--ink)": canvas.color("text"), "var(--muted)": canvas.color("muted")}.get(fill, fill)
        group = ET.fromstring(f'<g fill="{fill}">{"".join(uses)}</g>')
        group.tail = node.tail
        parent = next(parent for parent in root.iter() if node in list(parent))
        parent.insert(list(parent).index(node), group)
        parent.remove(node)
    return "".join(ET.tostring(child, encoding="unicode") for child in root)


def github(data, theme):
    c = Canvas("winter-score", theme, 427)
    base(c, 12, "momoyeyu@winter — github", snow=False)
    summary = data["summary"]
    as_of = generate_profile.date.fromisoformat(data["asOf"])
    year = data["asOf"][:4]
    c.text("On GitHub", CONTENT_X, CONTENT_TOP, 13, "text", family="bold")
    c.text(f"{year} · 截至 {as_of.month:02d}/{as_of.day:02d}", 754, CONTENT_TOP, 9, "muted", "end")
    prompt(c, f"git stats --year={year}", y=98)
    if summary["currentStart"]:
        start, end = map(generate_profile.date.fromisoformat, [summary["currentStart"], summary["currentEnd"]])
        span = f"{generate_profile.calendar.month_abbr[start.month]} {start.day:02d} – {generate_profile.calendar.month_abbr[end.month]} {end.day:02d}"
    else:
        span = "No active streak"
    stats = [
        (f'{summary["total"]:,}', "Contributions", year),
        (summary["currentStreak"], "Current streak", span),
        (summary["longestStreak"], "Longest streak", f"in {year}"),
    ]
    for center, (value, label, foot) in zip([161, 394, 627], stats):
        c.text(value, center, 140, 24, "text", "middle", "bold")
        c.text(label, center, 165, 11, "muted", "middle")
        c.text(foot, center, 185, 9, "muted", "middle")
    prompt(c, f"git trail --year={year}", y=225)
    root = ET.fromstring(recolor(generate_profile.render_snake(data, theme), theme))
    for child in list(root):
        if child.tag == f"{{{NS}}}rect" and child.attrib.get("x") in {".5", "0.5", "21"}:
            root.remove(child)
        elif child.tag == f"{{{NS}}}text" and float(child.attrib.get("y", 100)) <= 30:
            root.remove(child)
    body = vectorize_text(ET.tostring(root, encoding="unicode"), c)
    c.add(f'<g transform="translate(24 192) scale({740 / 788:.6f} 1)">{body}</g>')
    return c.finish(f"On GitHub: {summary['total']} contributions, current streak {summary['currentStreak']}, longest streak {summary['longestStreak']}. Contribution trail through {data['asOf']}.")


def picture(file, alt, badge=False):
    stem = file[:-4]
    size = 'height="32" align="middle"' if badge else 'width="788"'
    return f'<picture><source media="(prefers-color-scheme: dark)" srcset="{stem}-dark.svg?draft=11"><img src="{stem}-light.svg?draft=11" {size} alt="{alt}"></picture>'


def preview(as_of):
    badges = [
        ("blog", "https://momoyeyu.github.io/", "Blog: 文字与碎片"),
        ("red", "https://www.xiaohongshu.com/user/profile/66c0ce98000000001d033f82", "小红书: 日常手记"),
        ("bilibili", "https://space.bilibili.com/171878754", "bilibili: 墨末夜羽"),
    ]
    links = "&nbsp;".join(f'<a href="{url}" target="_blank" rel="noreferrer">{picture(f"candidates/badge-winter-score-{slug}.svg", alt, True)}</a>' for slug, url, alt in badges)
    sections = [
        picture("candidates/winter-score.svg", "Momoyeyu · 墨末夜羽 · AI Systems Engineer"),
        f'<p align="center" class="badges">{links}</p>',
        '<p align="center">关注 <strong>AI 的成本与性能</strong>，从模型能力到系统落地。</p>',
        '<p align="center">曾在 <strong>宇宙厂</strong> 与 <strong>某明星初创</strong> 实习，做过基础设施与 Agent 产品。</p>',
        picture("profile/workspace.svg", "Focus directories, programming tools and offline interests"),
        picture("profile/github.svg", "GitHub statistics and an animated contribution trail"),
    ]
    body = "\n".join(f'<p align="center" class="art">{part}</p>' if part.startswith("<picture>") else part for part in sections)
    return '''<!doctype html>
<html lang="zh-CN" data-theme="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Momoyeyu · 冬日乐谱整页草案</title>
<style>
:root{color-scheme:light;--bg:#f5f8fc;--text:#334d68;--muted:#7c92aa;--line:#d0dfec;--button:#e5edf6}:root[data-theme="dark"]{color-scheme:dark;--bg:#0d1117;--text:#d4e3f2;--muted:#91a8c1;--line:#3b536d;--button:#203247}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif}main{width:788px;max-width:100%;margin:0 auto;padding:0 0 28px}.toolbar{display:flex;justify-content:center;align-items:center;gap:8px;padding:18px 12px 22px;font-size:11px;color:var(--muted)}button,a.control{font:inherit;font-size:11px;color:var(--text);background:var(--button);border:1px solid var(--line);border-radius:5px;padding:6px 10px;cursor:pointer;text-decoration:none}button:focus-visible,a:focus-visible{outline:2px solid #a58bb9;outline-offset:3px}.art{margin:16px 0}.art img{display:block;max-width:100%;height:auto}.badges{line-height:36px}.badges img{display:inline-block;border:0}.draft-note{text-align:center;color:var(--muted);font-size:10px;line-height:1.8;border-top:1px solid var(--line);padding:18px 14px 0;margin-top:25px}@media(max-width:800px){main{padding-left:8px;padding-right:8px}.toolbar{flex-wrap:wrap}}
</style></head><body>
<nav class="toolbar" aria-label="草案预览控制"><span>整页 draft · 未修改线上 README</span><button id="theme" type="button">深色</button><button id="replay" type="button">重播</button><a class="control" href="header-canvas.html">对照头部方案</a></nav>
<main>__BODY__<footer class="draft-note">实际 &lt;picture&gt;&lt;img&gt; 预览 · 全矢量文字与图形<br>贡献数据使用本地快照，截至 __AS_OF__；正式定稿时接回每日更新。</footer></main>
<script>
let dark=false;const button=document.querySelector('#theme');
function theme(){document.documentElement.dataset.theme=dark?'dark':'light';document.querySelectorAll('picture source').forEach(s=>s.media=dark?'all':'not all');button.textContent=dark?'浅色':'深色';button.setAttribute('aria-pressed',String(dark))}
document.querySelector('#theme').addEventListener('click',()=>{dark=!dark;theme()});
document.querySelector('#replay').addEventListener('click',()=>{document.querySelectorAll('picture').forEach(p=>{const s=p.querySelector('source'),i=p.querySelector('img');s.srcset=s.srcset.split('?')[0]+'?replay='+Date.now();i.src=i.src.split('?')[0]+'?replay='+Date.now()})});
document.addEventListener('keydown',e=>{if(e.ctrlKey||e.metaKey||e.altKey)return;if(e.key.toLowerCase()==='t'){dark=!dark;theme()}if(e.key.toLowerCase()==='r')document.querySelector('#replay').click()});theme();
</script></body></html>
'''.replace("__BODY__", body).replace("__AS_OF__", as_of)


def validate():
    for path in (ROOT / "profile").glob("*.svg"):
        root = ET.parse(path).getroot()
        assert root.attrib["width"] == "788", path
        assert not root.findall(f".//{{{NS}}}text"), path
        assert not root.findall(f".//{{{NS}}}script"), path
        assert not root.findall(f".//{{{NS}}}image"), path
        for use in root.findall(f".//{{{NS}}}use"):
            ref = use.attrib["href"][1:]
            assert root.find(f'.//*[@id="{ref}"]') is not None, (path, ref)


def main():
    data = json.loads((REPO / "data/contributions.json").read_text())
    dest = ROOT / "profile"
    dest.mkdir(exist_ok=True)
    for name in ["focus", "tools", "stats", "snake", "offline"]:
        for theme in ["light", "dark"]:
            (dest / f"{name}-{theme}.svg").unlink(missing_ok=True)
    for theme in ["light", "dark"]:
        assets = {
            "workspace": workspace(theme),
            "github": github(data, theme),
        }
        for name, svg in assets.items():
            (dest / f"{name}-{theme}.svg").write_text(svg)
    validate()
    (ROOT / "profile-draft.html").write_text(preview(data["asOf"]))
    print(f"Rendered the complete README draft with local data through {data['asOf']}.")


if __name__ == "__main__":
    main()
