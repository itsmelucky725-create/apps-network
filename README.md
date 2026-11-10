# apps-network

A dependency-free, five-language showcase for Zion Tech Group. The build produces a static English landing page plus `/en/`, `/es/`, `/fr/`, `/de/`, and `/ja/` routes.

## Structure

- `languages/{en,es,fr,de,ja}.json`: canonical translation catalogs, including navigation, app descriptions, and pending-link messages.
- `apps.json`: central app registry; each entry has `id`, `name`, a canonical HTTPS `url`, and optional `localized_urls` overrides keyed by language code.
- `index.html`: HTML build template, not a file to publish directly.
- `assets/`: responsive styles and a progressively enhanced language selector. Ordinary language links work without JavaScript.
- `scripts/build.py`: validates inputs and builds the publishable `_site/` directory.
- `tests/`: translation, route, asset, registry, HTML escaping, and selector tests.
- `.github/workflows/pages.yml`: tests, builds, and deploys to GitHub Pages from `main` only.

The original root JSON files are retained as legacy source files, not used by the build. Published `/{lang}.json` compatibility endpoints are generated from the canonical `languages/` catalogs, so the live aliases cannot drift.

## Develop and verify

Requires Python 3.12+ and Node.js 22+ for the JavaScript tests; no third-party packages are needed.

```sh
python -m unittest discover -s tests -v
node --test tests/language.test.cjs
python scripts/build.py --output _site
python -m http.server 8000 --directory _site
```

Open `http://localhost:8000/` and each locale route. All internal paths are relative, so assets and navigation work under the GitHub Pages repository subpath. Every page includes the correct HTML language, localized metadata, alternate-language links, and a working language selector with a no-JavaScript fallback.

## App destinations

The app registry uses the destinations supplied by the project owner:

- [App One](https://ziontechgroup.com/app-one)
- [App Two](https://ziontechgroup.com/app-two)

All five locales use these exact canonical URLs. Locale-specific app destinations have not been supplied, so `localized_urls` remains empty. Configured apps render as links instead of pending labels.

External availability, redirects, and reciprocal navigation inside the destination apps still need separate verification. Passing the generated-link tests does not establish destination health or modify those apps.

To add or change an app, update its registry entry with its actual name and HTTPS destination. Add `localized_urls` only for explicitly supported localized destinations; otherwise every locale uses the exact canonical URL. The build never guesses external locale routes or query parameters. Update `app_descriptions` in all five catalogs if adding app IDs.

## Deployment

Enable GitHub Pages with the **GitHub Actions** build source. The workflow tests and builds on pull requests, and deploys only successful builds of `main` (push or manual dispatch). The generated `build-info.json` records the deployed commit, language list, and pending app IDs. Serve `_site/`, not the repository root. No custom domain, external credentials, or paid hosting is required.
