"""Build a dependency-free, localized static site for GitHub project Pages."""
import argparse
import json
import os
import re
import shutil
from html import escape
from pathlib import Path
from string import Template
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = {"en": "English", "es": "Español", "fr": "Français", "de": "Deutsch", "ja": "日本語"}
TEXT_KEYS = {"title", "description", "language_label", "apps_heading", "open_app", "pending_link", "pending_notice", "skip_to_content"}


def validate_url(value):
    if value is None:
        return
    if not isinstance(value, str) or not value or any(c.isspace() or ord(c) < 32 or c == "\\" for c in value):
        raise ValueError("App URLs must be nonempty HTTPS URLs without whitespace or backslashes")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise ValueError("App URLs must use HTTPS without credentials")
    _ = parsed.port


def load_inputs(root=ROOT):
    apps = json.loads((root / "apps.json").read_text(encoding="utf-8"))
    if not isinstance(apps, list):
        raise ValueError("apps.json must contain an array")
    ids = set()
    for app in apps:
        if not isinstance(app, dict) or not isinstance(app.get("id"), str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", app["id"]):
            raise ValueError("Each app needs a stable, URL-safe id")
        if app["id"] in ids or not isinstance(app.get("name"), str) or not app["name"].strip():
            raise ValueError("App ids must be unique and names nonempty")
        ids.add(app["id"])
        validate_url(app.get("url"))
        overrides = app.get("localized_urls", {})
        if not isinstance(overrides, dict) or not set(overrides) <= set(LANGUAGES):
            raise ValueError("localized_urls must map supported language codes to HTTPS URLs")
        for value in overrides.values():
            validate_url(value)
    catalogs = {}
    for lang in LANGUAGES:
        catalog = json.loads((root / "languages" / f"{lang}.json").read_text(encoding="utf-8"))
        if not isinstance(catalog, dict) or set(catalog) != TEXT_KEYS | {"app_descriptions"}:
            raise ValueError(f"{lang}: translation keys do not match the schema")
        if any(not isinstance(catalog[key], str) or not catalog[key].strip() for key in TEXT_KEYS):
            raise ValueError(f"{lang}: translations must be nonempty strings")
        descriptions = catalog["app_descriptions"]
        if not isinstance(descriptions, dict) or set(descriptions) != ids or any(not isinstance(v, str) or not v.strip() for v in descriptions.values()):
            raise ValueError(f"{lang}: every app needs a translated description")
        if "{name}" not in catalog["open_app"]:
            raise ValueError(f"{lang}: open_app must contain the literal token {{name}}")
        catalogs[lang] = catalog
    return apps, catalogs


def app_url(app, lang):
    # Never assume that an external app supports a locale path or query parameter.
    return app.get("localized_urls", {}).get(lang) or app.get("url")


def render(template, lang, catalogs, apps, prefix):
    catalog = catalogs[lang]
    alternates, links, options, cards = [], [], [], []
    for code, name in LANGUAGES.items():
        href = f"{prefix}{code}/"
        alternates.append(f'<link rel="alternate" hreflang="{code}" href="{href}">')
        current = ' aria-current="page"' if code == lang else ""
        selected = " selected" if code == lang else ""
        links.append(f'<li><a data-locale="{code}" lang="{code}" hreflang="{code}" href="{href}"{current}>{escape(name)}</a></li>')
        options.append(f'<option lang="{code}" value="{href}"{selected}>{escape(name)}</option>')
    alternates.append(f'<link rel="alternate" hreflang="x-default" href="{prefix}">')
    for app in apps:
        name, app_id = escape(app["name"]), app["id"]
        url = app_url(app, lang)
        if url:
            label = escape(catalog["open_app"].replace("{name}", app["name"]))
            destination = f'<a class="button" data-app-id="{app_id}" href="{escape(url, quote=True)}">{label}</a>'
        else:
            destination = f'<span class="pending" data-app-id="{app_id}" data-link-status="pending">{escape(catalog["pending_link"])}</span>'
        description = escape(catalog["app_descriptions"][app_id])
        cards.append(f'<article class="app-card"><h3>{name}</h3><p>{description}</p>{destination}</article>')
    pending = any(not app_url(app, lang) for app in apps)
    values = {key: escape(catalog[key], quote=True) for key in TEXT_KEYS}
    values.update(lang=lang, prefix=prefix, alternates="\n  ".join(alternates), language_links="".join(links), options="".join(options), app_cards="\n".join(cards))
    values["pending_notice"] = f'<p class="notice">{escape(catalog["pending_notice"])}</p>' if pending else ""
    return Template(template).substitute(values)


def build(root=ROOT, output=None):
    root = Path(root)
    output = Path(output) if output is not None else root / "_site"
    if output.resolve() == root.resolve() or output.resolve() in root.resolve().parents:
        raise ValueError("Build output must not overwrite the source directory or its parents")
    apps, catalogs = load_inputs(root)
    template = (root / "index.html").read_text(encoding="utf-8")
    output.mkdir(parents=True, exist_ok=True)
    for route, lang in [("", "en"), *((lang, lang) for lang in LANGUAGES)]:
        directory = output / route
        directory.mkdir(parents=True, exist_ok=True)
        prefix = "../" if route else "./"
        (directory / "index.html").write_text(render(template, lang, catalogs, apps, prefix), encoding="utf-8")
    (output / "assets").mkdir(exist_ok=True)
    for name in ("site.css", "language.js"):
        shutil.copyfile(root / "assets" / name, output / "assets" / name)
    (output / "languages").mkdir(exist_ok=True)
    for lang, catalog in catalogs.items():
        text = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
        (output / "languages" / f"{lang}.json").write_text(text, encoding="utf-8")
        (output / f"{lang}.json").write_text(text, encoding="utf-8")
    info = {"commit": os.environ.get("GITHUB_SHA", "local"), "languages": list(LANGUAGES), "pending_apps": [app["id"] for app in apps if any(not app_url(app, lang) for lang in LANGUAGES)]}
    (output / "build-info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    (output / ".nojekyll").write_text("", encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "_site")
    args = parser.parse_args()
    print(f"Built localized site: {build(output=args.output)}")
