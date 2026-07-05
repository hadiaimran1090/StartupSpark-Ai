import json
import os
import re
import urllib.parse
import urllib.request
from typing import Dict, Any

from src.rag.retriever import query_supabase


def _configured_key(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value or value.lower().startswith("your_") or value.lower() in {"your api key", "none", "null"}:
        return ""
    return value


def call_llm(prompt: str, temperature: float = 0.45) -> str:
    """Return an LLM response, preferring Gemini when GOOGLE_API_KEY is configured.

    NOTE: previously both provider branches used `except Exception: pass`,
    which silently swallowed the real failure reason (auth errors, bad key
    format, missing packages, quota errors, etc.) and made every failure
    look identical: "LLM did not return a response". Now every failure is
    logged with the exception type/message so the real cause is visible in
    the console/logs.
    """
    if os.getenv("DISABLE_LLM", "").lower() in {"1", "true", "yes"}:
        return ""

    google_key = _configured_key("GOOGLE_API_KEY")
    if google_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            llm = ChatGoogleGenerativeAI(model=model, temperature=temperature, google_api_key=google_key)
            response = llm.invoke(prompt)
            content = getattr(response, "content", str(response)) or ""
            if content:
                return content
            print("[call_llm] Gemini returned an empty response; falling back to OpenAI if configured.")
        except Exception as exc:
            print(f"[call_llm] Gemini call failed: {type(exc).__name__}: {exc}")

    openai_key = _configured_key("OPENAI_API_KEY")
    if openai_key:
        try:
            # ChatOpenAI moved out of langchain_community into its own
            # package. Install it with: pip install -U langchain-openai
            from langchain_openai import ChatOpenAI

            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            llm = ChatOpenAI(temperature=temperature, model=model, api_key=openai_key)
            response = llm.invoke(prompt)
            content = getattr(response, "content", str(response)) or ""
            if content:
                return content
            print("[call_llm] OpenAI returned an empty response.")
        except Exception as exc:
            print(f"[call_llm] OpenAI call failed: {type(exc).__name__}: {exc}")

    return ""



def parse_llm_json(raw: str):
    """Parse plain JSON or JSON wrapped in a markdown code fence."""
    if not raw:
        return None
    text = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        return json.loads(text)
    except Exception:
        return None


def extract_json_object(raw: str) -> Dict[str, Any]:
    parsed = parse_llm_json(raw)
    return parsed if isinstance(parsed, dict) else {}


def _safe_join_texts(rows):
    texts = []
    for s, r in rows:
        t = r.get('text') or r.get('content') or ''
        if t:
            texts.append(t)
    return "\n\n".join(texts[:10])


def _strip_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = re.sub(r"&quot;", '"', value)
    value = re.sub(r"&amp;", "&", value)
    value = re.sub(r"&#39;", "'", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _unique_rows(rows):
    seen = set()
    unique = []
    for score, row in rows or []:
        source = row.get("source") or row.get("title") or ""
        text = row.get("text") or row.get("content") or ""
        key = (source.strip().casefold(), text[:160].strip().casefold())
        if key in seen:
            continue
        seen.add(key)
        unique.append((score, row))
    return unique


def external_web_context(inputs: Dict[str, Any], top_k: int = 4):
    if os.getenv("ENABLE_EXTERNAL_SEARCH", "1").lower() in {"0", "false", "no"}:
        return []
    query_parts = [
        inputs.get("problem_statement") or inputs.get("retriever_query") or "",
        inputs.get("domain") or "",
        inputs.get("country_region") or "",
        "startup market competitors validation",
    ]
    query = " ".join(part for part in query_parts if part).strip()
    if not query:
        return []
    url = "https://duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            html = response.read().decode("utf-8", "ignore")
    except Exception as exc:
        print(f"[external_web_context] search request failed: {type(exc).__name__}: {exc}")
        return []

    titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, flags=re.I | re.S)
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, flags=re.I | re.S)
    rows = []
    for idx, title in enumerate(titles[:top_k]):
        clean_title = _strip_html(title) or "External market source"
        clean_snippet = _strip_html(snippets[idx] if idx < len(snippets) else "")
        text = clean_snippet or clean_title
        rows.append(
            (
                0.5,
                {
                    "title": clean_title,
                    "source": f"External web: {clean_title}",
                    "text": text,
                    "metadata": {"source_type": "external_web"},
                },
            )
        )
    return rows


def _source_summary(rows):
    sources = []
    for score, row in rows or []:
        title = row.get("title") or row.get("source") or "Untitled source"
        text = _strip_html(row.get("text") or row.get("content") or "")
        source = row.get("source") or title
        if not text:
            continue
        sources.append(
            {
                "title": title,
                "source": source,
                "score": score,
                "excerpt": text[:900],
            }
        )
    return sources[:12]


def _tools_used(rows):
    tools = ["supabase_rag_retriever"]
    if any(((row.get("metadata") or {}).get("source_type") == "external_web") for _, row in (rows or [])):
        tools.append("external_web_search")
    return tools


def _required_report_keys():
    return {
        "idea",
        "market_research",
        "competitor_analysis",
        "business_model",
        "swot_analysis",
        "validation",
        "mvp_features",
        "implementation_roadmap",
        "estimated_budget",
        "future_enhancements",
    }


def generate_llm_report(inputs: Dict[str, Any], retrieved_rows) -> Dict[str, Any]:
    sources = _source_summary(retrieved_rows)
    if not _configured_key("GOOGLE_API_KEY") and not _configured_key("OPENAI_API_KEY"):
        raise RuntimeError(
            "No LLM key configured. Add GOOGLE_API_KEY for Gemini or OPENAI_API_KEY in .env; "
            "hardcoded fallback report generation is disabled."
        )
    if not sources:
        raise RuntimeError(
            "No RAG or web context was retrieved. Add/upload knowledge-base data or enable external search; "
            "hardcoded fallback report generation is disabled."
        )

    prompt = f"""
You are StartupSpark AI's research-and-strategy engine.

Generate one complete startup report from the USER_INPUTS and RETRIEVED_CONTEXT below.
Use the retrieved context as evidence, then reason with current market/business judgment.

Strict rules:
- Return only valid JSON. No markdown fences. No commentary.
- Do not use placeholders or generic templates.
- Do not name the startup by simply combining the domain with "AI Solutions", "AI", "Tech", or "Startup".
- Generate a distinctive startup_name each run, suitable for a real company.
- Every section must be specific to the user problem, audience, country/region, budget, stage, and retrieved context.
- Competitors may be direct, indirect, or adjacent substitutes, but must be plausible and specific.
- Budget values should fit the user's available budget when provided.
- Include evidence_notes fields where useful, citing retrieved source titles or source names from RETRIEVED_CONTEXT.
- Vary wording and strategic choices naturally; do not repeat canned feature lists.

Return this exact JSON shape:
{{
  "idea": {{
    "startup_name": "distinctive brand name",
    "tagline": "short specific tagline",
    "core_idea": "specific product concept",
    "ai_solution": "specific AI/RAG/automation approach"
  }},
  "market_research": {{
    "summary": "grounded market summary",
    "trends": ["specific trend 1", "specific trend 2", "specific trend 3"],
    "stats": {{"tam": "market estimate or reasoned proxy", "cagr": "growth estimate or reasoned proxy"}},
    "evidence_notes": ["source-backed note 1", "source-backed note 2"]
  }},
  "competitor_analysis": {{
    "competitors": [
      {{"name": "competitor or substitute", "strengths": "specific strength", "weaknesses": "specific weakness"}}
    ]
  }},
  "business_model": {{
    "revenue_model": "specific revenue model",
    "pricing": "specific pricing strategy",
    "budget": "user budget or budget interpretation",
    "stage": "stage",
    "segments": "specific buyer/user segments"
  }},
  "swot_analysis": {{
    "strengths": ["specific strength"],
    "weaknesses": ["specific weakness"],
    "opportunities": ["specific opportunity"],
    "threats": ["specific threat"]
  }},
  "validation": {{
    "innovation": 1,
    "market_demand": 1,
    "feasibility": 1,
    "scalability": 1,
    "overall": 1,
    "rationale": "short scoring rationale"
  }},
  "mvp_features": ["specific MVP feature"],
  "implementation_roadmap": {{
    "phase_1": "specific milestone and timeframe",
    "phase_2": "specific milestone and timeframe",
    "phase_3": "specific milestone and timeframe",
    "phase_4": "specific milestone and timeframe"
  }},
  "estimated_budget": {{
    "category_name": 0
  }},
  "future_enhancements": ["specific enhancement"]
}}

USER_INPUTS:
{json.dumps(inputs, ensure_ascii=False, indent=2)}

RETRIEVED_CONTEXT:
{json.dumps(sources, ensure_ascii=False, indent=2)}
""".strip()

    raw = call_llm(prompt, temperature=0.8)
    if not raw:
        raise RuntimeError(
            "LLM did not return a response. Check GOOGLE_API_KEY/GEMINI_MODEL or OPENAI_API_KEY/OPENAI_MODEL; "
            "see console logs from call_llm for the specific provider error. "
            "Hardcoded fallback report generation is disabled."
        )
    report = extract_json_object(raw)
    missing = _required_report_keys() - set(report)
    if missing:
        raise RuntimeError(
            "LLM did not return a complete report JSON. Missing keys: "
            + ", ".join(sorted(missing))
        )

    report["swot"] = report.get("swot_analysis") or {}
    report["metadata"] = {
        "input": inputs,
        "generation": {
            "mode": "rag_llm",
            "retrieved_source_count": len(sources),
            "llm_provider": "gemini" if _configured_key("GOOGLE_API_KEY") else "openai",
            "tools_used": _tools_used(retrieved_rows),
        },
    }
    report["retrieved_sources"] = list(
        dict.fromkeys(src.get("source") or src.get("title") for src in sources if src.get("source") or src.get("title"))
    )
    return report


def orchestrate_startup(inputs: Dict[str, Any]) -> Dict[str, Any]:
    # normalize domain key
    domain = inputs.get('domain_key') or inputs.get('domain', '')
    # retrieval query: prefer explicit retriever_query else problem statement
    query = inputs.get('retriever_query') or inputs.get('problem_statement') or ''
    # run retrieval (auto mode uses RPC then fallback)
    retrieved = query_supabase(query, domain=domain, top_k=6, mode='auto')
    retrieved_text = _safe_join_texts(retrieved)
    if len(retrieved_text.strip()) < 350:
        retrieved = _unique_rows((retrieved or []) + external_web_context(inputs, top_k=5))
    retrieved_text = _safe_join_texts(retrieved)

    return generate_llm_report(inputs, retrieved)