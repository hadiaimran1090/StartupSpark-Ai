from pathlib import Path
import json
from typing import List
from dotenv import load_dotenv
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


def read_jsonl(path: Path) -> List[dict]:
    items = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            items.append(json.loads(line))
    return items


def prepare_rows(records: List[dict]) -> List[dict]:
    rows = []
    for r in records:
        row = {
            "id": r.get("id"),
            "domain": r.get("domain"),
            "source": r.get("source"),
            "title": r.get("title"),
            "content": r.get("text"),
            "metadata": {},
            "embedding": r.get("embedding"),
        }
        rows.append(row)
    return rows


def collect_jsonl_files(chunks_dir: str = "data/chunks") -> List[Path]:
    p = Path(chunks_dir)
    return sorted(p.glob("*.jsonl"))


def batch(iterable, n=100):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= n:
            yield batch
            batch = []
    if batch:
        yield batch


def upload_to_supabase(dry_run: bool = True, chunks_dir: str = "data/chunks") -> dict:
    files = collect_jsonl_files(chunks_dir)
    total = 0
    details = {}

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set in .env")

    try:
        from supabase import create_client
    except Exception as e:
        raise RuntimeError("supabase package is required") from e

    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    for f in files:
        records = read_jsonl(f)
        rows = prepare_rows(records)
        details[str(f)] = len(rows)
        total += len(rows)
        if dry_run:
            print(f"Dry-run: would upload {len(rows)} rows from {f}")
            continue

        for b in batch(rows, 100):
            # avoid duplicate primary key errors by checking existing ids
            ids = [r["id"] for r in b]
            existing = client.table("startup_knowledge").select("id").in_("id", ids).execute()
            existing_ids = []
            if getattr(existing, "data", None):
                existing_ids = [row.get("id") for row in existing.data]

            to_insert = [r for r in b if r.get("id") not in existing_ids]
            if not to_insert:
                print(f"Skipping batch: all {len(b)} rows already present")
                continue

            res = client.table("startup_knowledge").insert(to_insert).execute()
            if getattr(res, "error", None):
                raise RuntimeError(f"Supabase insert error: {res.error}")

    return {"files": details, "total": total}
