"""LLM extraction per chunk using Bedrock runtime."""

from __future__ import annotations

import json
import re

import boto3
from loguru import logger

from kg_builder_cli.types.document import Chunk
from kg_builder_cli.types.extraction import Entity, Relationship


def extract_chunk(
    chunk: Chunk,
    prompt: str,
    model_id: str,
    region: str,
    profile: str,
) -> tuple[list[Entity], list[Relationship]]:
    """Extract entities and relationships from a chunk using Bedrock.

    Sends the prompt to the specified model, parses the JSON response,
    and converts to Entity and Relationship objects.

    Returns empty lists on JSON parse errors.
    """
    try:
        session = boto3.Session(profile_name=profile if profile else None)
        client = session.client("bedrock-runtime", region_name=region)

        response = client.converse(
            modelId=model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ],
            inferenceConfig={"temperature": 0.0},
        )

        output_text = response["output"]["message"]["content"][0]["text"]
        data = _parse_json_response(output_text)

        if data is None:
            logger.warning(
                "Failed to parse JSON from LLM response for chunk {}",
                chunk.id,
            )
            return [], []

        entities = _build_entities(data.get("entities", []), chunk, model_id)
        relationships = _build_relationships(
            data.get("relationships", []), chunk, model_id
        )

        logger.debug(
            "Chunk {} -> {} entities, {} relationships",
            chunk.id,
            len(entities),
            len(relationships),
        )
        return entities, relationships

    except Exception:
        logger.exception("Extraction failed for chunk {}", chunk.id)
        return [], []


def _parse_json_response(text: str) -> dict | None:
    """Parse JSON from LLM response, handling markdown code blocks."""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding first { to last }
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None


def _build_entities(
    raw_entities: list[dict], chunk: Chunk, model_id: str
) -> list[Entity]:
    """Convert raw entity dicts to Entity objects."""
    entities: list[Entity] = []
    for raw in raw_entities:
        try:
            entities.append(
                Entity(
                    id=raw.get("id", ""),
                    name=raw.get("name", ""),
                    type=raw.get("type", ""),
                    description=raw.get("description", ""),
                    properties=raw.get("properties", {}),
                    source_chunks=[chunk.id],
                    confidence=float(raw.get("confidence", 1.0)),
                    extraction_model=model_id,
                )
            )
        except Exception:
            logger.warning("Skipping malformed entity: {}", raw)
    return entities


def _build_relationships(
    raw_rels: list[dict], chunk: Chunk, model_id: str
) -> list[Relationship]:
    """Convert raw relationship dicts to Relationship objects."""
    relationships: list[Relationship] = []
    for raw in raw_rels:
        try:
            relationships.append(
                Relationship(
                    source=raw.get("source", ""),
                    target=raw.get("target", ""),
                    type=raw.get("type", ""),
                    description=raw.get("description", ""),
                    properties=raw.get("properties", {}),
                    source_chunks=[chunk.id],
                    confidence=float(raw.get("confidence", 1.0)),
                    extraction_model=model_id,
                )
            )
        except Exception:
            logger.warning("Skipping malformed relationship: {}", raw)
    return relationships
