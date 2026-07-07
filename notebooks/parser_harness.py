"""Shared harness for the R14 SOTA parser round (H146-H150).

Reuses the EXACT H51 normalization / name-presence conventions so results are
comparable to reports/parse-fidelity-h51-*.json. Do not change norm/nospace/present.
"""
import json, re, hashlib, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDFDIR = ROOT / 'data/external/cpap-datasheets-and-manuals'
CACHE = ROOT / 'tmp/parser-round-cache'
CACHE.mkdir(parents=True, exist_ok=True)

# ---- H51 conventions (verbatim) ----
def norm(x): return ' '.join((x or '').lower().split())
def nospace(x): return re.sub(r'\s+', '', (x or '').lower())

def present_in(name, text_norm, text_nospace):
    nn = norm(name)
    if nn and nn in text_norm:
        return True
    ns = nospace(name)
    return bool(ns) and ns in text_nospace

# ---- entity rows (cached from neo4j2 read-only) ----
def load_entities():
    d = json.loads((CACHE / 'entities.json').read_text())
    return d['docnames'], d['rows']

# ---- per-parser text cache: {docname: fulltext} ----
def text_path(parser): return CACHE / f'text_{parser}.json'
def save_text(parser, d): text_path(parser).write_text(json.dumps(d))
def load_text(parser): return json.loads(text_path(parser).read_text())

def norm_maps(textdict):
    """docname -> (norm_text, nospace_text)"""
    return {nm: (norm(t), nospace(t)) for nm, t in textdict.items()}

# ---- baseline trio present() using cached texts ----
TRIO = ['pymupdf4llm', 'pdfplumber', 'pypdf']

def build_found_table(rows, textmaps_by_parser, parsers):
    """rows -> per entity: {parser: found_in_any_source_doc}."""
    out = []
    for r in rows:
        found = {}
        for p in parsers:
            tm = textmaps_by_parser[p]
            found[p] = any(
                (dn in tm) and present_in(r['name'], tm[dn][0], tm[dn][1])
                for dn in r['docs']
            )
        out.append(dict(name=r['name'], docs=r['docs'], types=r['types'], found=found))
    return out

def present_in_doc(name, dn, textmap):
    if dn not in textmap:
        return False
    tn, ts = textmap[dn]
    return present_in(name, tn, ts)
