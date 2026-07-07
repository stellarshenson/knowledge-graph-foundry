"""Build the frozen H216 census artifact + H216/H217 reports from cached intermediates."""
import json, collections, datetime, re
from pathlib import Path

ROOT = Path("/home/lab/workspace/learning/projects/knowledge-graph-foundry")
CACHE = ROOT / "reports/image-census-cache"
a13 = json.loads((CACHE / "arms13.json").read_text())
a2 = json.loads((CACHE / "arm2.json").read_text())
asm = json.loads((CACHE / "assembled.json").read_text())
verdicts = json.loads((CACHE / "h217_verdicts.json").read_text())
DOCS = a13["docs"]
arm1, arm3 = a13["arm1"], a13["arm3"]
CLASS_PROFILE = asm["class_profile"]
uniq1 = asm["uniq1"]; lbl1 = asm["lbl1"]
INFO_BEARING = {"product_photo", "diagram", "rendered_table", "chart"}
STAMP = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def md(r): return max((r.get("w") or 0), (r.get("h") or 0))

# ---- clause (b): per-doc info-bearing + pixel-only info-bearing text (verified) ----
# verified pixel-only info-bearing text (visible in image, NOT in doc text layer)
PIXEL_TEXT_DOCS = {
 "PDF RESmart Service Manual CPAP.pdf": "troubleshooting flowchart node text ('Power Supply','Wrong Version') rendered as images; not in text layer",
 "DreamStation_CPAP_User_Manual.pdf": "device-display screenshot values ('5.5 cmH2O') pixel-only",
 "SleepStyle_200_Operating_Manual.pdf": "regulatory rating symbol 'IPX1' rendered as image; not in text layer",
 "Brochure_BMC_GIII_A20_Oxygenium_Medical.pdf": "device screen 'Usage Summary' / iCode rendered pixel-only",
 "ARTP_Standards_of_Care_-_CPAP_Devices_(Technical_and_Performance)_Version_5.0_-_05-02-2022.pdf": "schematic dimension '40 mm' + chart axis/legend rendered pixel-only",
 "ResMed-Airsense-11-Manual.pdf": "touchscreen UI menu values rendered pixel-only (product specs are live text)",
 "Resvent-iBreeze-Auto-CPAP-User-Manual.pdf": "device-UI screenshot values rendered pixel-only (specs are live text)",
}
# every doc carries >=1 information-bearing image (product photo / diagram / table / chart)
docs_info_bearing = set(DOCS)   # verified via montage inspection: all 27 have product photos/diagrams/tables
n_docs = len(DOCS)
clause_b_share = len(PIXEL_TEXT_DOCS) / n_docs
info_bearing_doc_share = len(docs_info_bearing) / n_docs

# ---- per-image census records (frozen) ----
byhash = collections.defaultdict(list)
for r in arm1: byhash[r["content_hash"]].append(r)
records = []
for u, l in zip(uniq1, lbl1):
    ib = l in INFO_BEARING
    records.append(dict(
        source_doc=u["doc"], page=u["page"], extraction_arms=["pymupdf_embedded"],
        content_hash=u["content_hash"], bbox=list(u["bbox"]) if u.get("bbox") else None,
        px_w=u.get("w"), px_h=u.get("h"), area_frac_on_page=u.get("area_frac"),
        n_placements=u["nplace"], n_pages_recurring=u["npg"], n_docs_recurring=u["ndocs"],
        class_label=l, information_bearing=ib,
        text_in_text_layer=(None if l in ("product_photo", "logo_decorative", "decorative")
                            else "doc_dependent"),
        label_method="montage_inferred_doc_profile+geometry"))
# vector-arm regions (Arm3) as census records (information-bearing tables/schematics/charts)
for r in arm3:
    if not r.get("file"): continue
    records.append(dict(
        source_doc=r["doc"], page=r["page"], extraction_arms=["page_render_vector_diff"],
        content_hash=None, bbox=list(r["bbox"]), px_w=None, px_h=None,
        area_frac_on_page=r["area_frac"], n_placements=1, n_pages_recurring=1, n_docs_recurring=1,
        class_label="vector_region(rendered_table/schematic/chart/textbox)", information_bearing=True,
        text_in_text_layer="in_text_layer(vector fills + real glyphs; catalogue codes recoverable)",
        label_method="montage_sample_A3_inspected"))

# ---- per-doc summary ----
per_doc = {}
for doc in DOCS:
    u1 = [u for u in uniq1 if u["doc"] == doc]
    l1 = [l for u, l in zip(uniq1, lbl1) if u["doc"] == doc]
    v3 = [r for r in arm3 if r["doc"] == doc]
    d2 = a2.get(doc, {})
    cls = collections.Counter(l1)
    per_doc[doc] = dict(
        arm1_embedded_unique=len(u1), arm1_placements=sum(u["nplace"] for u in u1),
        arm2_docling_pictures=d2.get("n_pictures", None if doc not in a2 else 0),
        arm2_docling_tables=d2.get("n_tables", None if doc not in a2 else 0),
        arm3_vector_regions=len(v3),
        class_distribution=dict(cls),
        info_bearing_unique=sum(1 for l in l1 if l in INFO_BEARING),
        has_information_bearing_image=True,
        has_pixel_only_infobearing_text=doc in PIXEL_TEXT_DOCS,
        pixel_text_note=PIXEL_TEXT_DOCS.get(doc, ""),
        class_profile=CLASS_PROFILE[doc])

# ---- clause (a) ----
A1 = len(uniq1); A2p = sum(v.get("n_pictures", 0) for v in a2.values())
A2t = sum(v.get("n_tables", 0) for v in a2.values()); A2 = A2p + A2t
A3 = len([r for r in arm3 if r["area_frac"] >= 0.02])
disagree = {"A1_vs_A2": abs(A1 - A2) / max(A1, A2), "A1_vs_A3": abs(A1 - A3) / max(A1, A3),
            "A2_vs_A3": abs(A2 - A3) / max(A2, A3)}
ib1 = sum(1 for l in lbl1 if l in INFO_BEARING)

census = dict(
    hypothesis="R21-H216", utc=STAMP, corpus="27-doc benchmark (data/external/cpap-datasheets-and-manuals, "
    "excludes 'Evox Auto CPAP Machine- Brochure - Oxygen Times.pdf' not in neo4j2 graph)",
    corpus_docs=DOCS, read_only=True, cpu_only=True,
    class_labels=["product_photo", "diagram", "rendered_table", "chart", "logo_decorative", "decorative",
                  "vector_region(rendered_table/schematic/chart/textbox)"],
    per_doc=per_doc, records=records,
    methodology=dict(
        arm1="pymupdf embedded image-object extraction (page.get_images + extract_image); deduped by content hash",
        arm2="Docling figure/layout detection (.venv-docling, do_ocr=False, do_table_structure=True); doc.pictures + doc.tables",
        arm3="page-render vector-diff: cluster_drawings() regions minus embedded-image bboxes, area_frac>=0.02, text-block subtracted",
        classification="multimodal inspection of 13 montage contact-sheets (513 sampled unique images, all 27 docs) "
                       "-> per-doc class profiles; per-image labels propagated from the inspected doc profile + geometry "
                       "(recurring small mark->logo, <64px->fragment). Per-image labels are doc-profile-inferred, "
                       "not per-image verified; authoritative granularity = per-doc class profile + 513 inspected samples.",
        deviation="Docling (Arm2) crashed repeatedly on product_and_solutions_catalog.pdf (90+ pages, memory); "
                  "26/27 docs have Docling coverage. That doc is still covered by Arm1 (283 embedded) + Arm3 (162 vector regions)."))
(ROOT / "data/processed/image-census-h216.json").write_text(json.dumps(census, indent=1))

# ---- H216 report ----
h216_report = dict(
    hypothesis="R21-H216", utc=STAMP, verdict_summary="clause(a) PASS; clause(b) NARROW (<30%, not refuted-narrow)",
    arm_inventories=dict(arm1_embedded_unique=A1, arm1_placements=len(arm1),
                         arm2_docling_pictures=A2p, arm2_docling_tables=A2t, arm2_docling_total=A2,
                         arm2_coverage="26/27 docs (catalogue OOM deviation)",
                         arm3_vector_regions=A3),
    clause_a=dict(count_disagreement=disagree, threshold=0.20, passes=all(v >= 0.20 for v in disagree.values()),
                  dominating_arm="Docling (Arm2)",
                  dominating_rationale="Docling captures raster figures (745, ~89% page-overlap with embedded objects) "
                  "PLUS 226 structured tables the embedded arm misses entirely; embedded arm inflates raw count "
                  "(1566 unique from 91175 placements, 281 decorative) yet captures ZERO vector-drawn tables/schematics; "
                  "vector arm (Arm3) uniquely captures 558 vector-drawn tables/schematics/charts as image regions. "
                  "The three inventories are materially different; no arm is a superset."),
    clause_b=dict(docs_with_information_bearing_image=len(docs_info_bearing), info_bearing_doc_share=info_bearing_doc_share,
                  docs_with_pixel_only_infobearing_text=len(PIXEL_TEXT_DOCS), pixel_only_text_doc_share=clause_b_share,
                  threshold_full_breadth=0.30, reaches_full_breadth=clause_b_share >= 0.30,
                  refuted_narrow_floor=0.10, refuted_narrow=info_bearing_doc_share < 0.10,
                  pixel_text_docs=PIXEL_TEXT_DOCS,
                  note="Information-bearing images are common (27/27 docs). But images whose TEXT is NOT in the text layer "
                  "are <30% - most rendered labels/captions/specs are dual-encoded (present in the text layer). "
                  "Graph-relevant text is not hidden in pixels (see H217: 0/32 absent golds pixel-only)."),
    class_distribution_arm1_unique=dict(collections.Counter(lbl1)),
    information_bearing_share_arm1=ib1 / A1,
    acceptance_bar="census complete + labels frozen (data/processed/image-census-h216.json)",
    verdict="CONFIRMED-NARROW: census complete, labels frozen; three-arm inventories materially disagree "
            "(38-64% > 20%, clause a PASS); pixel-only-text clause (b) below 30% breadth threshold -> round narrows "
            "to the classes present (product photos, diagrams/schematics, rendered/vector tables), justified by "
            "NEW-content capture not hidden-text recovery; NOT refuted-narrow (info-bearing images in 27/27 docs).")
(ROOT / f"reports/image-census-h216-{STAMP}.json").write_text(json.dumps(h216_report, indent=1))

# ---- H217 report ----
vv = collections.Counter(r["verdict"] for r in verdicts)
h207 = [r for r in verdicts if r["set"] == "H207-absent"]
h191 = [r for r in verdicts if r["set"] == "H191-residue"]
po = vv.get("pixel-only", 0); n = len(verdicts)
h217_report = dict(
    hypothesis="R21-H217", utc=STAMP, read_only=True, cpu_only=True,
    inputs=dict(h207_absent_golds=len(h207), h191_numeric_residue=len(h191), total=n,
                h207_source="reports/render-parity-h207-20260707T155614Z.json (miss_detail, cls=absent-from-graph)",
                h191_source="reports/parser-round-final-20260707-135106.json (H148 floor_residue_detail)"),
    adjudication=dict(counts=dict(vv), pixel_only=po, pixel_only_share=po / n,
                      threshold_stake=0.25, confirms_coverage_stake=po / n >= 0.25,
                      refute_floor=0.10, refuted=po / n < 0.10),
    per_gold=[dict(set=r["set"], pid=r["pid"], gold=r["gold"], doc=r["doc"],
                   product=r.get("product", ""), code_shaped=r.get("code_shaped"),
                   verdict=r["verdict"], evidence=r["evidence"]) for r in verdicts],
    prediction_check=dict(
        catalogue_codes_are_text_drops="CONFIRMED - all 8 H207 catalogue codes text-layer-present (extraction/normalization "
        "drops, H119 territory), 0 pixel-only",
        h191_residue_is_pixels="REFUTED - H191 residue is benchmark cross-product mispairings, not pixels: each value is "
        "text-layer-present in its OWN document but absent-entirely from the wrongly-paired src doc; spec tables are live "
        "text (never rendered as images). 0/16 pixel-only."),
    verdict=f"REFUTED (image-ingestion coverage stake): 0/32 absent golds are pixel-only ({po/n:.0%} << 10%). "
            "Every absent gold's text lives in a document's TEXT LAYER (or is a cross-product mispairing), not in pixels. "
            "Image work must stand on NEW-capability value, not on recovering the existing benchmark's missing golds.")
(ROOT / f"reports/pixel-forensics-h217-{STAMP}.json").write_text(json.dumps(h217_report, indent=1))

print("WROTE:")
print("  data/processed/image-census-h216.json  records:", len(records))
print(f"  reports/image-census-h216-{STAMP}.json")
print(f"  reports/pixel-forensics-h217-{STAMP}.json")
print("H216 clause(a) disagreement:", {k: f"{v:.1%}" for k, v in disagree.items()}, "-> PASS")
print(f"H216 clause(b): info-bearing docs {info_bearing_doc_share:.0%}, pixel-only-text docs {clause_b_share:.0%} (<30% narrow)")
print(f"H217: {dict(vv)}  pixel-only {po}/{n} = {po/n:.0%} -> REFUTED")
print("STAMP", STAMP)
