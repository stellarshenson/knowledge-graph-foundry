"""Tests for the graph-resident ingest run lease."""

import os
import time
from unittest.mock import MagicMock, patch

import pytest

from knowledge_graph_foundry.graph.lock import (
    acquire_lease,
    heartbeat,
    lease_holder,
    new_run_id,
    release_lease,
)
from knowledge_graph_foundry.pipeline import Foundry, FoundryError
from knowledge_graph_foundry.settings import Settings


def _driver_returning(record):
    driver = MagicMock()
    session = driver.session.return_value.__enter__.return_value
    session.run.return_value.single.return_value = record
    return driver, session


class TestLeaseUnit:
    def test_acquire_success(self):
        driver, session = _driver_returning({"run_id": "abc"})
        assert acquire_lease(driver, "abc", 180) is True
        cypher = session.run.call_args.args[0]
        assert "KGFLock" in cypher
        assert "l.probe" in cypher  # write-lock serialization before the check
        assert session.run.call_args.kwargs["ttl_ms"] == 180_000

    def test_acquire_held_by_other(self):
        driver, _ = _driver_returning(None)
        assert acquire_lease(driver, "abc", 180) is False

    def test_heartbeat_lost_lease(self):
        driver, _ = _driver_returning(None)
        assert heartbeat(driver, "abc") is False

    def test_holder_none_when_free(self):
        driver, _ = _driver_returning(None)
        assert lease_holder(driver) is None

    def test_ingest_fails_fast_when_lease_held(self):
        foundry = Foundry(Settings())
        with (
            patch.object(Foundry, "driver", new_callable=lambda: property(lambda self: MagicMock())),
            patch("knowledge_graph_foundry.graph.lock.acquire_lease", return_value=False),
            patch(
                "knowledge_graph_foundry.graph.lock.lease_holder",
                return_value={"holder": "host:123", "run_id": "other", "age_seconds": 5.0},
            ),
        ):
            with pytest.raises(FoundryError, match="host:123"):
                foundry.ingest("somewhere")


pytestmark_integration = pytest.mark.skipif(
    os.environ.get("KGF_INTEGRATION") != "1", reason="needs live neo4j (KGF_INTEGRATION=1)"
)


@pytest.mark.integration
@pytestmark_integration
class TestLeaseIntegration:
    @pytest.fixture()
    def driver(self):
        from knowledge_graph_foundry.graphdb import create_driver
        from knowledge_graph_foundry.settings import load_settings

        driver = create_driver(load_settings().neo4j)
        yield driver
        with driver.session() as session:
            session.run("MATCH (l:KGFLock {id: 'ingest'}) DELETE l").consume()
        driver.close()

    def test_exclusive_claim_and_release(self, driver):
        a, b = new_run_id(), new_run_id()
        assert acquire_lease(driver, a, ttl_seconds=180) is True
        assert acquire_lease(driver, b, ttl_seconds=180) is False
        info = lease_holder(driver)
        assert info["run_id"] == a
        release_lease(driver, a)
        assert lease_holder(driver) is None
        assert acquire_lease(driver, b, ttl_seconds=180) is True

    def test_reacquire_own_lease_is_idempotent(self, driver):
        a = new_run_id()
        assert acquire_lease(driver, a, ttl_seconds=180) is True
        assert acquire_lease(driver, a, ttl_seconds=180) is True

    def test_stale_lease_reclaimed_and_heartbeat_detects_loss(self, driver):
        a, b = new_run_id(), new_run_id()
        assert acquire_lease(driver, a, ttl_seconds=1) is True
        time.sleep(1.5)
        assert acquire_lease(driver, b, ttl_seconds=180) is True  # stale takeover
        assert heartbeat(driver, a) is False  # original run detects the loss
        assert heartbeat(driver, b) is True

    def test_heartbeat_keeps_lease_live(self, driver):
        a, b = new_run_id(), new_run_id()
        assert acquire_lease(driver, a, ttl_seconds=2) is True
        for _ in range(3):
            time.sleep(0.8)
            assert heartbeat(driver, a) is True
        assert acquire_lease(driver, b, ttl_seconds=2) is False
