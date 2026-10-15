"""Decoder del formato turbo-stream (React Router v7) incorporato nelle pagine del configuratore."""
import json
import re

HOLE, NAN, NEG_INF, NEG_ZERO, NULL, POS_INF, UNDEFINED = -1, -2, -3, -4, -5, -6, -7
SPECIAL = {HOLE: None, NAN: float("nan"), NEG_INF: float("-inf"), NEG_ZERO: -0.0,
           NULL: None, POS_INF: float("inf"), UNDEFINED: None}

ENQUEUE_RE = re.compile(r'streamController\.enqueue\((".*?")\);?\s*</script>', re.S)


def stream_from_html(html: str) -> str:
    return "".join(json.loads(m.group(1)) for m in ENQUEUE_RE.finditer(html))


def decode(stream: str):
    lines = [l for l in stream.split("\n") if l.strip()]
    values = json.loads(lines[0])
    promises = {}
    for l in lines[1:]:  # righe "P<id>:<json>" con i valori delle promise risolte
        m = re.match(r"^[PE](\d+):(.*)$", l, re.S)
        if m:
            promises[int(m.group(1))] = json.loads(m.group(2))
    cache = {}

    def hyd(i):
        if isinstance(i, int) and i < 0:
            return SPECIAL.get(i)
        if i in cache:
            return cache[i]
        v = values[i]
        if isinstance(v, list):
            if v and isinstance(v[0], str) and len(v) <= 3 and v[0] in "DPRYEMSWBUZ" and len(v[0]) == 1:
                tag = v[0]
                if tag == "D":
                    out = v[1]
                elif tag == "P":
                    pid = v[1]
                    out = None
                    if pid in promises:
                        values.append(promises[pid][0] if isinstance(promises[pid], list) and len(promises[pid]) == 1 and isinstance(promises[pid][0], int) else None)
                        out = hyd(promises[pid][0]) if isinstance(promises[pid], list) and promises[pid] and isinstance(promises[pid][0], int) else promises[pid]
                elif tag == "S":
                    out = set()
                else:
                    out = v[1:] if len(v) > 1 else None
                cache[i] = out
                return out
            out = []
            cache[i] = out
            out.extend(hyd(x) for x in v)
            return out
        if isinstance(v, dict):
            out = {}
            cache[i] = out
            for k, vi in v.items():
                key = values[int(k[1:])] if k.startswith("_") else k
                out[key] = hyd(vi)
            return out
        cache[i] = v
        return v

    return hyd(0)
