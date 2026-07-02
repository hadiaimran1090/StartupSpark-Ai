from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.rag.retriever import query_supabase

if __name__ == '__main__':
    print('Calling query_supabase in rpc mode...')
    res = query_supabase('patient triage automation in hospitals', domain='healthcare_ai', top_k=3, mode='rpc')
    print('Result length:', len(res))
    for score, r in res:
        print(score, r.get('source'))
