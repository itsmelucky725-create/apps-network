"""Pin real directory-listed products so placeholder launch links cannot regress."""
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from scripts.build import build, load_inputs

EXPECTED_PRODUCTS = {
    "app-one": ("AI Automation Platform", "https://ziontechgroup.com/apps/ai-automation-platform.html"),
    "app-two": ("Cloud Cost Optimizer", "https://ziontechgroup.com/apps/cloud-cost-optimizer.html"),
}
RETIRED_PATHS = {"/app-one", "/app-two"}


class LaunchLinks(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.links = {}
        self.text = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and "data-app-id" in attrs:
            self.links[attrs["data-app-id"]] = attrs["href"]

    def handle_data(self, data):
        self.text.append(data)


class ProductionLinkTests(unittest.TestCase):
    def test_registry_uses_selected_published_products(self):
        apps, _ = load_inputs()
        by_id = {app["id"]: app for app in apps}
        for app_id, (name, url) in EXPECTED_PRODUCTS.items():
            with self.subTest(app=app_id):
                self.assertEqual(by_id[app_id]["name"], name)
                self.assertEqual(by_id[app_id]["url"], url)

    def test_retired_placeholder_paths_are_not_launch_targets(self):
        apps, _ = load_inputs()
        for app in apps:
            targets = [app.get("url"), *app.get("localized_urls", {}).values()]
            for target in filter(None, targets):
                parsed = urlsplit(target)
                if parsed.hostname in {"ziontechgroup.com", "www.ziontechgroup.com"}:
                    self.assertNotIn(parsed.path.rstrip("/"), RETIRED_PATHS)

    def test_both_real_products_render_on_every_showcase_page(self):
        with tempfile.TemporaryDirectory() as temp:
            output = build(output=Path(temp) / "site")
            pages = sorted(output.rglob("*.html"))
            self.assertEqual(len(pages), 6)
            for page in pages:
                with self.subTest(page=str(page.relative_to(output))):
                    parsed = LaunchLinks(page.read_text(encoding="utf-8"))
                    visible_text = " ".join(parsed.text)
                    for app_id, (name, url) in EXPECTED_PRODUCTS.items():
                        self.assertEqual(parsed.links[app_id], url)
                        self.assertIn(name, visible_text)
                    self.assertNotIn("App One", visible_text)
                    self.assertNotIn("App Two", visible_text)


if __name__ == "__main__":
    unittest.main()
