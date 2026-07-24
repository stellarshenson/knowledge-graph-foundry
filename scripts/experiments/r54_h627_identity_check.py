"""Is meanpool scoring EXACTLY a one-step smoothing of the raw similarity vector?

  z_u = (1-a) e_u + a (Ahat e)_u ,  score = <q, z_u>/||z_u||
  <q, Ahat e>_u = sum_w Ahat_uw <q, e_w> = (Ahat s)_u    where s = raw score vector
  => score = [(1-a) s_u + a (Ahat s)_u] / ||z_u||   with ||z_u|| query-INDEPENDENT
"""
import json, re
import numpy as np
from pathlib import Path
from scipy.sparse import csr_matrix

C = Path("/home/lab/workspace/learning/projects/knowledge-graph-foundry/tmp/results/r47")
meta = json.loads((C/"ents_meta.json").read_text())
titan = np.load(C/"titan_emb.npy"); n = len(meta)
idx = {m["id"]: i for i, m in enumerate(meta)}
edges = json.loads((C/"edges.json").read_text())
ij = np.array([[idx[a], idx[b]] for a, b in edges if a in idx and b in idx])
adj = csr_matrix((np.ones(len(ij)), (ij[:,0], ij[:,1])), shape=(n,n))
adj = ((adj+adj.T) > 0).astype(float).tocsr()
d = np.asarray(adj.sum(1)).ravel(); d[d == 0] = 1.0
Ahat = csr_matrix((1/d, (np.arange(n), np.arange(n))), shape=(n,n)) @ adj

E = titan/np.linalg.norm(titan, axis=1, keepdims=True)
a = 0.5
Z = (1-a)*E + a*(Ahat@E)
zn = np.linalg.norm(Z, axis=1); zn[zn == 0] = 1.0
Zn = Z/zn[:,None]

with np.load(C/"titan_probe_emb.npz") as zz:
    pids = list(zz.keys())[:20]
    maxerr, maxrank = 0.0, 0
    for pid in pids:
        q = zz[pid].astype(np.float64); q /= np.linalg.norm(q)
        direct = Zn @ q                       # what the gate computed
        s = E @ q                             # raw similarity vector
        smoothed = ((1-a)*s + a*(Ahat@s))/zn  # the claimed identity
        maxerr = max(maxerr, float(np.abs(direct-smoothed).max()))
        # do they induce the SAME top-16?
        t1 = set(np.argsort(-direct)[:16].tolist()); t2 = set(np.argsort(-smoothed)[:16].tolist())
        maxrank = max(maxrank, 16-len(t1 & t2))
print(f"probes checked      : {len(pids)}")
print(f"max abs score diff  : {maxerr:.3e}")
print(f"max top-16 disagree : {maxrank} of 16")
print(f"||z|| is query-independent: precomputable, {n} scalars")
