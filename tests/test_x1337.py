import json
import re
import types
import pytest

from x1337 import x1337


def test_normalize_size_bytes_and_display():
    cases = [
        ("1023 B", ("1023.00 B", 1023)),
        ("1 KB", ("1.00 KB", 1024)),
        ("1.5 MB", ("1.50 MB", int(1.5 * 1024 ** 2))),
        ("2.25 GB", ("2.25 GB", int(2.25 * 1024 ** 3))),
        ("", ("0 B", 0)),
    ]
    for input_text, expected in cases:
        display, b = x1337._normalize_size(input_text)
        assert expected[1] == b
        assert expected[0].split()[1] == display.split()[1]


def test_htmlparser_parse_with_minimal_html(monkeypatch, tmp_path):
    sample_html = '''
    <html>
    <body>
      <table>
        <tr>
          <td class="coll-1"><a href="/torrent/12345">Example.Torrent</a></td>
          <td class="coll-2">10</td>
          <td class="coll-3">5</td>
          <td class="coll-4">1.2 GB</td>
        </tr>
      </table>
    </body>
    </html>
    '''

    # monkeypatch retrieve_url so magnet link retrieval returns a magnet
    def fake_retrieve(url):
        return 'href="magnet:?xt=urn:btih:FAKEHASH&dn=Example.Torrent"'

    monkeypatch.setattr('x1337.retrieve_url', fake_retrieve, raising=False)

    parser = x1337.HTMLParser(x1337.url)
    results = parser.parse(sample_html)
    assert len(results) == 1
    magnet, name, size_str, seeds, leech, desc_url, size_bytes = results[0]
    assert magnet.startswith('magnet:?xt=urn:btih:')
    assert 'Example.Torrent' in name
    assert 'GB' in size_str
