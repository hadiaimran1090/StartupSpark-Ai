import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.rag import ingest


if __name__ == '__main__':
    # Ingest healthcare_ai (uses default deterministic_embedding dim=768)
    files = ingest.ingest_domain('healthcare_ai')
    print('Wrote files:')
    for f in files:
        print(f)
