# Logs

Background job logs for Knowledge Graph Foundry.

- `make-install.log` - environment creation and dependency installation
- `neo4j-verify.log` - Neo4j connectivity and plugin verification
- `cpap-ingest-*.log` - end-to-end ingestion runs on the CPAP corpus
- `cpap-rebuild.log` - full R1-R8 engine rebuild of the CPAP graph (R01 measurement)
- `cpap-rebuild-optimize.log` - communities + scorecard for the R01 rebuild
- `proposition-backfill.log` - R02-H11 proposition generation on the R01 graph
- `cpap-rebuild-h10.log` - H10/H12 rebuild against the second Neo4j (values-as-properties + provenance nodes)
- `cpap-rebuild-h10-resume.log` - resumed H10 rebuild on Haiku extraction after Bedrock quota outage
- `h10-optimize.log` - communities + propositions + densification on the rebuilt graph
- `probe-eval-phaseA.log`, `probe-eval-weak.log`, `probe-eval-r03.log` - probe evaluation notebook executions
- `repair-p09.log`, `repair-p19.log` - R04 targeted repair runs against the rebuilt graph
- `vllm-server.log` - local gpt-oss-120b vLLM server (port 8010, 96GB card)
- `r05-wave-*.log` - R05 longevity campaign wave ingestions on the local engine
