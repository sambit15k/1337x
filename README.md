# 1337x

This repository contains a small Python scraper/search engine wrapper for the 1337x torrent site.

Main file
- `x1337.py` — a lightweight, testable search class that parses 1337x search results and prints
  results using a `prettyPrinter`-style function (compatible with `novaprinter`). The implementation:
  - tries to use `BeautifulSoup` when available and falls back to regex parsing when necessary
  - normalizes file size strings and provides an integer byte size for easier filtering/sorting
  - includes a small retry/backoff fetch helper so the search is more robust for CI and local runs

Testing & CI
- `tests/test_x1337.py` contains unit tests for size normalization and basic HTML parsing.
- GitHub Actions workflow at `.github/workflows/ci.yml` installs dependencies and runs `pytest`.

Usage
- Run the search locally (example):
  - `python x1337.py "search terms"` (this script accepts several CLI flags; see file header)

Notes
- The code is intentionally minimal and includes a fallback `prettyPrinter` so it can run without
  external novaprinter tooling during tests or CI.
