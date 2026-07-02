import sys
from pathlib import Path
import sys

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.rag.retriever import query_supabase, deterministic_embedding, local_fallback


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
