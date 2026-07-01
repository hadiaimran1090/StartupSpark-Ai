import argparse
import json
import os
import uuid
from pathlib import Path
import hashlib

from dotenv import load_dotenv

load_dotenv()


def find_pdfs(root: str = "data/knowledge_base") -> list[Path]:
    root_p = Path(root)
    pdfs = list(root_p.rglob("*.pdf"))
    return pdfs


def extract_text_from_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except Exception as e:
        raise RuntimeError("pypdf is required to extract PDF text") from e

    reader = PdfReader(str(path))
    texts = []
    for page in reader.pages:
        try:
            texts.append(page.extract_text() or "")
        except Exception:
            texts.append("")
    return "\n\n".join(texts)


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    if not text:
        return []
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end]
        chunks.append(chunk.strip())
        if end >= text_len:
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


def deterministic_embedding(text: str, dim: int = 768) -> list[float]:
    # Deterministic pseudo-embedding using SHA256 stream
    h = hashlib.sha256()
    h.update(text.encode('utf-8'))
    digest = h.digest()
    out = []
    i = 0
    # expand digest to required dim by hashing digest + counter
    while len(out) < dim:
        h2 = hashlib.sha256()
        h2.update(digest)
        h2.update(i.to_bytes(4, 'little'))
        block = h2.digest()
        for b in block:
            out.append((b / 255.0))
            if len(out) >= dim:
                break
        i += 1
    return [float(x) for x in out[:dim]]


def save_chunks(chunks: list[str], domain: str, source: str, out_dir: str = "data/chunks") -> Path:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    base_name = f"{domain}__{Path(source).stem}"
    out_file = Path(out_dir) / f"{base_name}.jsonl"
    with out_file.open("w", encoding="utf-8") as fh:
        for i, chunk in enumerate(chunks):
            record = {
                "id": str(uuid.uuid4()),
                "domain": domain,
                "source": source,
                "title": Path(source).stem,
                "chunk_index": i,
                "text": chunk,
                "embedding": deterministic_embedding(chunk),
            }
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return out_file


def ingest_domain(domain: str, root: str = "data/knowledge_base") -> list[Path]:
    root_p = Path(root) / domain
    if not root_p.exists():
        raise FileNotFoundError(f"Domain folder not found: {root_p}")
    pdfs = list(root_p.glob("*.pdf"))
    written = []
    for pdf in pdfs:
        print(f"Processing {pdf}")
        text = extract_text_from_pdf(pdf)
        chunks = chunk_text(text)
        out = save_chunks(chunks, domain, pdf.name)
        written.append(out)
        print(f"Wrote {out} ({len(chunks)} chunks)")
    return written


def ingest_all(root: str = "data/knowledge_base") -> dict:
    pdfs = find_pdfs(root)
    results = {}
    for pdf in pdfs:
        domain = pdf.parent.name
        print(f"Processing {pdf} in domain {domain}")
        text = extract_text_from_pdf(pdf)
        chunks = chunk_text(text)
        out = save_chunks(chunks, domain, pdf.name)
        results[str(out)] = len(chunks)
    return results


def main():
    parser = argparse.ArgumentParser(description="Ingest PDFs into chunked JSONL with embeddings")
    parser.add_argument("--domain", help="Domain folder to ingest (e.g. healthcare_ai)")
    parser.add_argument("--all", action="store_true", help="Ingest all domains")
    args = parser.parse_args()

    if args.all:
        res = ingest_all()
        print("Ingested:", res)
        return

    if not args.domain:
        parser.error("--domain is required unless --all is set")

    written = ingest_domain(args.domain)
    print("Finished. Files:")
    for p in written:
        print(p)


if __name__ == "__main__":
    main()
