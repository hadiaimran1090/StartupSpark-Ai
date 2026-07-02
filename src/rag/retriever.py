from pathlib import Path
import os
import json
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")


def deterministic_embedding(text, dim=768):
    from src.rag.ingest import deterministic_embedding as det

    return det(text, dim=dim)


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
            dot = sum(a * b for a, b in zip(query_emb, emb))
            norm_a = sqrt(sum(a * a for a in query_emb))
            norm_b = sqrt(sum(b * b for b in emb))
            sim = dot / (norm_a * norm_b + 1e-10)
            candidates.append((sim, r))
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[:top_k]


def query_supabase(query_text: str, domain: str = "healthcare_ai", top_k: int = 5, mode: str = "auto"):
    emb = deterministic_embedding(query_text)

    # If mode is local-only, skip Supabase entirely
    if mode == "local":
        return local_fallback(emb, domain, top_k=top_k)

    try:
        from supabase import create_client
    except Exception:
        # supabase client not available -> fallback unless RPC-only
        if mode == "rpc":
            return []
        return local_fallback(emb, domain, top_k=top_k)

    # create client
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

    try:
        res = client.rpc("match_startup_knowledge", {"query_embedding": emb, "query_domain": domain, "match_count": top_k}).execute()
        if getattr(res, "error", None):
            raise RuntimeError(res.error)
        rows = getattr(res, "data", [])

        if mode == "rpc":
            # if RPC returned rows, normalize and return them
            if rows:
                out = []
                for r in rows:
                    sim = r.get("similarity") if isinstance(r.get("similarity"), (int, float)) else None
                    norm = {
                        "id": r.get("id"),
                        "domain": r.get("domain"),
                        "title": r.get("title"),
                        "text": r.get("content") or r.get("text"),
                        "metadata": r.get("metadata"),
                        "source": r.get("source") or r.get("title"),
                    }
                    out.append((sim, norm))
                return out
            # RPC returned no rows — try local fallback to avoid empty UI results
            fallback = local_fallback(emb, domain, top_k=top_k)
            # attach debug row indicating RPC returned nothing
            debug_row = {"source": "__rpc_empty__", "title": "RPC returned no rows", "text": "RPC query returned empty result; used local fallback"}
            fallback.append((None, debug_row))
            return fallback

        # auto mode: use RPC rows if present; otherwise fallback to local similarity
        if not rows:
            return local_fallback(emb, domain, top_k=top_k)
        out = []
        for r in rows:
            sim = r.get("similarity") if isinstance(r.get("similarity"), (int, float)) else None
            norm = {
                "id": r.get("id"),
                "domain": r.get("domain"),
                "title": r.get("title"),
                "text": r.get("content") or r.get("text"),
                "metadata": r.get("metadata"),
                "source": r.get("source") or r.get("title"),
            }
            out.append((sim, norm))
        return out
    except Exception as e:
        # RPC error: surface the error to the UI as a debug row
        err_text = str(e)
        debug_row = {"source": "__rpc_error__", "title": "RPC error", "text": err_text}
        if mode == "rpc":
            return [(None, debug_row)]
        # auto: fallback to local but include debug row at the end
        fallback = local_fallback(emb, domain, top_k=top_k)
        fallback.append((None, debug_row))
        return fallback
