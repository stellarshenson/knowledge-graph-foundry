import os, sys, json, time
os.environ.setdefault('CUDA_DEVICE_ORDER', 'PCI_BUS_ID')
os.environ.setdefault('CUDA_VISIBLE_DEVICES', '2')  # RTX 5000 Ada 32GB
sys.path.insert(0, 'notebooks')
import warnings; warnings.filterwarnings('ignore')
from pathlib import Path
from parser_harness import CACHE, PDFDIR
import torch, pypdfium2 as pdfium
from PIL import Image
from transformers import AutoProcessor, Qwen2VLForConditionalGeneration
from olmocr.prompts.prompts import build_finetuning_prompt
from olmocr.prompts.anchor import get_anchor_text

MODEL = 'allenai/olmOCR-7B-0225-preview'
MANIFEST = os.environ.get('OLM_MANIFEST', 'combined_manifest.json')
SUFFIX = os.environ.get('OLM_SUFFIX', '')  # '' first pass, '2' supplementary
manifest = json.loads((CACHE / MANIFEST).read_text())
print(f'device count {torch.cuda.device_count()} name {torch.cuda.get_device_name(0)}', flush=True)

t0 = time.time()
proc = AutoProcessor.from_pretrained(MODEL, trust_remote_code=True)
model = Qwen2VLForConditionalGeneration.from_pretrained(
    MODEL, torch_dtype=torch.bfloat16, device_map='cuda:0', trust_remote_code=True).eval()
print(f'model loaded {time.time()-t0:.1f}s', flush=True)

def render(doc, page, longest=1024):
    pdf = pdfium.PdfDocument(str(PDFDIR / doc))
    pg = pdf[page]
    w, h = pg.get_size()
    scale = longest / max(w, h)
    bmp = pg.render(scale=scale)
    img = bmp.to_pil().convert('RGB')
    pdf.close()
    return img

def infer(img, anchor_text):
    prompt = build_finetuning_prompt(anchor_text)
    messages = [{'role': 'user', 'content': [
        {'type': 'image'}, {'type': 'text', 'text': prompt}]}]
    text = proc.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = proc(text=[text], images=[img], return_tensors='pt').to('cuda:0')
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=1600, do_sample=False,
                             temperature=None, top_p=None, top_k=None)
    gen = out[0][inputs['input_ids'].shape[1]:]
    return proc.decode(gen, skip_special_tokens=True)

anchored, off, times = {}, {}, {}
for i, m in enumerate(manifest):
    doc, page = m['doc'], m['page']
    key = f'{doc}||{page}'
    t = time.time()
    img = render(doc, page)
    try:
        atext = get_anchor_text(str(PDFDIR / doc), page + 1, pdf_engine='pdfreport')
    except Exception as e:
        atext = ''
    try:
        anchored[key] = infer(img, atext)
    except Exception as e:
        anchored[key] = ''; print('ANCHORED FAIL', key, repr(e)[:120], flush=True)
    try:
        off[key] = infer(img, '')  # anchor-off: empty RAW_TEXT, image-only signal
    except Exception as e:
        off[key] = ''; print('OFF FAIL', key, repr(e)[:120], flush=True)
    times[key] = round(time.time() - t, 1)
    print(f'[{i+1}/{len(manifest)}] {times[key]:5.1f}s a={len(anchored[key])} o={len(off[key])} anc={len(atext)} {doc[:32]}#{page}', flush=True)
    if (i + 1) % 10 == 0:
        (CACHE / f'olmocr_anchored{SUFFIX}.json').write_text(json.dumps(anchored))
        (CACHE / f'olmocr_off{SUFFIX}.json').write_text(json.dumps(off))

(CACHE / f'olmocr_anchored{SUFFIX}.json').write_text(json.dumps(anchored))
(CACHE / f'olmocr_off{SUFFIX}.json').write_text(json.dumps(off))
(CACHE / f'olmocr_runtime{SUFFIX}.json').write_text(json.dumps(times))
print('DONE olmocr', flush=True)
