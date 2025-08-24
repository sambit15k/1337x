import re
import json
import logging
from time import sleep
from typing import Optional, List, Dict, Tuple

try:
    from helpers import retrieve_url
except Exception:
    retrieve_url = None  # type: ignore

try:
    from novaprinter import prettyPrinter
except Exception:
    # Fallback prettyPrinter for environments without novaprinter.
    def prettyPrinter(data: dict) -> None:  # type: ignore
        # Minimal printable representation to mimic novaprinter behaviour
        out = {
            'name': data.get('name'),
            'link': data.get('link'),
            'size': data.get('size'),
            'seeds': data.get('seeds'),
            'leech': data.get('leech'),
            'engine_url': data.get('engine_url'),
            'desc_link': data.get('desc_link')
        }
        print(json.dumps(out, ensure_ascii=False))

# Optional requests fallback
try:
    import requests  # type: ignore
    _HAS_REQUESTS = True
except Exception:
    requests = None  # type: ignore
    _HAS_REQUESTS = False

# Optional dependency for more robust parsing
try:
    from bs4 import BeautifulSoup  # type: ignore
    _HAS_BS4 = True
except Exception:
    BeautifulSoup = None  # type: ignore
    _HAS_BS4 = False

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class x1337(object):
    """1337x torrent search engine scraper with improved robustness."""
    url: str = 'https://1337x.to'
    name: str = '1337x'
    supported_categories: dict = {
        'all': 'search',
        'movies': 'Movies',
        'tv': 'TV',
        'music': 'Music',
        'games': 'Games',
        'anime': 'Anime',
        'software': 'Applications'
    }
    SLEEP_SECONDS: int = 3  # seconds between page requests
    RETRIES: int = 2
    RETRY_BACKOFF: float = 1.5  # multiplier

    class HTMLParser:
        """Parses HTML content to extract torrent information.

        Uses BeautifulSoup when available, otherwise falls back to regex.
        Adds size normalization (size_bytes) for easier filtering/sorting.
        """
        ROW_PATTERN = re.compile(r'<tr>.+?</tr>', re.DOTALL)
        TORRENT_PATTERN = re.compile(
            r'<a href="(/torrent/[^"]+)"[^>]*>([^<]+)</a>.*?'
            r'<td class="coll-2[^"]*">([^<]+)</td>.*?'
            r'<td class="coll-3[^"]*">([^<]+)</td>.*?'
            r'<td class="coll-4[^"]*">([^<]+)</td>',
            re.DOTALL
        )
        MAGNET_PATTERN = re.compile(r'href="(magnet:\?xt=urn:btih:[^"]+)"')

        def __init__(self, url: str):
            self.url = url
            self.noTorrents = False

        def feed(self, html: str) -> None:
            """Parse HTML and pretty-print results via novaprinter.prettyPrinter."""
            self.noTorrents = False
            torrents = self.__findTorrents(html)
            if not torrents:
                self.noTorrents = True
                return
            for torrent in torrents:
                data = {
                    'link': torrent[0],
                    'name': torrent[1],
                    'size': torrent[2],
                    'size_bytes': torrent[6],
                    'seeds': torrent[3],
                    'leech': torrent[4],
                    'engine_url': self.url,
                    'desc_link': torrent[5]
                }
                prettyPrinter(data)

        def __findTorrents(self, html: str) -> List[List]:
            results: List[List] = []
            if _HAS_BS4 and BeautifulSoup is not None:
                try:
                    soup = BeautifulSoup(html, 'html.parser')
                    rows = soup.find_all('tr')
                    for row in rows:
                        a = row.find('a', href=re.compile(r'^/torrent/'))
                        if not a:
                            continue
                        torrent_url = self.url + a['href']
                        name = a.get_text(strip=True)
                        cols = row.find_all('td')
                        # Best-effort mapping based on 1337x table layout
                        seeds = cols[1].get_text(strip=True) if len(cols) > 1 else '0'
                        leech = cols[2].get_text(strip=True) if len(cols) > 2 else '0'
                        size_text = cols[3].get_text(strip=True) if len(cols) > 3 else ''
                        size_str, size_bytes = x1337._normalize_size(size_text)
                        magnet = self.__getMagnetLink(torrent_url)
                        if magnet:
                            results.append([magnet, name, size_str, seeds, leech, torrent_url, size_bytes])
                    return results
                except Exception as e:
                    logger.debug('BeautifulSoup parsing failed, falling back to regex: %s', e)

            # Fallback to regex parsing
            rows = self.ROW_PATTERN.findall(html)
            for row in rows:
                match = self.TORRENT_PATTERN.search(row)
                if match:
                    torrent_url = self.url + match.group(1)
                    name = match.group(2).strip()
                    seeds = match.group(3).strip()
                    leech = match.group(4).strip()
                    raw_size = match.group(5).strip()
                    size_str, size_bytes = x1337._normalize_size(raw_size)
                    magnet = self.__getMagnetLink(torrent_url)
                    if magnet:
                        results.append([magnet, name, size_str, seeds, leech, torrent_url, size_bytes])
            return results

        def parse(self, html: str) -> List[List]:
            """Public parse method returning list of torrent tuples.

            Each item: [magnet, name, size_str, seeds, leech, desc_url, size_bytes]
            """
            return self.__findTorrents(html)

        def __getMagnetLink(self, desc_url: str) -> Optional[str]:
            try:
                html = retrieve_url(desc_url)
                match = self.MAGNET_PATTERN.search(html)
                if match:
                    return match.group(1)
            except Exception as e:
                logger.debug('Error retrieving magnet link from %s: %s', desc_url, e)
            return None

    @staticmethod
    def _normalize_size(text: str) -> Tuple[str, int]:
            """Convert size string like '1.23 GB' or '1234 MB' to canonical display and bytes.

            Returns (human_readable, bytes_int).
            """
            if not text:
                return ('0 B', 0)
            t = text.replace('\xa0', ' ').strip()
            # Extract number and unit
            m = re.search(r'([\d,.]+)\s*([KMGT]?B|B|KB|MB|GB|TB)?', t, re.IGNORECASE)
            if not m:
                return (t, 0)
            number = m.group(1).replace(',', '')
            try:
                value = float(number)
            except Exception:
                value = 0.0
            unit = (m.group(2) or 'B').upper()
            # normalize units
            unit_map = {
                'B': 0,
                'KB': 1,
                'MB': 2,
                'GB': 3,
                'TB': 4,
                'K': 1,
                'M': 2,
                'G': 3,
                'T': 4,
            }
            unit_key = unit.replace('IB', 'B') if unit.endswith('IB') else unit
            power = unit_map.get(unit_key, 0)
            bytes_val = int(value * (1024 ** power))
            # nice human readable with two decimals
            for i, u in enumerate(['B', 'KB', 'MB', 'GB', 'TB']):
                if bytes_val < 1024 ** (i + 1) or i == 4:
                    display = f"{bytes_val / (1024 ** i):.2f} {u}"
                    return (display, bytes_val)
            return (t, bytes_val)


    def _fetch_with_retries(self, url: str) -> Optional[str]:
        """Fetch a URL using retrieve_url with simple retry/backoff."""
        attempt = 0
        backoff = 1.0
        while attempt <= self.RETRIES:
            try:
                if retrieve_url:
                    html = retrieve_url(url)
                elif _HAS_REQUESTS and requests is not None:
                    r = requests.get(url, timeout=10)
                    r.raise_for_status()
                    html = r.text
                else:
                    raise RuntimeError('No available HTTP retrieval function (install helpers or requests)')
                return html
            except Exception as e:
                logger.debug('Fetch attempt %d failed for %s: %s', attempt + 1, url, e)
                attempt += 1
                if attempt > self.RETRIES:
                    logger.warning('All fetch attempts failed for %s', url)
                    return None
                sleep(backoff)
                backoff *= self.RETRY_BACKOFF

    def search(self, what: str, cat: str = 'all', output_json: bool = False, max_pages: Optional[int] = None) -> None:
        """Search for torrents matching 'what' in the given category and print results.

        This is intentionally simple (prints via novaprinter) but now more robust and testable.
        """
        what = what.replace(' ', '%20')
        cat_url = self.supported_categories.get(cat, 'search')
        parser = self.HTMLParser(self.url)
        page = 1
        collected: List[List] = [] if output_json else []

        while True:
            if cat == 'all':
                search_url = f'{self.url}/search/{what}/{page}/'
            else:
                search_url = f'{self.url}/{cat_url}/{what}/{page}/'

            html = self._fetch_with_retries(search_url)
            if not html:
                break
            # normalize whitespace for easier regex parsing
            html_norm = re.sub(r'\s+', ' ', html).strip()
            parsed = parser.parse(html_norm)
            if not parsed:
                break

            if output_json:
                collected.extend(parsed)
            else:
                for torrent in parsed:
                    data = {
                        'link': torrent[0],
                        'name': torrent[1],
                        'size': torrent[2],
                        'seeds': torrent[3],
                        'leech': torrent[4],
                        'engine_url': self.url,
                        'desc_link': torrent[5]
                    }
                    prettyPrinter(data)

            page += 1
            if max_pages and page > max_pages:
                break
            sleep(self.SLEEP_SECONDS)

        if output_json and collected:
            out = []
            for t in collected:
                out.append({
                    'magnet': t[0],
                    'name': t[1],
                    'size': t[2],
                    'size_bytes': t[6],
                    'seeds': t[3],
                    'leech': t[4],
                    'desc_link': t[5],
                })
            print(json.dumps(out, ensure_ascii=False, indent=2))

    # (results already printed or output above)


def main():
    import argparse
    p = argparse.ArgumentParser(description='Search 1337x and print results via novaprinter')
    p.add_argument('query', help='Search query')
    p.add_argument('--category', '-c', default='all', help='Category (default: all)')
    p.add_argument('--json', action='store_true', dest='output_json', help='Output results as JSON')
    p.add_argument('--max-pages', type=int, dest='max_pages', default=None, help='Maximum number of pages to fetch')
    p.add_argument('--sleep', type=float, dest='sleep_seconds', default=None, help='Override sleep seconds between pages')
    args = p.parse_args()
    engine = x1337()
    if args.sleep_seconds is not None:
        engine.SLEEP_SECONDS = args.sleep_seconds
    engine.search(args.query, args.category, output_json=args.output_json, max_pages=args.max_pages)


if __name__ == '__main__':
    main()
