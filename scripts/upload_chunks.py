import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.rag.supabase_upload import upload_to_supabase


def main():
    parser = argparse.ArgumentParser(description="Upload chunk JSONL files to Supabase (dry-run default)")
    parser.add_argument("--commit", action="store_true", help="Actually perform uploads instead of dry-run")
    parser.add_argument("--chunks", default="data/chunks", help="Chunks folder path")
    args = parser.parse_args()

    res = upload_to_supabase(dry_run=not args.commit, chunks_dir=args.chunks)
    print("Result:", res)


if __name__ == '__main__':
    main()
