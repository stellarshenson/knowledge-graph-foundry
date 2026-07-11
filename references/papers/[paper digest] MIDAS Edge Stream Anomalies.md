**MIDAS: Microcluster-Based Detector of Anomalies in Edge Streams, Bhatia, Hooi, Yoon, Shin, Faloutsos, AAAI 2020 (arXiv 1911.04464)**

Streaming anomaly detection on EDGE ARRIVALS (not snapshots): detect microclusters - sudden bursts of suspiciously similar edges - in **constant time and memory per edge**, with a chi-squared score carrying **theoretical false-positive probability bounds**, running **162-644x faster** than prior edge-stream detectors (SEDANSPOT) at up to **48% higher AUC** (DARPA intrusion data: MIDAS-R AUC ~0.95 class vs ~0.64 baselines).

**Key mechanism**
- Two Count-Min-Sketches per edge identity (u,v): total count s_uv over all time, current-window count a_uv (reset per tick)
- Score = chi-squared statistic comparing current-window mass against the historical mean under a stationarity null: (a − s/t)^2 · t^2 / (s(t−1))
- MIDAS-R adds temporal smoothing (decay instead of reset) and spatial relations (node-level sketches catch bursts spread over many edge identities)
- The chi-squared tail bound converts the sketch score into a priced alarm: choose threshold from a target false-positive rate

**Main findings**
- Microcluster (burst) anomalies are invisible to whole-snapshot methods until aggregated - edge-granularity catches them at arrival
- Constant-memory sketches make the monitor deployable INSIDE an ingest loop with zero growth in state

**Key takeaways**
- The ingest-time (online) complement to offline snapshot forensics: KGF's extractor emits relationship streams per document; a MIDAS-class sketch on (head-label, rel-type, tail-label) or (entity, entity) arrivals flags "this document just emitted an anomalous burst of near-identical edges" at the document that does it
- Burst-of-similar-edges is exactly the schema-flood signature a 2wiki comparison corpus produces (many film→director, director→country edges of one shape) - the suspected REG-1 window class
- The priced-alarm construction (score with a probability bound, threshold from target FP rate) satisfies KGF's H351 noise-floor doctrine by design

**Tags**: #EdgeStreams #StreamingAnomalyDetection #CountMinSketch #Microclusters #PricedAlarms

**Source**: https://arxiv.org/abs/1911.04464. Local: [paper] MIDAS Edge Stream Anomalies, 2019-11.pdf
