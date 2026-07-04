import json
import os
import re
import urllib.parse
import urllib.request
from typing import Dict, Any

from src.rag.retriever import query_supabase


# LLM integration (LangChain/OpenAI). Uses OPENAI_API_KEY if present.
def get_llm():
    try:
        from langchain.llms import OpenAI
    except Exception:
        return None
    key = os.getenv('OPENAI_API_KEY')
    if not key:
        return None
    try:
        # model name: gpt-5-mini (OpenAI-compatible)
        return OpenAI(temperature=0.2, model_name="gpt-5-mini", openai_api_key=key)
    except Exception:
        return None


def call_llm(prompt: str) -> str:
    llm = get_llm()
    if not llm:
        return ""
    try:
        return llm(prompt)
    except Exception:
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
    except Exception:
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


def _input_profile(inputs: Dict[str, Any]) -> Dict[str, str]:
    problem = (inputs.get("problem_statement") or inputs.get("retriever_query") or "the target customer problem").strip()
    domain = (inputs.get("domain") or "AI startup").strip()
    audience = (inputs.get("target_audience") or "target customers").strip()
    region = (inputs.get("country_region") or "the selected market").strip()
    stage = (inputs.get("business_stage") or "Idea").strip()
    return {"problem": problem, "domain": domain, "audience": audience, "region": region, "stage": stage}


def idea_generation_agent(inputs: Dict[str, Any], retrieved_text: str) -> Dict[str, str]:
    problem = inputs.get('problem_statement', '').strip() or inputs.get('retriever_query', '')
    domain = inputs.get('domain', '')
    # If LLM available, ask it to generate a JSON response with fields
    llm_prompt = (
        f"You are an assistant that generates startup ideas.\nDomain: {domain}\nProblem: {problem}\nContext: {retrieved_text[:1000]}\n"
        "Respond with a JSON object exactly with keys: startup_name, tagline, core_idea, ai_solution."
    )
    llm_out = call_llm(llm_prompt)
    if llm_out:
        parsed = parse_llm_json(llm_out)
        if isinstance(parsed, dict):
            # ensure keys exist
            return {
                "startup_name": parsed.get("startup_name"),
                "tagline": parsed.get("tagline"),
                "core_idea": parsed.get("core_idea"),
                "ai_solution": parsed.get("ai_solution"),
            }

    # deterministic fallback
    profile = _input_profile(inputs)
    name = f"{domain.split()[0] if domain else 'Spark'} AI Solutions"
    tagline = f"Solving: {problem[:80]}"
    core = (
        f"Build an AI-powered {profile['domain']} product for {profile['audience']} in {profile['region']} "
        f"that reduces the pain point: {profile['problem']}."
    )
    ai_solution = (
        "Use retrieval-augmented workflows, predictive scoring, automated triage, and a human-in-the-loop dashboard "
        "to turn customer inputs into prioritized recommendations and operational actions."
    )
    return {"startup_name": name, "tagline": tagline, "core_idea": core, "ai_solution": ai_solution}


def market_research_agent(inputs: Dict[str, Any], retrieved_text: str) -> Dict[str, Any]:
    # try LLM-based summary if available
    llm_prompt = (
        f"You are an analyst. Summarize the following context into a short market research summary and list top 3 trends as a JSON with keys: summary, trends (array).\\nContext: {retrieved_text[:2000]}"
    )
    llm_out = call_llm(llm_prompt)
    if llm_out:
        parsed = parse_llm_json(llm_out)
        if isinstance(parsed, dict):
            return {"summary": parsed.get("summary"), "trends": parsed.get("trends"), "sources_count": 0}
    # summarize retrieved text heuristically
    profile = _input_profile(inputs)
    if retrieved_text:
        summary = _strip_html(retrieved_text)[:1000]
    else:
        summary = (
            f"{profile['domain']} demand in {profile['region']} is shaped by customer access gaps, workflow automation, "
            f"cost pressure, and the need for measurable outcomes for {profile['audience']}. The opportunity is strongest "
            "where the product can prove faster service, lower operating cost, or better decision quality in a focused pilot."
        )
    trends = [
        "AI-assisted workflow automation",
        "Localized customer acquisition and trust-building",
        "Outcome-based pricing and pilot-first adoption",
    ]
    return {"summary": summary, "trends": trends, "sources_count": len(retrieved_text or "")}


def competitor_analysis_agent(inputs: Dict[str, Any], retrieved_text: str) -> Dict[str, Any]:
    # try LLM to extract competitors
    llm_prompt = (
        f"Extract up to 5 potential competitors or existing solutions from the context. Respond with JSON array under key 'competitors' where each item has name, strengths, weaknesses. Context: {retrieved_text[:2000]}"
    )
    llm_out = call_llm(llm_prompt)
    if llm_out:
        parsed = parse_llm_json(llm_out)
        if isinstance(parsed, dict):
            comps = parsed.get('competitors') or []
            return {"competitors": comps}
    # crude competitor extraction fallback
    profile = _input_profile(inputs)
    competitors = [
        {
            "name": f"Existing {profile['domain']} SaaS platforms",
            "strengths": "Established workflows, integrations, and customer trust",
            "weaknesses": "Often broad, expensive, and weakly localized for the selected audience",
        },
        {
            "name": "Manual service providers and consultants",
            "strengths": "High-touch support and local relationships",
            "weaknesses": "Slow delivery, inconsistent quality, and limited scalability",
        },
        {
            "name": "Generic AI assistants",
            "strengths": "Low-cost and flexible for early experimentation",
            "weaknesses": "Lack domain-specific data, compliance controls, and workflow ownership",
        },
    ]
    return {"competitors": competitors}


def business_model_agent(inputs: Dict[str, Any]) -> Dict[str, Any]:
    profile = _input_profile(inputs)
    stage = inputs.get('business_stage', 'Idea')
    budget = inputs.get('budget', '')
    revenue = "SaaS subscription + paid pilots + implementation support"
    pricing = f"Pilot package for {profile['audience']}, then tiered monthly plans by usage, seats, or managed locations"
    return {"revenue_model": revenue, "pricing": pricing, "budget": budget, "stage": stage, "segments": profile["audience"]}


def swot_agent(inputs: Dict[str, Any], retrieved_text: str) -> Dict[str, Any]:
    profile = _input_profile(inputs)
    strengths = [
        f"Focused solution for {profile['audience']} in {profile['region']}",
        "AI-first automation can reduce manual workload and response time",
        "Pilot-friendly MVP can be launched with a narrow workflow",
    ]
    weaknesses = [
        "Needs reliable customer data and workflow integrations",
        "Early trust-building and proof of ROI will be required",
    ]
    opportunities = [
        f"Underserved {profile['domain']} workflows can be localized by region and customer segment",
        "Partnerships with existing operators can accelerate distribution",
    ]
    threats = [
        "Incumbent platforms may copy high-value features",
        "Regulatory, privacy, or procurement friction can slow adoption",
    ]
    return {"strengths": strengths, "weaknesses": weaknesses, "opportunities": opportunities, "threats": threats}


def validation_agent(inputs: Dict[str, Any]) -> Dict[str, Any]:
    profile = _input_profile(inputs)
    problem_len = len(profile["problem"])
    audience_bonus = 1 if profile["audience"] != "target customers" else 0
    region_bonus = 1 if profile["region"] != "the selected market" else 0
    scores = {
        "innovation": min(9, 6 + (1 if "ai" in profile["domain"].lower() else 0) + audience_bonus),
        "market_demand": min(9, 6 + (1 if problem_len > 40 else 0) + region_bonus),
        "feasibility": 7 if problem_len else 5,
        "scalability": min(9, 6 + audience_bonus + region_bonus),
    }
    overall = round(sum(scores.values()) / len(scores), 2)
    return {**scores, "scores": scores, "overall": overall}


def report_generator(inputs: Dict[str, Any], agents_output: Dict[str, Any], retrieved_rows) -> Dict[str, Any]:
    report = {
        "metadata": {"input": inputs},
        "idea": agents_output.get('idea'),
        "market_research": agents_output.get('market'),
        "competitor_analysis": agents_output.get('competitor'),
        "business_model": agents_output.get('business'),
        "swot": agents_output.get('swot'),
        "swot_analysis": agents_output.get('swot'),
        "validation": agents_output.get('validation'),
        "retrieved_sources": list(dict.fromkeys([r.get('source') or r.get('title') for s, r in (retrieved_rows or []) if r.get('source') or r.get('title')])),
    }
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

    agents_output = {}
    agents_output['idea'] = idea_generation_agent(inputs, retrieved_text)
    agents_output['market'] = market_research_agent(inputs, retrieved_text)
    agents_output['competitor'] = competitor_analysis_agent(inputs, retrieved_text)
    agents_output['business'] = business_model_agent(inputs)
    agents_output['swot'] = swot_agent(inputs, retrieved_text)
    agents_output['validation'] = validation_agent(inputs)

    final = report_generator(inputs, agents_output, retrieved)
    # add simple MVP features, roadmap and budget heuristics
    # MVP features: login, dashboard, core AI, analytics, notifications
    mvp = [
        "User authentication (mobile + web)",
        "Dashboard for recommendations",
        "Core AI recommendation / prediction module",
        "Basic analytics and reporting",
        "Notifications (email / SMS / WhatsApp)"
    ]
    roadmap = {
        "phase_1": "Research & prototyping (2-4 weeks)",
        "phase_2": "MVP development (6-10 weeks)",
        "phase_3": "Pilot with early customers (4-8 weeks)",
        "phase_4": "Launch & iterate (ongoing)"
    }
    # simple budget split
    budget_total = inputs.get('budget') or "TBD"
    try:
        # try parse numeric value if possible
        b = str(budget_total).replace('$','').replace(',','').strip()
        bnum = float(b) if b else None
    except Exception:
        bnum = None
    if bnum:
        est = {
            "development": round(bnum * 0.5, 2),
            "cloud": round(bnum * 0.2, 2),
            "marketing": round(bnum * 0.15, 2),
            "operations": round(bnum * 0.15, 2),
        }
    else:
        est = {"development": "TBD", "cloud": "TBD", "marketing": "TBD", "operations": "TBD"}

    final["mvp_features"] = mvp
    final["implementation_roadmap"] = roadmap
    final["estimated_budget"] = est
    final["future_enhancements"] = ["Multilingual support", "Offline-first mobile features", "Integrations with local platforms"]
    return final
