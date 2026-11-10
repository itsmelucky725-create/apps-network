import copy
import json
import tempfile
import unittest
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from scripts.build import LANGUAGES, ROOT, app_url, build, load_inputs, render, validate_url


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def matching(self, tag, **attrs):
        return [a for t, a in self.tags if t == tag and all(a.get(k) == v for k, v in attrs.items())]


class SiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = build(output=Path(cls.temp.name) / "site")
        cls.apps, cls.catalogs = load_inputs()
        cls.template = (ROOT / "index.html").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def pages(self):
        return sorted(self.output.rglob("*.html"))

    def test_six_pages_and_correct_html_language(self):
        self.assertEqual(len(self.pages()), 6)
        for page in self.pages():
            expected = "en" if page.parent == self.output else page.parent.name
            parsed = Page(page.read_text(encoding="utf-8"))
            self.assertEqual(parsed.matching("html")[0]["lang"], expected)
            title = self.catalogs[expected]["title"]
            decoded_html = unescape(page.read_text(encoding="utf-8"))
            self.assertIn(title, decoded_html)

    def test_every_language_links_to_all_five_locales(self):
        for page in self.pages():
            parsed = Page(page.read_text(encoding="utf-8"))
            links = [a for tag, a in parsed.tags if tag == "a" and "data-locale" in a]
            self.assertEqual({a["data-locale"] for a in links}, set(LANGUAGES))
            self.assertEqual(len(links), 5)
            self.assertEqual(len([a for a in links if a.get("aria-current") == "page"]), 1)
            for a in links:
                self.assertEqual((page.parent / a["href"]).resolve(), (self.output / a["data-locale"]).resolve())
                self.assertEqual(a["hreflang"], a["data-locale"])

    def test_dropdown_values_match_language_links(self):
        for page in self.pages():
            parsed = Page(page.read_text(encoding="utf-8"))
            options = parsed.matching("option")
            links = [a for tag, a in parsed.tags if tag == "a" and "data-locale" in a]
            self.assertEqual({o["value"] for o in options}, {a["href"] for a in links})
            selected = [o for o in options if "selected" in o]
            current = [a for a in links if a.get("aria-current") == "page"]
            self.assertEqual(len(selected), 1)
            self.assertEqual(selected[0]["value"], current[0]["href"])

    def test_all_internal_urls_exist_and_fragments_resolve(self):
        for page in self.pages():
            parsed = Page(page.read_text(encoding="utf-8"))
            for tag, attrs in parsed.tags:
                for key in ("href", "src"):
                    if key not in attrs:
                        continue
                    url = urlsplit(attrs[key])
                    if url.scheme or url.netloc:
                        self.assertEqual(url.scheme, "https")
                        continue
                    self.assertFalse(url.path.startswith("/"), (page, attrs))
                    target = (page.parent / unquote(url.path)).resolve() if url.path else page
                    if target.is_dir(): target = target / "index.html"
                    self.assertTrue(target.is_relative_to(self.output.resolve()))
                    self.assertTrue(target.is_file(), (page, attrs))
                    if url.fragment:
                        ids = [a.get("id") for _, a in Page(target.read_text(encoding="utf-8")).tags]
                        self.assertIn(url.fragment, ids)

    def test_metadata_is_localized(self):
        for lang in LANGUAGES:
            page = Page((self.output / lang / "index.html").read_text(encoding="utf-8"))
            self.assertEqual(page.matching("meta", name="description")[0]["content"], self.catalogs[lang]["description"])
            alternates = page.matching("link", rel="alternate")
            self.assertEqual({a["hreflang"] for a in alternates}, set(LANGUAGES) | {"x-default"})

    def test_unconfigured_apps_are_pending_not_fake_links(self):
        for page in self.pages():
            parsed = Page(page.read_text(encoding="utf-8"))
            pending = [a for _, a in parsed.tags if a.get("data-link-status") == "pending"]
            lang = parsed.matching("html")[0]["lang"]
            expected_pending = {a["id"] for a in self.apps if not app_url(a, lang)}
            self.assertEqual({a["data-app-id"] for a in pending}, expected_pending)
            linked = {a["data-app-id"]: a["href"] for tag, a in parsed.tags if tag == "a" and "data-app-id" in a}
            self.assertEqual(linked, {a["id"]: app_url(a, lang) for a in self.apps if app_url(a, lang)})
            self.assertFalse(any(a.get("href") in ("", "#") for _, a in parsed.tags if "href" in a))

    def test_app_urls_use_exact_explicit_locale_override_or_canonical_fallback(self):
        app = {"id": "app-one", "name": "App One", "url": "https://app-one.invalid/start?source=network&mode=full", "localized_urls": {"ja": "https://app-one.invalid/japanese/"}}
        for lang in LANGUAGES:
            expected = app["localized_urls"].get(lang) or app["url"]
            self.assertEqual(app_url(app, lang), expected)
            parsed = Page(render(self.template, lang, self.catalogs, [app], "../"))
            self.assertEqual(parsed.matching("a", **{"data-app-id": "app-one"})[0]["href"], expected)
            self.assertFalse(parsed.matching("span", **{"data-link-status": "pending"}))

    def test_unsafe_urls_rejected(self):
        for url in ("javascript:alert(1)", "http://app.invalid/", "/app/", "https://user:password@app.invalid", "https://app.invalid/\n", "https://app.invalid/\\other", ""):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url(url)
        validate_url(None)
        validate_url("https://app.invalid/path?lang=ja")

    def test_missing_or_empty_translations_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "languages").mkdir()
            (root / "apps.json").write_text(json.dumps(self.apps), encoding="utf-8")
            for lang, catalog in self.catalogs.items():
                (root / "languages" / f"{lang}.json").write_text(json.dumps(catalog), encoding="utf-8")
            for key in ("language_label", "app_descriptions"):
                broken = copy.deepcopy(self.catalogs["en"])
                del broken[key]
                (root / "languages/en.json").write_text(json.dumps(broken), encoding="utf-8")
                with self.assertRaises(ValueError): load_inputs(root)
            broken = copy.deepcopy(self.catalogs["en"])
            broken["pending_link"] = ""
            (root / "languages/en.json").write_text(json.dumps(broken), encoding="utf-8")
            with self.assertRaises(ValueError): load_inputs(root)

    def test_generated_json_aliases_match_and_build_info_is_honest(self):
        for lang in LANGUAGES:
            self.assertEqual(json.loads((self.output / f"{lang}.json").read_text()), self.catalogs[lang])
            self.assertEqual(json.loads((self.output / "languages" / f"{lang}.json").read_text()), self.catalogs[lang])
        info = json.loads((self.output / "build-info.json").read_text())
        self.assertEqual(info["languages"], list(LANGUAGES))
        self.assertEqual(set(info["pending_apps"]), {a["id"] for a in self.apps if any(not app_url(a, lang) for lang in LANGUAGES)})

    def test_names_and_translations_are_html_escaped(self):
        apps = [{"id": "app-one", "name": '<img src=x onerror="alert(1)">', "url": None}]
        text = render(self.template, "en", self.catalogs, apps, "../")
        self.assertFalse(Page(text).matching("img"))
        self.assertIn("&lt;img", text)


if __name__ == "__main__":
    unittest.main()
