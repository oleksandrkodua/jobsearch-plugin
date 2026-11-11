"""The README picture "the path of a vacancy" must not drift from the plugin.

Checks, without node or Minicharts:
- every command in plugins/jobsearch/commands/ is either a station of the chart or is
  listed in docs/img/vacancy-path.json with a reason for being left out;
- every station is drawn in the source and labelled in the SVG;
- the SVG was rebuilt after the last edit of its source (stored SHA-256);
- the README shows the picture.

When this fails after adding or renaming a command: update docs/img/vacancy-path.json
(and the drawing in docs/img/vacancy-path.js if the command is a step of a vacancy),
then run tools/build_vacancy_path.py.
"""
import hashlib
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "docs", "img")
COMMANDS = os.path.join(ROOT, "plugins", "jobsearch", "commands")


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return f.read()


DATA = json.loads(read(IMG, "vacancy-path.json"))
SOURCE = read(IMG, "vacancy-path.js")
SVG = read(IMG, "vacancy-path.svg")
STEPS = DATA["steps"]
LEFT_OUT = DATA["not_in_chart"]


class VacancyPathChart(unittest.TestCase):
    def test_every_command_is_a_station_or_left_out_with_a_reason(self):
        commands = {n[:-3] for n in os.listdir(COMMANDS) if n.endswith(".md")}
        self.assertEqual(set(STEPS) & set(LEFT_OUT), set())
        self.assertEqual(commands, set(STEPS) | set(LEFT_OUT))
        self.assertEqual(len(STEPS), len(set(STEPS)))
        for name, reason in LEFT_OUT.items():
            self.assertTrue(reason.strip(), name)

    def test_every_station_is_drawn_and_labelled(self):
        for name in STEPS + [DATA["manual_step"]]:
            self.assertIn(f"'{name}'", SOURCE, name)
            self.assertIn(f">{name.upper()}<", SVG, name)

    def test_stations_follow_the_documented_order(self):
        at = []
        for name in STEPS:
            m = re.search(r"jsfCap\(\d+,\d+,'%s'," % re.escape(name), SOURCE)
            self.assertIsNotNone(m, name)
            at.append(m.start())
        self.assertEqual(at, sorted(at))

    def test_svg_was_rebuilt_from_the_current_source(self):
        m = re.search(r'data-source-sha256="([0-9a-f]{64})"', SVG)
        self.assertIsNotNone(m, "run tools/build_vacancy_path.py")
        self.assertEqual(m.group(1), hashlib.sha256(SOURCE.encode("utf-8")).hexdigest(),
                         "docs/img/vacancy-path.js changed: run tools/build_vacancy_path.py")

    def test_svg_is_clean_and_says_the_data_is_synthetic(self):
        self.assertNotIn("NaN", SVG)
        self.assertNotIn("undefined", SVG)
        self.assertIn("synthetic data", SVG)
        self.assertIn(f"id:'{DATA['chart_id']}'", SOURCE)

    def test_readme_shows_the_picture(self):
        readme = read(ROOT, "README.md")
        self.assertIn("](docs/img/vacancy-path.svg)", readme)
        self.assertIn("tools/build_vacancy_path.py", readme)


if __name__ == "__main__":
    unittest.main()
