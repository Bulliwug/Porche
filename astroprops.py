"""Decoder delle props serializzate dei componenti Astro (<astro-island props="...">) di porsche.com."""
import html
import json
import re

PROPS_RE = re.compile(r'<astro-island[^>]*?\sprops="([^"]*)"', re.S)


def _de(v):
    if isinstance(v, list) and len(v) == 2 and isinstance(v[0], int):
        t, x = v
        if t == 0:
            return {k: _de(val) for k, val in x.items()} if isinstance(x, dict) else x
        if t == 1:
            return [_de(i) for i in x]
        return x
    if isinstance(v, dict):
        return {k: _de(val) for k, val in v.items()}
    return v


def islands(page_html: str):
    for m in PROPS_RE.finditer(page_html):
        try:
            yield {k: _de(v) for k, v in json.loads(html.unescape(m.group(1))).items()}
        except Exception:
            continue
