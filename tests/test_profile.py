import sys
import re
import xml.etree.ElementTree as ET
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from generate_profile import CalendarParser, render_snake, summarize


class CalendarTests(unittest.TestCase):
    def test_future_dates_and_formatted_counts(self):
        parser = CalendarParser()
        parser.feed('''<td id="a" data-date="2026-01-01" data-level="4"></td>
        <tool-tip for="a">1,234 contributions on January 1st.</tool-tip>
        <td id="b" data-date="2026-01-02" data-level="0"></td>
        <tool-tip for="b">No contributions on January 2nd.</tool-tip>''')
        self.assertEqual(parser.days(date(2026, 1, 1)), [{"date": "2026-01-01", "level": 4, "count": 1234}])

    def test_missing_tooltip_is_not_silently_zero(self):
        parser = CalendarParser()
        parser.feed('<td id="a" data-date="2026-01-01" data-level="0"></td>')
        with self.assertRaises(ValueError):
            parser.days(date(2026, 1, 1))

    def test_missing_calendar_date_is_rejected(self):
        parser = CalendarParser()
        parser.feed('<td id="a" data-date="2026-01-02" data-level="0"></td><tool-tip for="a">No contributions on January 2nd.</tool-tip>')
        with self.assertRaises(ValueError):
            parser.days(date(2026, 1, 2))

    def test_unfinished_day_preserves_yesterday_streak(self):
        days = [{"date": f"2026-01-{i:02d}", "count": n} for i,n in enumerate([1, 2, 0, 3, 4, 5, 0], 1)]
        summary = summarize(days)
        self.assertEqual((summary["currentStreak"], summary["longestStreak"]), (3, 3))
        self.assertEqual((summary["currentStart"], summary["currentEnd"]), ("2026-01-04", "2026-01-06"))
        self.assertEqual(summary["total"], 15)
        self.assertEqual(summarize(days + [{"date": "2026-01-08", "count": 0}])["currentStreak"], 0)


class ArtworkLayoutTests(unittest.TestCase):
    def test_picture_sources_keep_the_same_scale(self):
        # GitHub can override theme media conditions for a signed-in theme.
        # Every selectable source must be safe at the fallback display width.
        root = Path(__file__).resolve().parents[1]
        for fragment in re.findall(r"<picture>.*?</picture>", (root / "README.md").read_text(), re.S):
            picture = ET.fromstring(re.sub(r"<(source|img)([^>]*?)/?>", lambda m: "<" + m[1] + m[2] + "/>", fragment))
            fallback = picture.find("img")
            displayed = float(fallback.attrib["width"])
            base = ET.parse(root / fallback.attrib["src"]).getroot()
            ratio = float(base.attrib["width"]) / float(base.attrib["height"])
            for source in picture.findall("source"):
                art = ET.parse(root / source.attrib["srcset"]).getroot()
                with self.subTest(source=source.attrib["srcset"]):
                    self.assertGreaterEqual(float(art.attrib["width"]), displayed)
                    self.assertAlmostEqual(float(art.attrib["width"]) / float(art.attrib["height"]), ratio)


class SnakeAnimationTests(unittest.TestCase):
    def test_contributions_dim_at_head_arrival_and_reset_after_tail(self):
        first = date(2026, 1, 1)
        days = [dict(date=(first + timedelta(days=i)).isoformat(), count=int(i != 2), level=int(i != 2))
                for i in range(14)]
        ns = {"svg": "http://www.w3.org/2000/svg"}

        for theme in ("light", "dark"):
            with self.subTest(theme=theme):
                art = ET.fromstring(render_snake({"days": days}, theme))
                snake = art.find('svg:g[@class="snake"]', ns)
                self.assertIsNotNone(snake)
                motions = snake.findall("svg:rect/svg:animateMotion", ns)
                self.assertEqual(len(motions), 7)
                head = motions[-1]
                route_id = head.find("svg:mpath", ns).attrib["href"][1:]
                path = art.find(f'.//svg:path[@id="{route_id}"]', ns)
                points = [(int(x), int(y)) for x, y in re.findall(r"(-?\d+),(-?\d+)", path.attrib["d"])]
                self.assertTrue(all(abs(x - nx) + abs(y - ny) == 1
                                    for (x, y), (nx, ny) in zip(points, points[1:])))
                _, head_start, head_end, _ = map(float, head.attrib["keyTimes"].split(";"))
                tail_end = head_end
                for motion in reversed(motions[:-1]):
                    _, start, end, _ = map(float, motion.attrib["keyTimes"].split(";"))
                    self.assertGreater(end, tail_end)
                    self.assertAlmostEqual(end - start, head_end - head_start, places=7)
                    tail_end = end

                tx, ty, step = map(float, re.findall(r"[\d.]+", snake.attrib["transform"]))
                cells = art.findall('svg:rect[@class="contribution"]', ns)
                self.assertEqual(len(cells), len(days))
                for day, rect in zip(days, cells):
                    with self.subTest(day=day["date"]):
                        x, y, size = (float(rect.attrib[attr]) for attr in ("x", "y", "width"))
                        col, row = (x + size/2 - tx)/step, (y + size/2 - ty)/step
                        self.assertAlmostEqual(col, round(col), places=3)
                        self.assertAlmostEqual(row, round(row), places=3)
                        progress = points.index((round(col), round(row))) / (len(points) - 1)
                        anim = rect.find('svg:animate[@attributeName="opacity"]', ns)
                        if not day["count"]:
                            self.assertIsNone(anim)
                            continue
                        arrive = head_start + progress * (head_end - head_start)
                        _, dim, dimmed, restore, restored, _ = map(float, anim.attrib["keyTimes"].split(";"))
                        self.assertAlmostEqual(dim, arrive, places=7)
                        self.assertLess(dim, dimmed)
                        self.assertLess(dimmed, restore)
                        self.assertGreaterEqual(restore, tail_end)
                        self.assertLess(restore, restored)
                        self.assertLess(restored, 1)
                        for attr in ("dur", "repeatCount", "begin"):
                            self.assertEqual(anim.get(attr), head.get(attr))


if __name__ == "__main__":
    unittest.main()
