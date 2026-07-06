"""R04-H21 identity audit - deterministic alias detection.

Fixtures mirror the measured P09 evidence: the SleepStyle 200 manual defers
to "the HC230-Series Product range ... of this manual" (deictic), the HC230
family shares the model-code token, and SmartRamp/Smart Ramp differ only in
whitespace.
"""

from knowledge_graph_foundry.graph.aliases import (
    code_tokens,
    find_alias_pairs,
    normalize_name,
)


class TestDetectors:
    def test_code_tokens_mixed_alnum_only(self):
        assert code_tokens("HC230 Product Range") == {"hc230"}
        assert code_tokens("HC230-Series") == {"hc230"}
        assert code_tokens("900HC230 Compliance Maximizer") == {"900hc230"}
        assert code_tokens("AirSense 10") == set()  # pure-letter + pure-digit tokens
        assert code_tokens("DreamStation") == set()

    def test_normalized_name(self):
        assert normalize_name("Smart Ramp") == normalize_name("SmartRamp")
        assert normalize_name("Auto Ramp") != normalize_name("SmartRamp")


class TestFindAliasPairs:
    NAMES = {
        "e_sleepstyle": "SleepStyle 200 Series",
        "e_hc230series": "HC230-Series",
        "e_hc230range": "HC230 Product Range",
        "e_maximizer": "900HC230 Compliance Maximizer",
        "e_smartramp": "SmartRamp",
        "e_smart_ramp": "Smart Ramp",
        "e_dreamstation": "DreamStation",
    }

    def _pairs(self, doc_chunks):
        return find_alias_pairs(self.NAMES, doc_chunks)

    def _pairset(self, pairs):
        return {frozenset((l, r)) for l, r, _, _ in pairs}

    def test_model_code_clusters_hc230_family_not_the_software(self):
        pairs = self._pairs({})
        ps = self._pairset(pairs)
        assert frozenset(("e_hc230series", "e_hc230range")) in ps
        assert not any("e_maximizer" in p for p in ps)  # 900HC230 is a different code

    def test_normalized_name_merges_smartramp(self):
        ps = self._pairset(self._pairs({}))
        assert frozenset(("e_smartramp", "e_smart_ramp")) in ps

    def test_deictic_assertion_links_document_primary(self):
        doc = {
            "d1": [
                "The SleepStyle 200 Series is easy to use. SleepStyle 200 Series "
                "settings are on the display.",
                "Please refer to the HC230-Series Product range listed in the "
                "Appendix section of this manual.",
            ]
        }
        pairs = self._pairs(doc)
        deictic = [(l, r) for l, r, m, _ in pairs if m == "deictic_assertion"]
        assert ("e_sleepstyle", "e_hc230series") in deictic

    def test_explicit_assertion(self):
        doc = {"d1": ["The DreamStation, also known as the SleepStyle 200 Series, ships in two variants."]}
        pairs = self._pairs(doc)
        explicit = [(l, r) for l, r, m, _ in pairs if m == "explicit_assertion"]
        assert len(explicit) == 1

    def test_no_alias_between_unrelated_devices(self):
        doc = {"d1": ["The DreamStation is quiet. The SleepStyle 200 Series is compact."]}
        ps = self._pairset(self._pairs(doc))
        assert frozenset(("e_dreamstation", "e_sleepstyle")) not in ps


class TestFalseAliasGuards:
    """Iteration 2 fixes, each pinned to a measured false alias."""

    def test_measurement_tokens_are_not_model_codes(self):
        assert code_tokens("15mm Tubing") == set()
        assert code_tokens("Thermistor (oral, adult, 1.5mm connectors)") == set()
        assert code_tokens("2.5kg humidifier") == set()
        assert code_tokens("HC230 Product Range") == {"hc230"}  # real codes survive
        assert code_tokens("RJ9 to 2.5mm 3 inch Female Adapter Cable") == {"rj9"}

    def test_generic_name_cannot_be_document_primary(self):
        from knowledge_graph_foundry.graph.aliases import is_specific_name

        assert not is_specific_name("Device")
        assert not is_specific_name("Therapy")
        assert is_specific_name("SleepStyle 200 Series")
        assert is_specific_name("HC230-Series")  # single token but carries a code

    def test_deictic_skips_generic_primary(self):
        names = {
            "e_generic": "Device",
            "e_sleepstyle": "SleepStyle 200 Series",
            "e_hc230series": "HC230-Series",
        }
        doc = {
            "d1": [
                "The device is easy to use. The device has a display. The device "
                "heats water. The SleepStyle 200 Series ships with a chamber.",
                "Please refer to the HC230-Series Product range listed in the "
                "Appendix section of this manual.",
            ]
        }
        pairs = find_alias_pairs(names, doc)
        deictic = [(l, r) for l, r, m, _ in pairs if m == "deictic_assertion"]
        assert ("e_sleepstyle", "e_hc230series") in deictic
        assert not any(l == "e_generic" for l, _ in deictic)

    def test_filename_signal_beats_occurrence_count(self):
        """Iteration 3: 'Patient Menu' out-occurred the device name in its own
        manual; the document filename names the subject."""
        names = {
            "e_menu": "Patient Menu",
            "e_sleepstyle": "SleepStyle 200 Series",
            "e_hc230series": "HC230-Series",
        }
        doc = {
            "d1": [
                "Open the Patient Menu. The Patient Menu shows ramp. The Patient "
                "Menu shows humidity. The SleepStyle 200 Series ships ready to use.",
                "Please refer to the HC230-Series Product range listed in the "
                "Appendix section of this manual.",
            ]
        }
        pairs = find_alias_pairs(
            names, doc, doc_names={"d1": "SleepStyle_200_Operating_Manual.pdf"}
        )
        deictic = [(l, r) for l, r, m, _ in pairs if m == "deictic_assertion"]
        assert ("e_sleepstyle", "e_hc230series") in deictic
        assert not any(l == "e_menu" for l, _ in deictic)

    def test_provenance_membership_beats_text_substring(self):
        """Iteration 4: the manual's subject never appears verbatim in its own
        chunk text (stylized PDF rendering) - extraction provenance decides."""
        names = {
            "e_temp": "Operating temperature",
            "e_sleepstyle": "SleepStyle 200 Series",
            "e_hc230series": "HC230-Series",
        }
        doc = {
            "d1": [
                "Operating temperature is 5 to 35 C. Operating temperature must "
                "be checked. The unit ships ready to use.",
                "Please refer to the HC230-Series Product range listed in the "
                "Appendix section of this manual.",
            ]
        }
        pairs = find_alias_pairs(
            names,
            doc,
            doc_names={"d1": "SleepStyle_200_Operating_Manual.pdf"},
            entity_docs={"e_sleepstyle": {"d1"}, "e_temp": {"d1"}, "e_hc230series": {"d1"}},
        )
        deictic = [(l, r) for l, r, m, _ in pairs if m == "deictic_assertion"]
        assert ("e_sleepstyle", "e_hc230series") in deictic
