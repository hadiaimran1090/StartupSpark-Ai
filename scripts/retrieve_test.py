import sys
from pathlib import Path
import os
import json
from dotenv import load_dotenv

# Ensure project root on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

def deterministic_embedding(text, dim=768):
    from src.rag.ingest import deterministic_embedding as det_emb
    return det_emb(text, dim=dim)


def local_fallback(query_emb, domain, top_k=5, chunks_dir="data/chunks"):
    from math import sqrt
    files = sorted(Path(chunks_dir).glob(f"{domain}__*.jsonl"))
    candidates = []
    for f in files:
        for line in f.open("r", encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            emb = r.get("embedding")
            if not emb:
                continue
            # cosine similarity
            dot = sum(a*b for a,b in zip(query_emb, emb))
            norm_a = sqrt(sum(a*a for a in query_emb))
            norm_b = sqrt(sum(b*b for b in emb))
            sim = dot / (norm_a*norm_b + 1e-10)
            candidates.append((sim, r))
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[:top_k]


def query_supabase(query_text: str, domain: str = "healthcare_ai", top_k: int = 5):
    try:
        from supabase import create_client
    except Exception:
        print("supabase client not installed; falling back to local retrieval")
        emb = deterministic_embedding(query_text)
        return local_fallback(emb, domain, top_k=top_k)

    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        print("Supabase credentials missing; falling back to local retrieval")
        emb = deterministic_embedding(query_text)
        return local_fallback(emb, domain, top_k=top_k)

    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    emb = deterministic_embedding(query_text)

    # Try RPC function first
    try:
        res = client.rpc("match_startup_knowledge", {"query_embedding": emb, "query_domain": domain, "match_count": top_k}).execute()
        if getattr(res, "error", None):
            raise RuntimeError(res.error)
        rows = getattr(res, "data", [])
        # compute similarity score if returned
        out = []
        for r in rows:
            sim = r.get("similarity") if isinstance(r.get("similarity"), (int, float)) else None
            out.append((sim, r))
        return out
    except Exception as e:
        print("RPC failed or not available, falling back to local similarity:", e)
        return local_fallback(emb, domain, top_k=top_k)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default="patient triage automation in hospitals")
    parser.add_argument("--domain", default="healthcare_ai")
    parser.add_argument("--topk", type=int, default=5)
    parser.add_argument("--force-local", action="store_true", help="Force local chunk similarity fallback")
    args = parser.parse_args()

    query = args.query
    domain = args.domain
    print(f"Running retrieval test for query: '{query}' domain: {domain}")
    if args.force_local:
        emb = deterministic_embedding(query)
        results = local_fallback(emb, domain, top_k=args.topk)
    else:
        results = query_supabase(query, domain=domain, top_k=args.topk)
    print("Top results:\n")
    for score, row in results:
        print(f"score={score}\nsource={row.get('source')}, title={row.get('title')}\ntext_preview={row.get('text')[:300]}\n---\n")
