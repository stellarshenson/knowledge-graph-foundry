import sys, time; sys.path.insert(0, 'notebooks')
import warnings; warnings.filterwarnings('ignore')
from parser_harness import *
import pymupdf4llm, pdfplumber
from pypdf import PdfReader
docnames, rows = load_entities()
allpdfs = sorted(p.name for p in PDFDIR.glob('*.pdf'))
print('pdfs on disk', len(allpdfs), '| ingested docnames', len(docnames), flush=True)
tri = {p: {} for p in TRIO}
for i, nm in enumerate(allpdfs):
    p = PDFDIR / nm
    t0 = time.time()
    try: tri['pymupdf4llm'][nm] = pymupdf4llm.to_markdown(str(p))
    except Exception as e: tri['pymupdf4llm'][nm] = ''; print('pymupdf4llm FAIL', nm, e, flush=True)
    try:
        with pdfplumber.open(str(p)) as pdf:
            tri['pdfplumber'][nm] = '\n'.join((pg.extract_text() or '') for pg in pdf.pages)
    except Exception as e: tri['pdfplumber'][nm] = ''; print('pdfplumber FAIL', nm, e, flush=True)
    try:
        tri['pypdf'][nm] = '\n'.join((pg.extract_text() or '') for pg in PdfReader(str(p)).pages)
    except Exception as e: tri['pypdf'][nm] = ''; print('pypdf FAIL', nm, e, flush=True)
    print(f'[{i+1}/{len(allpdfs)}] {nm[:45]:45s} {time.time()-t0:5.1f}s '
          f'chars={ {k: len(tri[k][nm]) for k in TRIO} }', flush=True)
for p in TRIO: save_text(p, tri[p])
evox = [n for n in allpdfs if 'Evox' in n][0]
print('EVOX chars:', {p: len(tri[p][evox]) for p in TRIO}, flush=True)
print('DONE saved trio', [text_path(p).exists() for p in TRIO], flush=True)
