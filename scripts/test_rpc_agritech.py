from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.rag.retriever import query_supabase
print('RPC agritech...')
res = query_supabase('satellite-based crop yield prediction', domain='agritech', top_k=5, mode='rpc')
print('len res:', len(res))
for score,row in res:
    print(score, row.get('source'))
