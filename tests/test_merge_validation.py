"""Tests for post-LLM merge validation."""

import pytest

from kg_builder_cli.curing.merge_validation import (
    ClusteringValidationResult,
    MergeValidation,
    validate_type_clustering,
    _name_similarity,
    _description_coherence,
    _split_pascal_case,
)


class FakeEntity:
    """Minimal entity stub for testing."""

    def __init__(self, type: str, description: str = ""):
        self.type = type
        self.description = description


class TestNameSimilarity:
    def test_identical_names(self):
        assert _name_similarity("Device", "Device") == 1.0

    def test_formatting_variant(self):
        """MedicalCondition vs Medical_Condition should be high."""
        score = _name_similarity("MedicalCondition", "Medical_Condition")
        assert score > 0.7

    def test_unrelated_names(self):
        """Mode vs Role should be low."""
        score = _name_similarity("Mode", "Role")
        assert score < 0.4

    def test_gas_vs_accessory(self):
        """Gas vs Accessory should be very low."""
        score = _name_similarity("Gas", "Accessory")
        assert score < 0.3


class TestSplitPascalCase:
    def test_simple(self):
        assert _split_pascal_case("MedicalDevice") == {"medical", "device"}

    def test_single_word(self):
        assert _split_pascal_case("Device") == {"device"}

    def test_underscore_variant(self):
        assert _split_pascal_case("Medical_Condition") == {"medical", "condition"}


class TestDescriptionCoherence:
    def test_no_descriptions(self):
        """No descriptions returns neutral 0.5."""
        score = _description_coherence("A", "B", {})
        assert score == 0.5

    def test_similar_descriptions(self):
        descs = {
            "MedicalCondition": ["chronic respiratory disease", "sleep apnea condition"],
            "Medical_Condition": ["respiratory disease treatment", "medical condition diagnosis"],
        }
        score = _description_coherence("MedicalCondition", "Medical_Condition", descs)
        assert score > 0.2

    def test_dissimilar_descriptions(self):
        descs = {
            "Mode": ["ventilation mode setting", "CPAP pressure mode"],
            "Role": ["clinical role of physician", "patient role in treatment"],
        }
        score = _description_coherence("Mode", "Role", descs)
        assert score < 0.4


class TestValidateTypeClustering:
    def test_identity_merges_skip_validation(self):
        """Types mapping to themselves should pass without validation."""
        mapping = {"Device": "Device", "Person": "Person"}
        result = validate_type_clustering(mapping, {}, [])
        assert result.flagged_count == 0
        assert result.approved_mapping == mapping
        assert len(result.merge_validations) == 0

    def test_high_similarity_approved(self):
        """Formatting variants should pass validation."""
        mapping = {"MedicalCondition": "Medical_Condition"}
        entities = [
            FakeEntity("MedicalCondition", "chronic respiratory condition"),
            FakeEntity("Medical_Condition", "respiratory condition treatment"),
        ]
        freqs = {"MedicalCondition": 10, "Medical_Condition": 8}
        result = validate_type_clustering(mapping, freqs, entities)
        assert result.flagged_count == 0
        assert result.approved_mapping["MedicalCondition"] == "Medical_Condition"

    def test_low_similarity_flagged(self):
        """Semantically different types should be flagged and reverted."""
        mapping = {"Mode": "Role"}
        entities = [
            FakeEntity("Mode", "ventilation pressure mode"),
            FakeEntity("Role", "clinical physician role"),
        ]
        freqs = {"Mode": 15, "Role": 10}
        result = validate_type_clustering(mapping, freqs, entities)
        assert result.flagged_count == 1
        assert result.approved_mapping["Mode"] == "Mode"  # reverted to identity

    def test_cpap_bad_merges_flagged(self):
        """Known bad merges from CPAP data should all be flagged."""
        mapping = {
            "Mode": "Role",
            "Gas": "Accessory",
            "Software": "Feature",
        }
        entities = [
            FakeEntity("Mode", "ventilation mode"),
            FakeEntity("Role", "user role"),
            FakeEntity("Gas", "oxygen supply gas"),
            FakeEntity("Accessory", "mask accessory"),
            FakeEntity("Software", "device firmware software"),
            FakeEntity("Feature", "product feature"),
        ]
        freqs = {"Mode": 15, "Role": 10, "Gas": 8, "Accessory": 12, "Software": 5, "Feature": 20}
        result = validate_type_clustering(mapping, freqs, entities)
        assert result.flagged_count == 3
        assert result.approved_mapping["Mode"] == "Mode"
        assert result.approved_mapping["Gas"] == "Gas"
        assert result.approved_mapping["Software"] == "Software"

    def test_approved_mapping_reverts_flagged(self):
        """approved_mapping should have identity for flagged, target for approved."""
        mapping = {
            "MedicalCondition": "Medical_Condition",  # should pass
            "Mode": "Role",  # should fail
            "Device": "Device",  # identity, skipped
        }
        entities = [
            FakeEntity("MedicalCondition", "chronic condition"),
            FakeEntity("Medical_Condition", "medical condition"),
            FakeEntity("Mode", "ventilation mode"),
            FakeEntity("Role", "clinical role"),
        ]
        freqs = {"MedicalCondition": 10, "Medical_Condition": 8, "Mode": 15, "Role": 10}
        result = validate_type_clustering(mapping, freqs, entities)
        assert result.approved_mapping["Device"] == "Device"
        assert result.approved_mapping["Mode"] == "Mode"  # reverted
        assert result.approved_mapping["MedicalCondition"] == "Medical_Condition"  # approved

    def test_entity_with_no_descriptions_neutral(self):
        """Type with no entity descriptions should get neutral coherence score."""
        mapping = {"TypeA": "TypeB"}
        freqs = {"TypeA": 5, "TypeB": 5}
        result = validate_type_clustering(mapping, freqs, [])
        # With no entities, desc coherence = 0.5 (neutral)
        assert len(result.merge_validations) == 1
        v = result.merge_validations[0]
        assert v.description_coherence == 0.5
