from pathlib import Path
from time import perf_counter
from src.rag.ingest import extract_text_from_pdf, chunk_text, deterministic_embedding

p = Path('data/knowledge_base/healthcare_ai/Mapping-and-redesigning-workflow.pdf')
print('PDF:', p)
text = extract_text_from_pdf(p)
chunks = chunk_text(text)
print('chunks', len(chunks))
if chunks:
    t0 = perf_counter()
    v = deterministic_embedding(chunks[0])
    t1 = perf_counter()
    print('embed_dim', len(v), 'time_s', t1-t0)
else:
    print('no chunks')
