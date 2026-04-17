"""Embedding generation using Amazon Titan Text Embeddings v2."""

from __future__ import annotations

import json
import os

import boto3
from loguru import logger

from kgf.types.extraction import Entity


def generate_embeddings(
    entities: list[Entity],
    model: str = "amazon.titan-embed-text-v2:0",
    batch_size: int = 25,
) -> list[Entity]:
    """Generate embeddings for entities using Titan v2 via Bedrock.

    Input text per entity: "{type}: {name} - {description[:200]}"
    Titan v2 produces 1024-dimensional vectors.
    Populates entity.embedding field in place and returns the list.
    """
    if not entities:
        return entities

    profile = os.environ.get("AWS_PROFILE", "kolomolo")
    region = os.environ.get(
        "AWS_REGION_NAME", os.environ.get("AWS_DEFAULT_REGION", "eu-central-1")
    )

    session = boto3.Session(profile_name=profile, region_name=region)
    client = session.client("bedrock-runtime")

    total = len(entities)
    embedded = 0

    for offset in range(0, total, batch_size):
        batch = entities[offset : offset + batch_size]
        for entity in batch:
            text = f"{entity.type}: {entity.name} - {entity.description[:200]}"
            try:
                response = client.invoke_model(
                    modelId=model,
                    contentType="application/json",
                    accept="application/json",
                    body=json.dumps({"inputText": text}),
                )
                body = json.loads(response["body"].read())
                entity.embedding = body["embedding"]
                embedded += 1
            except Exception:
                logger.warning("Embedding failed for entity '{}'", entity.name)

        if embedded % 50 == 0 or offset + batch_size >= total:
            logger.info("Embeddings: {}/{}", embedded, total)

    logger.info("Generated embeddings for {}/{} entities", embedded, total)
    return entities
