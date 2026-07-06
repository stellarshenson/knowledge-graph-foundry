# Logs

Background job logs for Knowledge Graph Foundry.

- `make-install.log` - environment creation and dependency installation
- `neo4j-verify.log` - Neo4j connectivity and plugin verification
- `cpap-ingest-*.log` - end-to-end ingestion runs on the CPAP corpus
- `cpap-rebuild.log` - full R1-R8 engine rebuild of the CPAP graph (R01 measurement)
- `cpap-rebuild-optimize.log` - communities + scorecard for the R01 rebuild
- `proposition-backfill.log` - R02-H11 proposition generation on the R01 graph
- `cpap-rebuild-h10.log` - H10/H12 rebuild against the second Neo4j (values-as-properties + provenance nodes)
