import html as html_lib
import json
import os
import re
import textwrap
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from src.config import PROJECT_TITLE, SUPPORTED_DOMAINS
from src.rag.retriever import query_supabase
from src.workflow.orchestrator import orchestrate_startup


load_dotenv()

DISPLAY_TO_FOLDER = {
    "Healthcare AI": "healthcare_ai",
    "FinTech": "fintech",
    "Education AI": "edtech",
    "Agriculture Tech": "agritech",
    "Cybersecurity": "cybersecurity",
}

REPORTS_DIR = Path("reports")
REPORT_HISTORY_FILE = REPORTS_DIR / "report_history.json"


def create_supabase_auth_client():
    from supabase import create_client

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_anon = os.getenv("SUPABASE_ANON_KEY")
    if not supabase_url or not supabase_anon:
        return None
    return create_client(supabase_url, supabase_anon)


def user_to_dict(user_obj):
    if not user_obj:
        return {}
    if isinstance(user_obj, dict):
        return user_obj
    return {
        "id": getattr(user_obj, "id", None),
        "email": getattr(user_obj, "email", None),
        "user_metadata": getattr(user_obj, "user_metadata", {}) or {},
        "created_at": getattr(user_obj, "created_at", None),
    }


def load_report_history():
    if "report_history" in st.session_state:
        return st.session_state["report_history"]
    try:
        history = json.loads(REPORT_HISTORY_FILE.read_text(encoding="utf-8")) if REPORT_HISTORY_FILE.exists() else []
    except Exception:
        history = []
    st.session_state["report_history"] = history
    return history


def save_report_history(history):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_HISTORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")
    st.session_state["report_history"] = history


def report_title(report):
    idea = report.get("idea") or {}
    title = idea.get("startup_name") or "Startup Report"
    domain = (report.get("metadata") or {}).get("input", {}).get("domain")
    return f"{title} - {domain}" if domain else title


def remember_report(report):
    history = load_report_history()
    entry = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
        "created_at": datetime.now().strftime("%b %d, %Y %I:%M %p"),
        "title": report_title(report),
        "report": report,
    }
    history = [entry] + history
    save_report_history(history[:12])


def unique_nonempty(values):
    seen = set()
    unique = []
    for value in values or []:
        if not value:
            continue
        text = str(value).strip()
        if not text:
            continue
        key = re.sub(r"\s+", " ", text).casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(text)
    return unique


def safe_filename(value):
    return re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower() or "startup-report"


def esc(value, default="N/A"):
    if value is None or value == "":
        return default
    return html_lib.escape(str(value))


def render_html(markup):
    html = "\n".join(line.strip() for line in textwrap.dedent(markup).strip().splitlines())
    st.markdown(html, unsafe_allow_html=True)


def disable_auth_autofill():
    components.html(
        """
        <script>
        const apply = () => {
            const doc = window.parent.document;
            doc.querySelectorAll('input').forEach((input) => {
                const label = (input.getAttribute('aria-label') || input.placeholder || '').toLowerCase();
                if (label.includes('email') || label.includes('password')) {
                    input.setAttribute('autocomplete', label.includes('password') ? 'new-password' : 'off');
                    input.setAttribute('autocorrect', 'off');
                    input.setAttribute('autocapitalize', 'none');
                    input.setAttribute('spellcheck', 'false');
                }
            });
        };
        apply();
        setTimeout(apply, 250);
        setTimeout(apply, 1000);
        </script>
        """,
        height=0,
    )


def score_value(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def score_pct(value):
    v = score_value(value)
    if v is None:
        return 0
    return max(0, min(100, v * 10))


def normalized_validation(report):
    validation = report.get("validation") or {}
    scores = validation.get("scores") or {}
    return {
        **validation,
        "innovation": validation.get("innovation", scores.get("innovation")),
        "market_demand": validation.get("market_demand", scores.get("market_demand")),
        "feasibility": validation.get("feasibility", scores.get("feasibility")),
        "scalability": validation.get("scalability", scores.get("scalability")),
        "overall": validation.get("overall", "N/A"),
    }


def normalized_swot(report):
    return report.get("swot_analysis") or report.get("swot") or {}


def escape_pdf_text(text):
    replacements = {
        "•": "-",
        "–": "-",
        "—": "-",
        "→": "->",
        "↗": "->",
        "✓": "OK",
        "✦": "*",
        "“": '"',
        "”": '"',
        "’": "'",
        "‘": "'",
        "…": "...",
    }
    cleaned = str(text)
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    cleaned = cleaned.encode("latin-1", "ignore").decode("latin-1")
    return cleaned.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


# ---------------------------------------------------------------------------
# Colored / styled PDF export — mirrors the dark "StartupSpark" brand palette
# used on the report page (no external PDF libraries required).
# ---------------------------------------------------------------------------

PDF_COLORS = {
    "bg": (0.043, 0.075, 0.149),        # #0b1326
    "primary": (0.678, 0.776, 1.0),     # #adc6ff
    "accent": (1.0, 0.718, 0.525),      # #ffb786
    "secondary": (0.816, 0.737, 1.0),   # #d0bcff
    "muted": (0.71, 0.729, 0.808),      # #aeb7cd
    "text": (0.855, 0.886, 0.992),      # #dae2fd
    "error": (1.0, 0.706, 0.671),       # soft red tint
}

PDF_STYLES = {
    "title":  {"font": "F2", "size": 21, "color": PDF_COLORS["primary"], "leading": 27, "wrap": 44, "indent": 0},
    "meta":   {"font": "F1", "size": 9.5, "color": PDF_COLORS["muted"], "leading": 13, "wrap": 100, "indent": 0},
    "h2":     {"font": "F2", "size": 13, "color": PDF_COLORS["accent"], "leading": 23, "wrap": 74, "indent": 0},
    "kv":     {"font": "F1", "size": 10.5, "color": PDF_COLORS["text"], "leading": 15, "wrap": 90, "indent": 0},
    "body":   {"font": "F1", "size": 10.5, "color": PDF_COLORS["text"], "leading": 15.5, "wrap": 88, "indent": 0},
    "item":   {"font": "F1", "size": 10.5, "color": PDF_COLORS["text"], "leading": 15, "wrap": 84, "indent": 16},
    "spacer": {"leading": 9},
}


def report_to_blocks(report):
    """Flatten a report dict into (kind, text) blocks used to build the PDF."""
    idea = report.get("idea") or {}
    validation = normalized_validation(report)
    market = report.get("market_research") or {}
    business = report.get("business_model") or {}
    inputs = (report.get("metadata") or {}).get("input") or {}
    competitors = (report.get("competitor_analysis") or {}).get("competitors", [])
    swot = normalized_swot(report)
    roadmap = report.get("implementation_roadmap") or {}
    budget = report.get("estimated_budget") or {}
    future_enh = report.get("future_enhancements", [])
    sources = unique_nonempty(report.get("retrieved_sources", []))
    mvp_features = report.get("mvp_features", [])

    blocks = [
        ("title", "StartupSpark AI — Analysis Report"),
        ("meta", report_title(report)),
        ("meta", f"Generated: {datetime.now().strftime('%B %d, %Y')}"),
        ("spacer", ""),
        ("h2", "1. Startup Overview"),
        ("kv", f"Name: {idea.get('startup_name') or 'N/A'}"),
        ("kv", f"Tagline: {idea.get('tagline') or 'N/A'}"),
        ("kv", f"Domain: {inputs.get('domain') or 'N/A'}"),
        ("kv", f"Audience: {inputs.get('target_audience') or 'N/A'}"),
        ("kv", f"Region: {inputs.get('country_region') or 'N/A'}"),
        ("kv", f"Budget: {inputs.get('budget') or 'N/A'}"),
        ("kv", f"Stage: {inputs.get('business_stage') or 'N/A'}"),
        ("spacer", ""),
        ("h2", "2. Problem Statement"),
        ("body", inputs.get("problem_statement") or "N/A"),
        ("spacer", ""),
        ("h2", "3. Proposed Solution"),
        ("body", idea.get("ai_solution") or idea.get("core_idea") or "N/A"),
        ("spacer", ""),
        ("h2", "4. Market Research"),
        ("body", market.get("summary") or "No market summary available."),
        ("spacer", ""),
        ("h2", "5. Competitor Analysis"),
    ]
    if competitors:
        for c in competitors:
            blocks.append(("item", f"{c.get('name', 'N/A')} — Strength: {c.get('strengths', 'N/A')} | Weakness: {c.get('weaknesses', 'N/A')}"))
    else:
        blocks.append(("body", "No competitors found in current knowledge base sample."))

    blocks.extend([
        ("spacer", ""),
        ("h2", "6. Business Model"),
        ("kv", f"Revenue model: {business.get('revenue_model') or 'TBD'}"),
        ("kv", f"Pricing:       {business.get('pricing') or 'TBD'}"),
        ("kv", f"Segments:      {business.get('segments') or 'N/A'}"),
        ("spacer", ""),
        ("h2", "7. MVP Features"),
    ])
    if mvp_features:
        for feature in mvp_features:
            blocks.append(("item", feature))
    else:
        blocks.append(("body", "N/A"))

    blocks.extend([("spacer", ""), ("h2", "8. SWOT Analysis")])
    for label, key in [("Strengths", "strengths"), ("Weaknesses", "weaknesses"), ("Opportunities", "opportunities"), ("Threats", "threats")]:
        values = swot.get(key)
        if isinstance(values, str):
            values = [values]
        blocks.append(("kv", f"{label}:"))
        if values:
            for value in values:
                blocks.append(("item", value))
        else:
            blocks.append(("item", "N/A"))

    blocks.extend([
        ("spacer", ""),
        ("h2", "9. Validation Score"),
        ("kv", f"Innovation: {validation.get('innovation', 'N/A')}"),
        ("kv", f"Market Demand: {validation.get('market_demand', 'N/A')}"),
        ("kv", f"Feasibility: {validation.get('feasibility', 'N/A')}"),
        ("kv", f"Overall Spark Score: {validation.get('overall', 'N/A')}/10"),
        ("spacer", ""),
        ("h2", "10. Implementation Roadmap"),
    ])
    if roadmap:
        for key, value in roadmap.items():
            blocks.append(("item", f"{key.replace('_', ' ').title()}: {value}"))
    else:
        blocks.append(("body", "N/A"))

    blocks.extend([("spacer", ""), ("h2", "11. Estimated Budget")])
    if budget:
        for key, value in budget.items():
            blocks.append(("item", f"{key.title()}: {value}"))
    else:
        blocks.append(("body", "N/A"))

    blocks.extend([("spacer", ""), ("h2", "12. Future Enhancements")])
    if future_enh:
        for item in future_enh:
            blocks.append(("item", item))
    else:
        blocks.append(("body", "N/A"))

    blocks.extend([("spacer", ""), ("h2", "13. Retrieved Sources")])
    if sources:
        for source in sources[:10]:
            blocks.append(("item", source))
    else:
        blocks.append(("body", "No sources retrieved."))

    return blocks


def _wrap_pdf_text(text, width):
    text = str(text)
    if not text:
        return [""]
    return textwrap.wrap(text, width=width) or [""]


def _paginate_pdf_blocks(blocks):
    page_w, page_h = 612, 792
    margin_x = 50
    top_y = 738
    bottom_y = 60

    pages = []
    current_page = []
    y = top_y

    def start_new_page():
        nonlocal current_page, y
        pages.append(current_page)
        current_page = []
        y = top_y

    for kind, text in blocks:
        style = PDF_STYLES[kind]
        leading = style["leading"]
        if kind == "spacer":
            y -= leading
            if y < bottom_y:
                start_new_page()
            continue

        bullet = "- " if kind == "item" else ""
        lines = _wrap_pdf_text(text, style["wrap"])
        for i, line in enumerate(lines):
            if y < bottom_y:
                start_new_page()
            display_text = (bullet + line) if i == 0 else (("  " if kind == "item" else "") + line)
            current_page.append(
                {
                    "x": margin_x + style["indent"],
                    "y": y,
                    "font": style["font"],
                    "size": style["size"],
                    "color": style["color"],
                    "text": display_text,
                }
            )
            y -= leading

    if current_page or not pages:
        pages.append(current_page)
    return pages, page_w, page_h


def make_pdf_bytes(report):
    blocks = report_to_blocks(report)
    pages, page_w, page_h = _paginate_pdf_blocks(blocks)
    num_pages = len(pages)

    page_obj_ids, content_obj_ids = [], []
    next_id = 3
    for _ in range(num_pages):
        page_obj_ids.append(next_id)
        next_id += 1
        content_obj_ids.append(next_id)
        next_id += 1
    font1_id, font2_id = next_id, next_id + 1

    objects = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Kids [{' '.join(f'{pid} 0 R' for pid in page_obj_ids)}] /Count {num_pages} >>",
    }

    bg = PDF_COLORS["bg"]
    for i in range(num_pages):
        page_id, content_id = page_obj_ids[i], content_obj_ids[i]
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_w} {page_h}] "
            f"/Resources << /Font << /F1 {font1_id} 0 R /F2 {font2_id} 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        )

        stream_parts = [
            f"{bg[0]:.3f} {bg[1]:.3f} {bg[2]:.3f} rg",
            f"0 0 {page_w} {page_h} re f",
        ]
        for item in pages[i]:
            r, g, b = item["color"]
            stream_parts.extend(
                [
                    "BT",
                    f"/{item['font']} {item['size']:.1f} Tf",
                    f"{r:.3f} {g:.3f} {b:.3f} rg",
                    f"1 0 0 1 {item['x']:.1f} {item['y']:.1f} Tm",
                    f"({escape_pdf_text(item['text'])}) Tj",
                    "ET",
                ]
            )
        muted = PDF_COLORS["muted"]
        stream_parts.extend(
            [
                "BT",
                "/F1 8 Tf",
                f"{muted[0]:.3f} {muted[1]:.3f} {muted[2]:.3f} rg",
                f"1 0 0 1 {page_w - 110} 28 Tm",
                f"(Page {i + 1} of {num_pages}) Tj",
                "ET",
            ]
        )
        stream = "\n".join(stream_parts)
        objects[content_id] = f"<< /Length {len(stream.encode('latin-1', 'replace'))} >>\nstream\n{stream}\nendstream"

    objects[font1_id] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    objects[font2_id] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>"

    max_obj = font2_id
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0] * (max_obj + 1)
    for number in range(1, max_obj + 1):
        obj_str = objects.get(number)
        if obj_str is None:
            continue
        offsets[number] = len(pdf)
        pdf.extend(f"{number} 0 obj\n{obj_str}\nendobj\n".encode("latin-1", "replace"))

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {max_obj + 1}\n0000000000 65535 f \n".encode("latin-1"))
    for number in range(1, max_obj + 1):
        pdf.extend(f"{offsets[number]:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(f"trailer\n<< /Size {max_obj + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode("latin-1"))
    return bytes(pdf)


def inject_styles():
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Sora:wght@500;600;700;800&display=swap');

            :root {
                --bg: #071022;
                --surface: #0b1326;
                --panel: rgba(23, 31, 51, 0.74);
                --panel-strong: #171f33;
                --line: rgba(173, 198, 255, 0.16);
                --muted: #aeb7cd;
                --text: #dae2fd;
                --primary: #adc6ff;
                --secondary: #d0bcff;
                --accent: #ffb786;
            }

            .stApp {
                background:
                    radial-gradient(circle at 8% 0%, rgba(77, 142, 255, 0.16), transparent 31rem),
                    radial-gradient(circle at 88% 14%, rgba(208, 188, 255, 0.12), transparent 34rem),
                    linear-gradient(180deg, #071022 0%, #0b1326 44%, #071022 100%);
                color: var(--text);
                font-family: Inter, sans-serif;
            }

            #MainMenu, footer, header { visibility: hidden; }
            .block-container {
                max-width: none;
                padding: 0 3rem 3rem;
            }

            h1, h2, h3, .brand, .hero-title {
                font-family: Sora, sans-serif;
                letter-spacing: 0;
            }

            .topbar {
                display: flex;
                align-items: center;
                min-height: 3.5rem;
            }

            .brand {
                display: flex;
                align-items: center;
                gap: .65rem;
                color: var(--primary);
                font-weight: 800;
                font-size: 1.05rem;
            }

            .bolt {
                display: inline-grid;
                place-items: center;
                width: 1.6rem;
                height: 1.6rem;
                border-radius: .45rem;
                color: #06132b;
                background: linear-gradient(135deg, var(--primary), var(--secondary));
                font-weight: 900;
            }

            .navlinks {
                display: flex;
                justify-content: center;
                gap: 2rem;
                color: var(--muted);
                font-size: 1rem;
                font-weight: 700;
            }

            .account-icon button {
                width: 2.5rem;
                min-height: 2.5rem !important;
                padding: 0 !important;
                border-radius: 999px !important;
                color: var(--primary) !important;
                border: 1px solid rgba(173, 198, 255, .22) !important;
                background: rgba(173, 198, 255, 0.07) !important;
                font-size: 1.1rem !important;
            }

            .account-link {
                width: 2.5rem;
                height: 2.5rem;
                display: inline-grid;
                place-items: center;
                border-radius: 999px;
                color: var(--primary) !important;
                border: 1px solid rgba(173, 198, 255, .22);
                background: rgba(173, 198, 255, 0.07);
                text-decoration: none !important;
                font-size: 1.05rem;
                font-weight: 800;
            }

            .hero {
                text-align: center;
                min-height: 400px;
                display: grid;
                place-items: center;
                padding: 3rem 0 2rem;
            }

            .eyebrow {
                display: inline-flex;
                align-items: center;
                gap: .5rem;
                padding: .45rem .8rem;
                border: 1px solid var(--line);
                border-radius: 999px;
                color: var(--primary);
                background: rgba(23, 31, 51, 0.52);
                font-size: .72rem;
                font-weight: 800;
                text-transform: uppercase;
            }

            .hero-title {
                max-width: 900px;
                margin: 1.4rem auto .8rem;
                color: #eef3ff;
                font-size: clamp(3.25rem, 6.8vw, 6.15rem);
                line-height: 1.04;
                font-weight: 800;
            }

            .gradient-text {
                background: linear-gradient(135deg, var(--primary), var(--secondary));
                -webkit-background-clip: text;
                background-clip: text;
                color: transparent;
            }

            .hero-copy {
                max-width: 780px;
                margin: 0 auto 1.8rem;
                color: #c2c6d6;
                font-size: 1.16rem;
                line-height: 1.75;
            }

            .trait-row {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 1rem;
                max-width: 760px;
                margin: 2.2rem auto 0;
                color: rgba(218, 226, 253, 0.66);
                font-size: .78rem;
            }

            .section-title {
                margin-top: 3rem;
                margin-bottom: .35rem;
                font-size: 1.45rem;
                font-weight: 800;
            }

            .section-subtitle {
                color: var(--muted);
                margin-bottom: 1.5rem;
            }

            .glass-card, .metric-card, .auth-card {
                border: 1px solid var(--line);
                background: linear-gradient(180deg, rgba(23,31,51,.78), rgba(10,18,36,.72));
                box-shadow: 0 24px 80px rgba(0, 0, 0, .22);
                border-radius: 1.25rem;
            }

            .glass-card {
                min-height: 245px;
                padding: 1.65rem;
                margin-top: 20px;
            }

            .glass-card h3, .metric-card h3 {
                margin: 0 0 .8rem;
                font-size: 1.15rem;
                font-weight: 800;
            }

            .glass-card p, .metric-card p {
                color: #c2c6d6;
                line-height: 1.65;
                font-size: .92rem;
            }

            .icon-tile {
                display: grid;
                place-items: center;
                width: 2.55rem;
                height: 2.55rem;
                border-radius: .8rem;
                margin-bottom: 1.15rem;
                color: #06132b;
                font-weight: 900;
                background: linear-gradient(135deg, #4d8eff, #adc6ff);
            }

            .metric-card {
                min-height: 245px;
                padding: 1.65rem;
                color: #06132b;
                background: linear-gradient(135deg, #adc6ff, #d0bcff);
            }

            .metric-card p { color: rgba(0, 40, 93, .76); }
            .big-number {
                margin-top: 2rem;
                font-family: Sora, sans-serif;
                font-size: 3.5rem;
                font-weight: 800;
            }

            .wide-band {
                margin: 4rem -1.25rem 2rem;
                padding: 3rem 1.25rem;
                background: rgba(6, 14, 32, .62);
                border-top: 1px solid rgba(173, 198, 255, .06);
                border-bottom: 1px solid rgba(173, 198, 255, .06);
            }

            .mini-panel {
                padding: .9rem 1rem;
                margin: .8rem 0;
                border-radius: .75rem;
                border: 1px solid rgba(173, 198, 255, .11);
                background: rgba(45, 52, 73, .42);
            }

            .cta-box {
                max-width: 790px;
                margin: 4rem auto 3rem;
                padding: 3rem 1.5rem;
                text-align: center;
                border: 1px solid rgba(173, 198, 255, .28);
                border-radius: 1.5rem;
                background: rgba(23, 31, 51, .46);
            }

            .footerline {
                margin-top: 2rem;
                padding-top: 2rem;
                border-top: 1px solid rgba(173, 198, 255, .08);
                display: flex;
                justify-content: space-between;
                gap: 1rem;
                color: var(--muted);
                font-size: .78rem;
            }

            .auth-brand-large {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 1rem;
                margin: .8rem auto 2rem;
                color: var(--primary);
                font-family: Sora, sans-serif;
                font-size: clamp(1.5rem, 6vw, 3rem);
                font-weight: 800;
            }

            .auth-shell {
                max-width: 680px;
                margin: 0 auto 3rem;
                padding: clamp(1.4rem, 4vw, 2.4rem);
                border: 1px solid rgba(173, 198, 255, .18);
                border-radius: 2rem;
                background: linear-gradient(180deg, rgba(23,31,51,.86), rgba(14,24,45,.9));
                box-shadow: 0 28px 90px rgba(0, 0, 0, .32);
            }

            div[data-testid="column"]:has(.auth-brand-large) {
                padding: clamp(1.2rem, 3vw, 2rem);
                border: 1px solid rgba(173, 198, 255, .18);
                border-radius: 2rem;
                background: linear-gradient(180deg, rgba(23,31,51,.82), rgba(14,24,45,.9));
                box-shadow: 0 28px 90px rgba(0, 0, 0, .32);
            }

            .auth-back-button .stButton button {
                color: #4d8eff !important;
                border: none !important;
            }

            div[data-testid="stForm"]:has(button[kind="primary"]) {
                max-width: 480px;
                margin-left: auto;
                margin-right: auto;
            }

            .auth-title {
                text-align: center;
                margin: 2rem 0 .7rem;
                font-size: clamp(1.5rem, 6vw, 3rem);
                line-height: 1.05;
                font-weight: 800;
                color: #e6ecff;
            }

            .auth-subtitle {
                text-align: center;
                color: var(--muted);
                font-size: 1.05rem;
                line-height: 1.65;
                margin-bottom: 2.1rem;
            }

            .stButton > button, .stDownloadButton > button, div[data-testid="stFormSubmitButton"] button {
                border: 1px solid rgba(173, 198, 255, .16);
                background: rgba(23, 31, 51, .72);
                color: #dae2fd;
                border-radius: .8rem;
                min-height: 3rem;
                font-weight: 800;
                box-shadow: none;
            }

            .stButton > button[kind="primary"], div[data-testid="stFormSubmitButton"] button[kind="primary"] {
                color: #00285d;
                border: 0;
                background: linear-gradient(135deg, #adc6ff, #d0bcff);
                box-shadow: 0 18px 44px rgba(173, 198, 255, .18);
            }

            div[data-testid="stForm"] {
                border: 1px solid rgba(173, 198, 255, .08);
                border-radius: 1rem;
                padding: 1rem 1rem 1.15rem;
                background: rgba(7, 16, 34, .28);
            }

            .stTextInput label, .stTextArea label, .stSelectbox label, .stRadio label {
                color: #d6def5 !important;
                font-weight: 800 !important;
                letter-spacing: .04em;
            }

            .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {
                color: #dae2fd;
                border: 1px solid rgba(173, 198, 255, .14);
                border-radius: .75rem;
                background: #2d3449;
            }

            .stTextInput input::placeholder, .stTextArea textarea::placeholder {
                color: rgba(218, 226, 253, .52);
            }

            .stTextInput input:focus, .stTextArea textarea:focus {
                border-color: #adc6ff !important;
                box-shadow: 0 0 0 2px rgba(173, 198, 255, .20) !important;
            }

            .stRadio > div {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(70px, 1fr));
                gap: .5rem;
                padding: .45rem;
                border: 1px solid rgba(173, 198, 255, .14);
                border-radius: 1rem;
                background: rgba(19, 27, 46, .9);
                max-width: 520px;
                margin: 0 auto;
            }

            div[data-testid="stRadio"] {
                display: flex;
                justify-content: center;
                width: 100%;
            }

            .stRadio [role="radio"] {
                justify-content: center;
                min-height: 3.25rem;
                border-radius: .8rem;
                color: #d8e2ff !important;
                font-family: Sora, sans-serif;
                font-size: 1.05rem;
                font-weight: 800;
                white-space: nowrap;
            }

            .stRadio [role="radio"] p,
            .stRadio [data-testid="stMarkdownContainer"] p {
                color: #d8e2ff !important;
                font-weight: 800 !important;
                font-size: 1.02rem !important;
            }

            .stRadio [aria-checked="true"] {
                background: rgba(45, 52, 73, .85);
                box-shadow: 0 14px 36px rgba(173, 198, 255, .16);
            }

            .stTabs [data-baseweb="tab-list"] {
                gap: .35rem;
                background: rgba(19, 27, 46, .75);
                border: 1px solid var(--line);
                border-radius: .9rem;
                padding: .35rem;
            }

            .stTabs [data-baseweb="tab"] {
                border-radius: .65rem;
                color: var(--muted);
                font-weight: 800;
            }

            .stTabs [aria-selected="true"] {
                background: rgba(45, 52, 73, .8);
                color: var(--primary);
            }

            .app-topbar {
                display: grid;
                grid-template-columns: 430px minmax(0, 1fr) 72px;
                align-items: center;
                min-height: 4.8rem;
                width: 100%;
                padding: 0 3rem;
                border-bottom: 1px solid rgba(173, 198, 255, .08);            }

            .app-brand {
                display: flex;
                align-items: center;
                gap: .8rem;
                color: #c8d7ff;
                font-family: Sora, sans-serif;
                font-size: 1.4rem;
                font-weight: 800;
            }

            .app-brand .mark {
                color: #adc6ff;
                font-size: 1.5rem;
            }

            .app-nav {
                display: flex;
                justify-content: center;
                gap: 3rem;
                font-family: Sora, sans-serif;
                font-size: 1.2rem;
                font-weight: 800;
            }

            .app-nav a {
                color: #d6def5;
                text-decoration: none;
            }

            .app-nav a:hover {
                color: #adc6ff;
            }

            .app-user-icon {
                justify-self: end;
                width: 2.25rem;
                height: 2.25rem;
                display: grid;
                place-items: center;
                border-radius: 999px;
                border: 1px solid rgba(214, 222, 245, .35);
                color: #d6def5;
                font-weight: 900;
            }

            /* ---- Side rail: fixed so the nav buttons sit right under the
                   profile row instead of being pushed to the bottom ---- */
            div[data-testid="column"]:has(.side-rail) {
                background: rgba(23, 31, 51, .72);
                border-right: 1px solid rgba(173, 198, 255, .11);
            }

            .side-rail {
                min-height: auto;
                padding: 1.7rem 1.25rem 0;
                background: rgba(23, 31, 51, .72);
            }

            .profile-row {
                display: flex;
                gap: .9rem;
                align-items: center;
                padding: .15rem .35rem 1.4rem;
                color: rgba(218, 226, 253, .58);
                font-size: .86rem;
            }

            .avatar-dot {
                width: 3rem;
                height: 3rem;
                display: grid;
                place-items: center;
                border-radius: 999px;
                background: rgba(173, 198, 255, .12);
                color: #adc6ff;
                font-weight: 900;
            }

            .forge-main {
                width: 100%;
                padding: 0 clamp(1.5rem, 4vw, 4.5rem) 4rem;
            }

            .forge-hero {
                margin: 2.2rem 0 2rem;
            }

            .forge-hero h1 {
                margin: .8rem 0 .65rem;
                color: #dce6ff;
                font-size: clamp(1.5rem, 3vw, 3rem);
                line-height: 1.05;
                font-weight: 800;
            }

            .forge-hero p {
                max-width: 760px;
                color: #c7cedf;
                font-size: 1.05rem;
                line-height: 1.55;
            }

            div[data-testid="stForm"]:has([data-testid="stFormSubmitButton"]) {
                padding: clamp(1.7rem, 4vw, 3.1rem);
                border: 1px solid rgba(173, 198, 255, .16);
                border-radius: 1.5rem;
                background: linear-gradient(180deg, rgba(23,31,51,.9), rgba(17,27,50,.9));
                box-shadow: 0 30px 90px rgba(0, 0, 0, .34);
            }

            .trust-row {
                margin-top: 1.6rem;
                padding-top: 1.5rem;
                border-top: 1px solid rgba(173, 198, 255, .09);
            }

            .trust-copy {
                color: #d9def0;
                font-size: .82rem;
            }

            .report-card {
                padding: 1.2rem;
                margin: .9rem 0;
                border: 1px solid rgba(173, 198, 255, .13);
                border-radius: .9rem;
                background: rgba(7, 16, 34, .38);
            }

            .report-card h3 {
                margin: 0 0 .5rem;
                color: #dce6ff;
                font-size: 1.05rem;
            }

            .report-card p, .report-card li {
                color: #c2c6d6;
                line-height: 1.55;
            }

            /* =========================================================
               Analysis Report page (bento-grid style)
               ========================================================= */
            .rpt-topline {
                display: flex;
                flex-wrap: wrap;
                align-items: center;
                gap: .5rem;
                color: var(--muted);
                font-size: .78rem;
                margin-bottom: .4rem;
            }
            .rpt-topline .current { color: var(--primary); font-weight: 700; }

            .rpt-hero h1 {
                margin: .3rem 0 .5rem;
                font-size: clamp(1.9rem, 3.4vw, 2.6rem);
                font-weight: 800;
                color: #eef3ff;
            }
            .rpt-hero h1 span { color: var(--primary); }
            .rpt-hero p {
                color: var(--muted);
                font-size: 1.02rem;
                max-width: 760px;
            }

            .bento-grid {
                display: grid;
                grid-template-columns: repeat(12, minmax(0, 1fr));
                gap: 1.4rem;
                margin-top: 1.5rem;
            }
            .span-12 { grid-column: span 12; }
            .span-8 { grid-column: span 8; }
            .span-7 { grid-column: span 7; }
            .span-6 { grid-column: span 6; }
            .span-5 { grid-column: span 5; }
            .span-4 { grid-column: span 4; }

            .glass-panel {
                background: rgba(23, 31, 51, .68);
                border: 1px solid rgba(173, 198, 255, .12);
                border-radius: 1.5rem;
                padding: 1.75rem;
                box-shadow: 0 20px 60px rgba(0, 0, 0, .30);
            }

            .panel-head {
                display: flex;
                align-items: center;
                gap: .6rem;
                margin-bottom: 1.2rem;
                font-weight: 800;
                font-size: 1.1rem;
                color: #eef3ff;
            }
            .panel-head .ic {
                font-size: 1.15rem;
                color: var(--primary);
            }

            .field-label {
                font-size: .66rem;
                letter-spacing: .08em;
                text-transform: uppercase;
                color: var(--muted);
                margin-bottom: .3rem;
            }
            .field-value {
                color: #eef3ff;
                font-size: .96rem;
                line-height: 1.55;
                margin-bottom: 1.1rem;
            }

            .chip-row { display: flex; gap: .5rem; flex-wrap: wrap; margin-top: .5rem; }
            .chip {
                padding: .3rem .75rem;
                border-radius: 999px;
                font-size: .7rem;
                font-weight: 700;
                border: 1px solid rgba(173, 198, 255, .28);
                background: rgba(173, 198, 255, .08);
                color: var(--primary);
            }

            .validation-row {
                display: flex;
                justify-content: space-between;
                font-size: .84rem;
                color: var(--muted);
                margin-bottom: .35rem;
            }
            .validation-row strong { color: #eef3ff; font-size: 1.05rem; }
            .bar-track {
                height: 6px;
                border-radius: 999px;
                background: rgba(255, 255, 255, .08);
                overflow: hidden;
                margin-bottom: 1.1rem;
            }
            .bar-fill { height: 100%; border-radius: 999px; background: var(--primary); }

            .spark-score {
                text-align: center;
                margin-top: .5rem;
                padding-top: 1.2rem;
                border-top: 1px solid rgba(173, 198, 255, .14);
            }
            .spark-score .label {
                font-size: .66rem;
                text-transform: uppercase;
                letter-spacing: .1em;
                color: var(--muted);
            }
            .spark-score .value {
                font-size: 2.3rem;
                font-weight: 800;
                color: var(--primary);
                line-height: 1.3;
            }

            .tint-box {
                padding: 1.15rem;
                border-radius: 1rem;
                line-height: 1.65;
                font-size: .92rem;
            }
            .tint-error {
                background: rgba(255, 128, 128, .08);
                border: 1px solid rgba(255, 128, 128, .22);
                color: #ffd9d5;
            }
            .tint-primary {
                background: rgba(173, 198, 255, .08);
                border: 1px solid rgba(173, 198, 255, .22);
                color: #dbe6ff;
            }

            .stat-mini {
                text-align: center;
                padding: 1.2rem;
                border-radius: 1.1rem;
                background: rgba(45, 52, 73, .42);
                border: 1px solid rgba(173, 198, 255, .08);
            }
            .stat-mini .num { font-size: 1.7rem; font-weight: 800; }
            .stat-mini .cap { font-size: .7rem; color: var(--muted); margin-top: .3rem; }

            .comp-table { width: 100%; border-collapse: collapse; margin-top: .4rem; }
            .comp-table th {
                text-align: left;
                font-size: .66rem;
                color: var(--muted);
                text-transform: uppercase;
                letter-spacing: .06em;
                padding: .55rem 0;
                border-bottom: 1px solid rgba(173, 198, 255, .16);
            }
            .comp-table td {
                padding: .6rem 0;
                border-bottom: 1px solid rgba(173, 198, 255, .06);
                font-size: .88rem;
                color: #dce4fb;
            }

            .mvp-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
            .mvp-item {
                display: flex;
                gap: .7rem;
                align-items: flex-start;
                padding: 1rem;
                border-radius: 1rem;
                background: rgba(45, 52, 73, .4);
                border: 1px solid rgba(173, 198, 255, .06);
            }
            .mvp-item .ic { color: var(--accent); font-size: 1.15rem; }
            .mvp-item h5 { margin: 0 0 .2rem; color: #eef3ff; font-size: .92rem; }
            .mvp-item p { margin: 0; font-size: .78rem; color: var(--muted); }

            .swot-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1rem; }
            .swot-card { padding: 1.2rem; border-radius: 1.25rem; }
            .swot-card h5 {
                margin: 0 0 .6rem;
                font-weight: 800;
                display: flex;
                gap: .4rem;
                align-items: center;
                font-size: .95rem;
            }
            .swot-card ul { margin: 0; padding-left: 1.1rem; color: var(--muted); font-size: .8rem; line-height: 1.65; }
            .swot-strength { background: rgba(173, 198, 255, .06); border: 1px solid rgba(173, 198, 255, .2); }
            .swot-strength h5 { color: var(--primary); }
            .swot-weak { background: rgba(255, 183, 134, .06); border: 1px solid rgba(255, 183, 134, .2); }
            .swot-weak h5 { color: var(--accent); }
            .swot-opp { background: rgba(208, 188, 255, .06); border: 1px solid rgba(208, 188, 255, .2); }
            .swot-opp h5 { color: var(--secondary); }
            .swot-threat { background: rgba(255, 128, 128, .06); border: 1px solid rgba(255, 128, 128, .2); }
            .swot-threat h5 { color: #ff9d95; }

            .timeline { position: relative; padding-left: 2rem; }
            .timeline::before {
                content: '';
                position: absolute;
                left: .58rem;
                top: .4rem;
                bottom: .4rem;
                width: 2px;
                background: rgba(173, 198, 255, .2);
            }
            .tl-item { position: relative; margin-bottom: 1.7rem; }
            .tl-item:last-child { margin-bottom: 0; }
            .tl-dot {
                position: absolute;
                left: -2rem;
                top: .18rem;
                width: .85rem;
                height: .85rem;
                border-radius: 999px;
                background: var(--primary);
                box-shadow: 0 0 0 4px rgba(173, 198, 255, .18);
            }
            .tl-item.done .tl-dot { background: var(--muted); box-shadow: 0 0 0 4px rgba(174, 183, 205, .12); }
            .tl-item h5 { margin: 0 0 .3rem; color: #eef3ff; font-size: .96rem; }
            .tl-item p { margin: 0; color: var(--muted); font-size: .86rem; line-height: 1.5; }

            .budget-row { display: flex; justify-content: space-between; font-size: .84rem; margin-bottom: .3rem; color: var(--muted); }
            .budget-row strong { color: #eef3ff; }
            .budget-total {
                text-align: center;
                margin-top: 1.1rem;
                padding-top: 1.1rem;
                border-top: 1px solid rgba(173, 198, 255, .14);
            }
            .budget-total .label { font-size: .66rem; text-transform: uppercase; color: var(--muted); letter-spacing: .08em; }
            .budget-total .value { font-size: 1.8rem; font-weight: 800; color: var(--primary); }

            .enh-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .9rem; }
            .enh-item {
                display: flex;
                align-items: center;
                gap: .6rem;
                padding: .9rem 1rem;
                border-radius: 1rem;
                background: rgba(45, 52, 73, .4);
                border: 1px solid rgba(173, 198, 255, .06);
                font-size: .86rem;
                color: #dce4fb;
            }

            .source-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: .7rem .9rem;
                border-radius: .8rem;
                background: rgba(45, 52, 73, .35);
                margin-bottom: .5rem;
                font-size: .8rem;
                color: var(--muted);
            }

            @media (max-width: 900px) {
                .bento-grid [class*="span-"] { grid-column: span 12; }
                .mvp-grid, .enh-grid { grid-template-columns: 1fr; }
                .swot-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            }

            @media (max-width: 760px) {
                .navlinks { display: none; }
                .trait-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                .footerline { flex-direction: column; text-align: center; }
                .app-topbar { grid-template-columns: 1fr 2rem; padding: 0 1rem; }
                .app-nav, .side-rail { display: none; }
                .forge-main { padding: 0 1rem 3rem; }
                .swot-grid { grid-template-columns: 1fr; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def set_page(page, auth_mode="login"):
    st.session_state["page"] = page
    st.session_state["auth_mode"] = auth_mode
    if page != "auth":
        try:
            st.query_params.clear()
        except Exception:
            pass


def topbar(show_auth=True):
    left, middle, right = st.columns([0.32, 0.48, 0.2])
    with left:
        st.markdown(
            '<div class="topbar"><div class="brand"><span class="bolt">S</span> StartupSpark AI</div></div>',
            unsafe_allow_html=True,
        )
    with middle:
        st.markdown(
            """
            <div class="topbar navlinks">
                <span>Solutions</span><span>Process</span><span>Case Studies</span><span>Pricing</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        if show_auth:
            st.markdown(
                '<div class="topbar" style="justify-content:flex-end;"><a class="account-link" href="?page=auth&mode=login">◎</a></div>',
                unsafe_allow_html=True,
            )


def landing_page():
    topbar()
    st.markdown(
        """
        <section class="hero">
            <div>
                <div class="eyebrow">✧ The Future of Venture Architecture</div>
                <h1 class="hero-title">Turn Your Vision into a <span class="gradient-text">Scalable Startup</span></h1>
                <p class="hero-copy">
                    Deploy multi-agent AI ecosystems that handle market research, technical roadmapping,
                    validation, and GTM strategy in parallel.
                </p>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns([1, 0.95, 0.9, 1])
    with c2:
        if st.button("Launch Project  ↗", type="primary", use_container_width=True):
            set_page("auth", "signup")
            st.rerun()
    with c3:
        if st.button("View Ecosystem", use_container_width=True):
            st.session_state["scroll_hint"] = True

    st.markdown(
        """
        <div class="trait-row">
            <span>⚡ High Velocity</span>
            <span>◈ Enterprise Grade</span>
            <span>◇ Multi-Agent</span>
            <span>⌁ RAG-Optimized</span>
        </div>
        <h2 class="section-title">Intelligence Ecosystem</h2>
        <p class="section-subtitle">Three pillars of autonomous startup acceleration.</p>
        """,
        unsafe_allow_html=True,
    )

    a, b = st.columns([2, 1])
    with a:
        st.markdown(
            """
            <div class="glass-card">
                <div class="icon-tile">AI</div>
                <h3>Multi-Agent Analysis</h3>
                <p>Specialized AI agents coordinate like a founder team: market analyst, validation strategist,
                business planner, and technical roadmap builder.</p>
                <p>✓ Consensus-driven decisions<br>✓ Real-time market pressure simulation<br>✓ Founder-ready report output</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with b:
        st.markdown(
            """
            <div class="metric-card">
                <h3>Velocity Metrics</h3>
                <p>Reduce planning cycles with automated research, validation, and roadmapping.</p>
                <div class="big-number">12x</div>
                <strong>Faster GTM</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )

    c, d = st.columns(2)
    with c:
        st.markdown(
            """
            <div class="glass-card">
                <div class="icon-tile" style="background: linear-gradient(135deg, #ffb786, #df7412);">DB</div>
                <h3>RAG-based Research</h3>
                <p>Ground each idea in your knowledge base with domain-specific retrieval from healthcare,
                fintech, edtech, agritech, and cybersecurity sources.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with d:
        st.markdown(
            """
            <div class="glass-card">
                <div class="icon-tile" style="background: linear-gradient(135deg, #d0bcff, #571bc1); color: #fff;">MAP</div>
                <h3>Implementation Roadmap</h3>
                <p>Move from raw idea to MVP features, budget split, validation score, and phased execution plan.</p>
                <div class="mini-panel">Phase 1: Foundation <span style="float:right;color:#d0bcff;">75% Generated</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div class="wide-band">
            <h2 class="section-title" style="margin-top:0;">Accelerate GTM with <span class="gradient-text">Precision Intelligence</span></h2>
            <p class="section-subtitle">StartupSpark AI analyzes competitor weaknesses and market gaps to shape a practical launch strategy.</p>
            <div class="mini-panel"><strong>Market Gap Found</strong><br>Hyper-localized logistics and AI workflows for underserved founder segments.</div>
            <div class="mini-panel"><strong>Growth Vector</strong><br>Validation-first MVP with clear customer interviews, pricing tests, and launch channels.</div>
        </div>
        <div class="cta-box">
            <h2 class="section-title" style="margin-top:0;">Ready to Ignite?</h2>
            <p class="section-subtitle">Stop planning from a blank page. Start with an AI-generated startup blueprint.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    e1, e2, e3 = st.columns([1, 1, 1])
    with e1:
        if st.button("Get Early Access", type="primary", use_container_width=True):
            set_page("auth", "signup")
            st.rerun()
    with e2:
        if st.button("Talk to a Strategist", use_container_width=True):
            set_page("auth", "login")
            st.rerun()
    with e3:
        if st.button("Open Dashboard", use_container_width=True):
            if st.session_state.get("auth_user"):
                set_page("dashboard")
            else:
                set_page("auth", "login")
            st.rerun()

    st.markdown(
        """
        <div class="footerline">
            <span><strong style="color:#adc6ff;">StartupSpark AI</strong><br>High-velocity intelligence for next-generation founders.</span>
            <span>Privacy Policy &nbsp;&nbsp; Terms of Service &nbsp;&nbsp; AI Ethics</span>
            <span>© 2024 StartupSpark AI</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def auth_page():
    topbar(show_auth=False)
    disable_auth_autofill()
    st.markdown('<div class="auth-back-button">', unsafe_allow_html=True)
    if st.button("←", key="auth_back"):
        set_page("landing")
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    left, center, right = st.columns([0.28, 0.44, 0.28])
    with center:
        with st.container():
            selected_mode = st.radio(
                "Authentication mode",
                ["Login", "Sign Up"],
                index=1 if st.session_state.get("auth_mode") == "signup" else 0,
                horizontal=True,
                label_visibility="collapsed",
            )
            st.session_state["auth_mode"] = "signup" if selected_mode == "Sign Up" else "login"

        st.markdown(
            '<div class="auth-brand-large"><span class="bolt">S</span><span>StartupSpark AI</span></div>',
            unsafe_allow_html=True,
        )

        if selected_mode == "Login":
            st.markdown(
                """
                <div class="auth-title">Welcome Back</div>
                <div class="auth-subtitle">Enter your credentials to access the command center.</div>
                """,
                unsafe_allow_html=True,
            )
            with st.form("login_form", clear_on_submit=False):
                email = st.text_input("Email Address", placeholder="name@startup.com")
                password = st.text_input("Password", placeholder="••••••••", type="password")
                submitted = st.form_submit_button("Login to Dashboard  →", type="primary", use_container_width=True)
            if submitted:
                if not email.strip() or not password:
                    st.error("Email and password are required.")
                else:
                    try:
                        auth_client = create_supabase_auth_client()
                        if not auth_client:
                            st.error("Supabase credentials are missing in .env")
                        else:
                            login_res = auth_client.auth.sign_in_with_password(
                                {"email": email.strip(), "password": password}
                            )
                            logged_user = user_to_dict(getattr(login_res, "user", None))
                            if logged_user:
                                st.session_state["auth_user"] = logged_user
                                set_page("dashboard")
                                st.success("Login successful.")
                                st.rerun()
                            else:
                                st.error("Login failed. Please check credentials.")
                    except Exception as exc:
                        st.error(f"Login failed: {exc}")

        else:
            st.markdown(
                """
                <div class="auth-title">Join the Spark</div>
                <div class="auth-subtitle">Create your founder workspace and start building.</div>
                """,
                unsafe_allow_html=True,
            )
            with st.form("signup_form", clear_on_submit=False):
                name = st.text_input("Full Name", placeholder="Your name")
                email = st.text_input("Work Email", placeholder="name@startup.com")
                password = st.text_input("Create Password", type="password")
                confirm = st.text_input("Confirm Password", type="password")
                submitted = st.form_submit_button("Initialize Account  →", type="primary", use_container_width=True)
            if submitted:
                if not name.strip() or not email.strip() or not password:
                    st.error("Name, email, and password are required.")
                elif password != confirm:
                    st.error("Password and confirm password do not match.")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    try:
                        auth_client = create_supabase_auth_client()
                        if not auth_client:
                            st.error("Supabase credentials are missing in .env")
                        else:
                            signup_res = auth_client.auth.sign_up(
                                {
                                    "email": email.strip(),
                                    "password": password,
                                    "options": {"data": {"full_name": name.strip()}},
                                }
                            )
                            created_user = user_to_dict(getattr(signup_res, "user", None))
                            if created_user:
                                st.session_state["auth_user"] = created_user
                                set_page("dashboard")
                                st.success("Account created successfully.")
                                st.rerun()
                            else:
                                st.success("Account created. Please log in to continue.")
                    except Exception as exc:
                        st.error(f"Account creation failed: {exc}")


def dashboard_page():
    st.session_state.setdefault("dashboard_view", "form")
    # Sync from the URL only for values the top-nav <a> links actually use.
    # "report" is handled separately below and is never clobbered here,
    # so generating/opening a report always lands on the report page.
    query_view = st.query_params.get("view")
    if query_view == "form":
        st.session_state["dashboard_view"] = "form"
    elif query_view in {"reports", "roadmap"}:
        st.session_state["dashboard_view"] = "reports"
    elif query_view == "report" and st.session_state.get("last_report"):
        st.session_state["dashboard_view"] = "report"

    history = load_report_history()
    user = st.session_state.get("auth_user") or {}
    name = (user.get("user_metadata") or {}).get("full_name") or user.get("email") or "Founder"
    avatar_initial = (name.strip()[:1] or "F").upper()
    report_href = "?view=report" if st.session_state.get("last_report") else "?view=reports"
    st.markdown(
        f"""
        <div class="app-topbar">
            <div class="app-brand"><span>StartupSpark AI</span></div>
            <div class="app-nav">
                <a href="?view=form">Form</a>
                <a href="?page=landing">Explore</a>
                <a href="{report_href}">Reports</a>
            </div>
            <div class="app-user-icon">{esc(avatar_initial)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    shell_left, shell_main = st.columns([0.24, 0.76], gap="large")
    with shell_left:
        # Profile row + nav buttons rendered together at the TOP of the rail.
        st.markdown(
            f"""
            <div class="side-rail">
                <div class="profile-row">
                    <div class="avatar-dot">{esc(avatar_initial)}</div>
                    <div><strong>{esc(name)}</strong><br>Pro Tier - AI Active</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        current_view = st.session_state.get("dashboard_view")
        strategy_type = "primary" if current_view in {"form", "report"} else "secondary"
        roadmap_type = "primary" if current_view == "reports" else "secondary"
        if st.button("Strategy", use_container_width=True, type=strategy_type):
            st.session_state["dashboard_view"] = "form"
            st.query_params["view"] = "form"
            st.rerun()
        if st.button("Roadmap", use_container_width=True, type=roadmap_type):
            st.session_state["dashboard_view"] = "reports"
            st.query_params["view"] = "reports"
            st.rerun()
        if st.button("Logout", use_container_width=True):
            try:
                auth_client = create_supabase_auth_client()
                if auth_client:
                    auth_client.auth.sign_out()
            except Exception:
                pass
            st.session_state.pop("auth_user", None)
            st.session_state.pop("last_report", None)
            set_page("landing")
            st.rerun()

    with shell_main:
        if st.session_state.get("dashboard_view") == "reports":
            render_previous_reports(history)
            return

        if st.session_state.get("dashboard_view") == "report" and st.session_state.get("last_report"):
            render_report(st.session_state["last_report"])
            return

        st.markdown(
            """
            <main class="forge-main">
                <div class="forge-hero">
                    <div class="eyebrow">AI Analysis Engine</div>
                    <h1>Requirement Forge</h1>
                    <p>Define your startup's core parameters. Our AI consultants will analyze your inputs to generate a high-velocity strategy roadmap.</p>
                </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("startup_report_form"):
            c1, c2 = st.columns(2, gap="large")
            with c1:
                domain = st.selectbox("Startup Domain", SUPPORTED_DOMAINS, index=0)
                problem_statement = st.text_area(
                    "Problem Statement",
                    height=150,
                    placeholder="What primary challenge are you solving?",
                )
                target_audience = st.text_input("Target Audience", placeholder="e.g. SMBs in Southeast Asia")
            with c2:
                country_region = st.text_input("Country / Region", placeholder="Global / Specific Region")
                budget = st.slider("Available Budget (USD)", 1000, 1000000, 50000, 5000)
                business_stage = st.radio("Business Stage", ["Idea", "MVP", "Growth"], horizontal=True)
                additional = st.text_area(
                    "Additional Requirements",
                    height=108,
                    placeholder="Technical constraints, timeline, or specific AI models...",
                )
            st.markdown(
                """
                <div class="trust-row">
                    <div class="trust-copy"><span>Secure AI engine with encrypted report processing.</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            submitted = st.form_submit_button("Initialize Strategy", type="primary", use_container_width=True)
        st.markdown("</main>", unsafe_allow_html=True)

        if submitted:
            inputs = {
                "domain": domain,
                "domain_key": DISPLAY_TO_FOLDER.get(domain, domain.lower().replace(" ", "_")),
                "problem_statement": problem_statement,
                "target_audience": target_audience,
                "country_region": country_region,
                "budget": f"${budget:,}",
                "business_stage": "Existing Startup" if business_stage == "Growth" else business_stage,
                "additional_requirements": additional,
                "retriever_query": problem_statement,
            }
            with st.spinner("Analyzing concept and forging strategy..."):
                try:
                    report = orchestrate_startup(inputs)
                    st.session_state["last_report"] = report
                    remember_report(report)
                    st.session_state["dashboard_view"] = "report"
                    st.query_params["view"] = "report"
                    st.success("Strategy forged. Opening report.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Orchestration failed: {exc}")


def render_previous_reports(history):
    render_html(
        """
        <main class="forge-main">
            <div class="forge-hero">
                <div class="eyebrow">Roadmap Archive</div>
                <h1>Previous Reports</h1>
                <p>Review the strategy roadmaps you generated earlier and download any report as a PDF.</p>
            </div>
        </main>
        """
    )
    if not history:
        st.info("No previous reports yet. Generate a strategy from the Requirement Forge first.")
        return

    for item in history:
        report = item.get("report") or {}
        title = item.get("title") or report_title(report)
        created_at = item.get("created_at") or "Saved report"
        render_html(
            f"""
            <div class="report-card">
                <h3>{esc(title)}</h3>
                <p>{esc(created_at)}</p>
            </div>
            """
        )
        open_col, download_col, delete_col = st.columns([0.38, 0.38, 0.24])
        with open_col:
            if st.button("Open Report", key=f"open_{item.get('id')}", use_container_width=True):
                st.session_state["last_report"] = report
                st.session_state["dashboard_view"] = "report"
                st.query_params["view"] = "report"
                st.rerun()
        with download_col:
            st.download_button(
                "Download PDF",
                make_pdf_bytes(report),
                file_name=f"{safe_filename(title)}.pdf",
                mime="application/pdf",
                key=f"download_{item.get('id')}",
                use_container_width=True,
            )
        with delete_col:
            if st.button("Delete", key=f"delete_{item.get('id')}", use_container_width=True):
                updated_history = [h for h in load_report_history() if h.get("id") != item.get("id")]
                save_report_history(updated_history)
                if st.session_state.get("last_report") == report:
                    st.session_state.pop("last_report", None)
                    st.session_state["dashboard_view"] = "reports"
                    st.query_params["view"] = "reports"
                st.success("Report deleted.")
                st.rerun()


def render_report(report):
    idea = report.get("idea") or {}
    validation = normalized_validation(report)
    market = report.get("market_research") or {}
    business = report.get("business_model") or {}
    competitor_data = report.get("competitor_analysis") or {}
    competitors = competitor_data.get("competitors", [])
    mvp_features = report.get("mvp_features", [])
    swot = normalized_swot(report)
    roadmap = report.get("implementation_roadmap") or {}
    budget = report.get("estimated_budget") or {}
    future_enh = report.get("future_enhancements", [])
    sources = unique_nonempty(report.get("retrieved_sources", []))
    inputs = (report.get("metadata") or {}).get("input") or {}

    startup_name = idea.get("startup_name") or "Generated Startup Blueprint"
    tagline = idea.get("tagline") or "Your AI-generated roadmap is ready for review and export."

    # ---------- Header ----------
    render_html(
        f"""
        <div class="forge-main" style="padding-left:0; padding-right:0;">
            <div class="rpt-topline">
                <span>Analytics</span><span>›</span>
                <span class="current">{esc(startup_name)}</span>
            </div>
            <div class="rpt-hero">
                <h1>Analysis Report: <span>{esc(startup_name)}</span></h1>
                <p>{esc(tagline)}</p>
            </div>
        </div>
        """
    )

    back_col, pdf_col, json_col = st.columns([0.5, 0.25, 0.25])
    with back_col:
        if st.button("← Back to Requirement Forge", use_container_width=True):
            st.session_state["dashboard_view"] = "form"
            st.query_params["view"] = "form"
            st.rerun()
    with pdf_col:
        st.download_button(
            "Export PDF",
            make_pdf_bytes(report),
            file_name=f"{safe_filename(report_title(report))}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )
    with json_col:
        st.download_button(
            "Export JSON",
            json.dumps(report, indent=2),
            file_name=f"{safe_filename(report_title(report))}.json",
            mime="application/json",
            use_container_width=True,
        )

    # ---------- 1. Overview + 9. Validation ----------
    domain_audience = " / ".join(
        [v for v in [inputs.get("domain"), inputs.get("target_audience")] if v]
    ) or "N/A"

    innovation = validation.get("innovation")
    market_demand = validation.get("market_demand")
    feasibility = validation.get("feasibility")
    overall = validation.get("overall", "N/A")

    render_html(
        f"""
        <div class="bento-grid">

            <div class="glass-panel span-8">
                <div class="panel-head"><span class="ic">ⓘ</span> 1. Startup Overview</div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:2rem;">
                    <div>
                        <div class="field-label">Name</div>
                        <div class="field-value" style="color:var(--primary); font-weight:800; font-size:1.15rem;">{esc(startup_name)}</div>
                        <div class="field-label">Tagline</div>
                        <div class="field-value">{esc(tagline)}</div>
                    </div>
                    <div>
                        <div class="field-label">Domain &amp; Audience</div>
                        <div class="field-value">{esc(domain_audience)}</div>
                        <div class="field-label">Region</div>
                        <div class="field-value">{esc(inputs.get('country_region'))}</div>
                        <div class="chip-row">
                            <span class="chip">AI-First</span>
                            <span class="chip">{esc(inputs.get('domain'), 'General')}</span>
                            <span class="chip">{esc(inputs.get('business_stage'), 'Startup')}</span>
                        </div>
                    </div>
                </div>
            </div>

            <div class="glass-panel span-4">
                <div class="panel-head"><span class="ic">✓</span> 9. Validation</div>
                <div class="validation-row"><span>Innovation</span><strong>{esc(innovation, '—')}</strong></div>
                <div class="bar-track"><div class="bar-fill" style="width:{score_pct(innovation)}%;"></div></div>
                <div class="validation-row"><span>Market Demand</span><strong>{esc(market_demand, '—')}</strong></div>
                <div class="bar-track"><div class="bar-fill" style="width:{score_pct(market_demand)}%; background:var(--accent);"></div></div>
                <div class="validation-row"><span>Feasibility</span><strong>{esc(feasibility, '—')}</strong></div>
                <div class="bar-track"><div class="bar-fill" style="width:{score_pct(feasibility)}%; background:var(--secondary);"></div></div>
                <div class="spark-score">
                    <div class="label">Overall Spark Score</div>
                    <div class="value">{esc(overall)}</div>
                </div>
            </div>

            <div class="glass-panel span-6">
                <div class="panel-head"><span class="ic">⚠</span> 2. Problem Statement</div>
                <div class="tint-box tint-error">{esc(inputs.get('problem_statement'), 'No problem statement provided.')}</div>
            </div>

            <div class="glass-panel span-6">
                <div class="panel-head"><span class="ic">✦</span> 3. Proposed Solution</div>
                <div class="tint-box tint-primary">{esc(idea.get('ai_solution') or idea.get('core_idea'), 'No solution details available.')}</div>
            </div>

        </div>
        """
    )

    # ---------- 4/5. Market + Competitors ----------
    market_stats = market.get("stats") or {}
    cagr = market_stats.get("cagr") or market.get("cagr") or "N/A"
    tam = market_stats.get("tam") or market.get("tam") or "N/A"

    comp_rows = "".join(
        f"""
        <tr>
            <td style="font-weight:700;">{esc(c.get('name'))}</td>
            <td style="color:var(--primary);">{esc(c.get('strengths'))}</td>
            <td style="color:var(--muted); font-size:.8rem;">{esc(c.get('weaknesses'))}</td>
        </tr>
        """
        for c in competitors
    ) or '<tr><td colspan="3" style="color:var(--muted);">No competitors found in current knowledge base sample.</td></tr>'

    render_html(
        f"""
        <div class="bento-grid">
            <div class="glass-panel span-12">
                <div class="panel-head"><span class="ic">↗</span> 4. Market &amp; 5. Competitor Landscape</div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:2.5rem;">
                    <div>
                        <div class="field-label" style="margin-bottom:.8rem;">Market Trends</div>
                        <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem;">
                            <div class="stat-mini">
                                <div class="num" style="color:var(--primary);">{esc(cagr)}</div>
                                <div class="cap">CAGR - Sector Growth</div>
                            </div>
                            <div class="stat-mini">
                                <div class="num" style="color:var(--accent);">{esc(tam)}</div>
                                <div class="cap">Total Addressable Market</div>
                            </div>
                        </div>
                        <p style="color:var(--muted); font-style:italic; margin-top:1.2rem; font-size:.88rem; line-height:1.6;">
                            {esc(market.get('summary'), 'No market summary available.')}
                        </p>
                    </div>
                    <div>
                        <div class="field-label" style="margin-bottom:.8rem;">Competitor Benchmarking</div>
                        <table class="comp-table">
                            <thead><tr><th>Competitor</th><th>Strength</th><th>Weakness</th></tr></thead>
                            <tbody>{comp_rows}</tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        """
    )

    # ---------- 6. Business Model + 7. MVP Features ----------
    mvp_html = "".join(
        f"""
        <div class="mvp-item">
            <span class="ic">✦</span>
            <div><h5>{esc(feature)}</h5></div>
        </div>
        """
        for feature in mvp_features
    ) or '<p style="color:var(--muted);">No MVP features generated yet.</p>'

    render_html(
        f"""
        <div class="bento-grid">
            <div class="glass-panel span-5">
                <div class="panel-head"><span class="ic">$</span> 6. Business Model</div>
                <div class="budget-row" style="font-size:.92rem;"><span>Revenue Model</span><strong>{esc(business.get('revenue_model'), 'TBD')}</strong></div>
                <div class="budget-row" style="font-size:.92rem; margin-bottom:1rem;"><span>Pricing</span><strong>{esc(business.get('pricing'), 'TBD')}</strong></div>
                <div class="field-label">Segments</div>
                <div class="field-value" style="margin-bottom:0;">{esc(business.get('segments'), 'N/A')}</div>
            </div>
            <div class="glass-panel span-7">
                <div class="panel-head"><span class="ic">▤</span> 7. MVP Features</div>
                <div class="mvp-grid">{mvp_html}</div>
            </div>
        </div>
        """
    )

    # ---------- 8. SWOT ----------
    def swot_list(items):
        items = items or []
        if isinstance(items, str):
            items = [items]
        if not items:
            return "<li>N/A</li>"
        return "".join(f"<li>{esc(item)}</li>" for item in items)

    render_html(
        f"""
        <div class="bento-grid">
            <div class="glass-panel span-12">
                <div class="panel-head"><span class="ic">▦</span> 8. SWOT Analysis</div>
                <div class="swot-grid">
                    <div class="swot-card swot-strength">
                        <h5>🏋 Strengths</h5>
                        <ul>{swot_list(swot.get('strengths'))}</ul>
                    </div>
                    <div class="swot-card swot-weak">
                        <h5>⚠ Weaknesses</h5>
                        <ul>{swot_list(swot.get('weaknesses'))}</ul>
                    </div>
                    <div class="swot-card swot-opp">
                        <h5>💡 Opportunities</h5>
                        <ul>{swot_list(swot.get('opportunities'))}</ul>
                    </div>
                    <div class="swot-card swot-threat">
                        <h5>⛔ Threats</h5>
                        <ul>{swot_list(swot.get('threats'))}</ul>
                    </div>
                </div>
            </div>
        </div>
        """
    )

    # ---------- 10. Roadmap + 11. Budget ----------
    roadmap_items = list(roadmap.items()) if roadmap else []
    roadmap_html = "".join(
        f"""
        <div class="tl-item {'done' if i == 0 else ''}">
            <div class="tl-dot"></div>
            <h5>{esc(phase.replace('_', ' ').title())}</h5>
            <p>{esc(detail)}</p>
        </div>
        """
        for i, (phase, detail) in enumerate(roadmap_items)
    ) or '<p style="color:var(--muted);">No roadmap generated yet.</p>'

    budget_items = list(budget.items()) if budget else []
    max_budget_val = 0
    parsed_budget = []
    for key, value in budget_items:
        num = re.sub(r"[^\d.]", "", str(value)) or "0"
        try:
            num_val = float(num)
        except ValueError:
            num_val = 0
        parsed_budget.append((key, value, num_val))
        max_budget_val = max(max_budget_val, num_val)

    bar_colors = ["var(--primary)", "var(--secondary)", "var(--accent)", "var(--muted)"]
    budget_html = ""
    total_seed = None
    for i, (key, value, num_val) in enumerate(parsed_budget):
        pct = (num_val / max_budget_val * 100) if max_budget_val > 0 else 0
        color = bar_colors[i % len(bar_colors)] if bar_colors else "var(--primary)"
        budget_html += f"""
            <div class="budget-row"><span>{esc(key.replace('_', ' ').title())}</span><strong>{esc(value)}</strong></div>
            <div class="bar-track"><div class="bar-fill" style="width:{pct}%; background:{color};"></div></div>
        """
    if not budget_html:
        budget_html = '<p style="color:var(--muted);">No budget breakdown available.</p>'

    if parsed_budget:
        total_val = sum(v for _, _, v in parsed_budget)
        total_seed = f"${total_val:,.0f}"

    render_html(
        f"""
        <div class="bento-grid">
            <div class="glass-panel span-8">
                <div class="panel-head"><span class="ic">⟿</span> 10. Implementation Roadmap</div>
                <div class="timeline">{roadmap_html}</div>
            </div>
            <div class="glass-panel span-4">
                <div class="panel-head"><span class="ic">💼</span> 11. Estimated Budget</div>
                {budget_html}
                <div class="budget-total">
                    <div class="label">Total Required Seed</div>
                    <div class="value">{total_seed if total_seed is not None else 'N/A'}</div>
                </div>
            </div>
        </div>
        """
    )

    # ---------- 12. Future Enhancements + 13. Retrieved Sources ----------
    enh_html = "".join(
        f'<div class="enh-item">✦ {esc(item)}</div>' for item in future_enh
    ) or '<p style="color:var(--muted);">No future enhancements listed.</p>'

    src_html = "".join(
        f'<div class="source-item"><span>{esc(src)}</span><span>↗</span></div>'
        for src in sources[:10]
    ) or '<p style="color:var(--muted);">No sources retrieved.</p>'

    render_html(
        f"""
        <div class="bento-grid">
            <div class="glass-panel span-6">
                <div class="panel-head"><span class="ic">🚀</span> 12. Future Enhancements</div>
                <div class="enh-grid">{enh_html}</div>
            </div>
            <div class="glass-panel span-6">
                <div class="panel-head"><span class="ic">📚</span> 13. Retrieved Sources (RAG)</div>
                {src_html}
            </div>
        </div>
        <div style="height:2rem;"></div>
        """
    )


def main():
    st.set_page_config(page_title=PROJECT_TITLE, page_icon="⚡", layout="wide")
    inject_styles()
    st.session_state.setdefault("page", "landing")
    st.session_state.setdefault("auth_mode", "login")
    query_page = st.query_params.get("page")
    query_mode = st.query_params.get("mode")
    if query_page == "landing":
        st.session_state["page"] = "landing"
    elif query_page == "auth":
        st.session_state["page"] = "auth"
        st.session_state["auth_mode"] = "signup" if query_mode == "signup" else "login"

    if st.session_state["page"] == "auth":
        auth_page()
    elif st.session_state["page"] == "dashboard":
        if st.session_state.get("auth_user"):
            dashboard_page()
        else:
            set_page("auth", "login")
            st.rerun()
    else:
        landing_page()


if __name__ == "__main__":
    main()
