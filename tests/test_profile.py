import sys
import re
import xml.etree.ElementTree as ET
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from generate_profile import CalendarParser, summarize


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


if __name__ == "__main__":
    unittest.main()
