import sys, time, json; sys.path.insert(0, 'notebooks')
import warnings; warnings.filterwarnings('ignore')
from pathlib import Path
from parser_harness import PDFDIR, CACHE, save_text, load_entities
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, AcceleratorOptions, AcceleratorDevice

opts = PdfPipelineOptions()
opts.do_ocr = False  # born-digital: use text cells (docling-parse backend), the H146 point
opts.do_table_structure = True
opts.accelerator_options = AcceleratorOptions(device=AcceleratorDevice.CPU)
conv = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})

docnames, rows = load_entities()
allpdfs = sorted(p.name for p in PDFDIR.glob('*.pdf'))
full, tabletext, times = {}, {}, {}
for i, nm in enumerate(allpdfs):
    t0 = time.time()
    try:
        res = conv.convert(str(PDFDIR / nm))
        doc = res.document
        md = doc.export_to_markdown()
        tt = '\n'.join(t.export_to_markdown(doc) for t in doc.tables)
        full[nm] = md; tabletext[nm] = tt
    except Exception as e:
        full[nm] = ''; tabletext[nm] = ''; print('DOCLING FAIL', nm, repr(e)[:200], flush=True)
    times[nm] = round(time.time() - t0, 1)
    print(f'[{i+1}/{len(allpdfs)}] {nm[:45]:45s} {times[nm]:6.1f}s md={len(full[nm])} tab={len(tabletext[nm])}', flush=True)
save_text('docling', full)
(CACHE / 'docling_tabletext.json').write_text(json.dumps(tabletext))
(CACHE / 'docling_runtime.json').write_text(json.dumps(times))
evox = [n for n in allpdfs if 'Evox' in n][0]
print('EVOX docling chars:', len(full[evox]), flush=True)
print('DONE docling', flush=True)
