from pathlib import Path


def load_documents(data_dir: str = "data/raw_pdfs") -> list[Path]:
    path = Path(data_dir)
    if not path.exists():
        return []
    return sorted(path.glob("*.pdf"))
