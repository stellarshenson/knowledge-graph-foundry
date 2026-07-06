"""Ingest run lease - graph-resident concurrency control.

A single (:KGFLock {id: 'ingest'}) node arbitrates who may mutate the
foundry state. Claims are atomic: the claim statement takes the node's
write lock first (SET l.probe) so competing transactions serialize, then
checks the lease. A lease is reclaimable when it is free, already ours, or
stale (no heartbeat within the TTL) - a crashed run never wedges ingestion.
Server-side timestamp() keeps competing clients on one clock.
"""

from __future__ import annotations

import os
import socket
import uuid

from neo4j import Driver

_CLAIM = """
MERGE (l:KGFLock {id: 'ingest'})
SET l.probe = timestamp()
WITH l, timestamp() AS now
WHERE l.run_id IS NULL OR l.run_id = $run_id
   OR l.heartbeat < now - coalesce(l.ttl_ms, $ttl_ms)
SET l.run_id = $run_id, l.holder = $holder, l.heartbeat = now,
    l.acquired_at = now, l.ttl_ms = $ttl_ms
RETURN l.run_id AS run_id
"""

_HEARTBEAT = """
MATCH (l:KGFLock {id: 'ingest'})
WHERE l.run_id = $run_id
SET l.heartbeat = timestamp()
RETURN l.run_id AS run_id
"""

_RELEASE = """
MATCH (l:KGFLock {id: 'ingest'})
WHERE l.run_id = $run_id
SET l.run_id = NULL, l.holder = NULL, l.heartbeat = NULL, l.acquired_at = NULL,
    l.ttl_ms = NULL
"""

_HOLDER = """
MATCH (l:KGFLock {id: 'ingest'})
RETURN l.run_id AS run_id, l.holder AS holder, l.heartbeat AS heartbeat,
       timestamp() AS now
"""


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def default_holder() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def acquire_lease(
    driver: Driver, run_id: str, ttl_seconds: int, holder: str | None = None
) -> bool:
    """Claim the ingest lease. True on success; False when another live
    run holds it."""
    with driver.session() as session:
        record = session.run(
            _CLAIM,
            run_id=run_id,
            ttl_ms=ttl_seconds * 1000,
            holder=holder or default_holder(),
        ).single()
    return record is not None and record["run_id"] == run_id


def heartbeat(driver: Driver, run_id: str) -> bool:
    """Refresh the lease; False when the lease was lost (stolen after stale)."""
    with driver.session() as session:
        record = session.run(_HEARTBEAT, run_id=run_id).single()
    return record is not None


def release_lease(driver: Driver, run_id: str) -> None:
    with driver.session() as session:
        session.run(_RELEASE, run_id=run_id).consume()


def lease_holder(driver: Driver) -> dict | None:
    """Current lease info, or None when free. Includes staleness."""
    with driver.session() as session:
        record = session.run(_HOLDER).single()
    if record is None or record["run_id"] is None:
        return None
    return {
        "run_id": record["run_id"],
        "holder": record["holder"],
        "age_seconds": (record["now"] - record["heartbeat"]) / 1000.0,
    }
