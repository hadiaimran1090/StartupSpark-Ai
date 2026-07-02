import os
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from supabase import create_client
from src.rag.ingest import deterministic_embedding

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')

client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
emb = deterministic_embedding('patient triage automation in hospitals')
print('embedding len:', len(emb))
print('first 6:', emb[:6])
res = client.rpc('match_startup_knowledge', {'query_embedding': emb, 'query_domain': 'healthcare_ai', 'match_count': 5}).execute()
print('res repr:', repr(res))
print('res attrs:', dir(res))
print('res.error:', getattr(res, 'error', None))
print('res.data type:', type(getattr(res, 'data', None)))
print('res.data len:', len(getattr(res, 'data', []) or []))
print('res.data sample:', getattr(res, 'data', None))
