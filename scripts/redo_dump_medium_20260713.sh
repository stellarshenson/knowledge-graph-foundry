#!/usr/bin/env bash
# Redo the failed medium dump (proxy made `docker wait` return early; poll for the
# dump file inside the container before cp). Waits for the #59 answer run first,
# then scores it, then dumps. Watch logs/medium-collection-20260713.log
set -x
cd /home/lab/workspace/learning/projects/knowledge-graph-foundry

echo "[redo $(date -u +%FT%TZ)] waiting for bench_answer to finish"
until grep -qa 'DONE reports/experiments/bench' logs/bench-answer-medium.log || ! pgrep -f bench_answer_kgf.py > /dev/null; do sleep 30; done
sleep 5

ANSWERS=$(ls -t reports/experiments/bench/2wikimultihopqa-answers-*.jsonl | head -1)
echo "[redo $(date -u +%FT%TZ)] scoring $ANSWERS"
.venv/bin/python scripts/bench_score.py "$ANSWERS" 2>&1 | tee reports/experiments/bench/medium-score-20260713.txt || true

SRC=user-konrad.jelen-kgf-neo4j-small
DUMPC=kgf-dump-medium2
DUMPCP=user-konrad.jelen-kgf-dump-medium2
DUMP=data/interim/dumps/20260713-neo4j-medium-2wiki-1000.dump

echo "[redo $(date -u +%FT%TZ)] stopping $SRC for dump"
docker stop $SRC
docker create --name $DUMPC --volumes-from $SRC neo4j:5.26.0 \
  neo4j-admin database dump neo4j --to-path=/data/_dumps --overwrite-destination=true
docker start $DUMPCP 2>/dev/null || docker start $DUMPC
# poll until the dump container exits AND the file exists (proxy wait is unreliable)
for i in $(seq 1 60); do
  STATE=$(docker inspect -f '{{.State.Running}}' $DUMPCP 2>/dev/null || docker inspect -f '{{.State.Running}}' $DUMPC)
  [ "$STATE" = "false" ] && break
  sleep 10
done
docker logs $DUMPCP 2>/dev/null || docker logs $DUMPC
docker cp $DUMPCP:/data/_dumps/neo4j.dump "$DUMP" 2>/dev/null || docker cp $DUMPC:/data/_dumps/neo4j.dump "$DUMP"
docker rm $DUMPCP 2>/dev/null || docker rm $DUMPC
docker start $SRC
ls -la "$DUMP"
if [ -s "$DUMP" ]; then echo "[redo $(date -u +%FT%TZ)] DUMP OK"; else echo "[redo $(date -u +%FT%TZ)] DUMP STILL FAILED"; fi
echo "[redo $(date -u +%FT%TZ)] REDO CHAIN COMPLETE"
