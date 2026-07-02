from src.rag.retriever import query_supabase, local_fallback
from src.rag.ingest import deterministic_embedding

print('RPC agritech check:')
print(len(query_supabase('satellite-based crop yield prediction', domain='agritech', top_k=3, mode='rpc')))
print('Local agritech check:')
emb = deterministic_embedding('satellite-based crop yield prediction')
print(len(local_fallback(emb, 'agritech', top_k=3)))
print('RPC cybersecurity check:')
print(len(query_supabase('endpoint detection for small businesses', domain='cybersecurity', top_k=3, mode='rpc')))
print('Local cybersecurity check:')
print(len(local_fallback(emb, 'cybersecurity', top_k=3)))
