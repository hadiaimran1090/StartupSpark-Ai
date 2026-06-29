from pathlib import Path


def save_report(report_text: str, output_dir: str = "reports") -> Path:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    file_path = path / "startup_report.txt"
    file_path.write_text(report_text, encoding="utf-8")
    return file_path
