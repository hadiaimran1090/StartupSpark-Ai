import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.rag import ingest

# Use a faster dummy embedding for testing
ingest.deterministic_embedding = lambda text, dim=128: [0.0]*128


if __name__ == '__main__':
    files = ingest.ingest_domain('healthcare_ai')
    print('Wrote files:')
    for f in files:
        print(f)
