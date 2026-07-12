

class TestFanoutRelationBoost:
    """R44-H468: relation-type-aware fanout ranking (default off)."""

    ROWS = [
        {"rel": "STARRED", "name": "Actor A", "emb": [1.0, 0.0]},
        {"rel": "STARRED", "name": "Actor B", "emb": [0.99, 0.1]},
        {"rel": "DIRECTED_BY", "name": "The Director", "emb": [0.8, 0.2]},
    ]

    def test_off_is_lexical_only(self):
        from knowledge_graph_foundry.graph.graphrag import cap_fanout
        top = cap_fanout(self.ROWS, [1.0, 0.0], 2)
        assert [r["name"] for r in top] == ["Actor A", "Actor B"]  # director crowded out

    def test_boost_promotes_relation_match(self):
        from knowledge_graph_foundry.graph.graphrag import cap_fanout
        top = cap_fanout(
            self.ROWS, [1.0, 0.0], 2,
            query_text="who is the director of the film", relation_boost=0.3,
        )
        assert "The Director" in [r["name"] for r in top]

    def test_boost_without_match_changes_nothing(self):
        from knowledge_graph_foundry.graph.graphrag import cap_fanout
        top = cap_fanout(
            self.ROWS, [1.0, 0.0], 2,
            query_text="what is the budget", relation_boost=0.3,
        )
        assert [r["name"] for r in top] == ["Actor A", "Actor B"]
