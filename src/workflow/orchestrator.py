import json
import os
import re
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
    name = f"{domain.split()[0]} AI Solutions"
    tagline = f"Solving: {problem[:80]}"
    core = f"Build an AI-powered {domain} product that addresses: {problem}. Key context: {retrieved_text[:300]}"
    ai_solution = "Use supervised models + domain-specific rules to extract insights from documents and make decisions for end users."
    return {"startup_name": name, "tagline": tagline, "core_idea": core, "ai_solution": ai_solution}


def market_research_agent(retrieved_text: str) -> Dict[str, Any]:
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
    summary = (retrieved_text or '')[:1000]
    trends = "; ".join([line.strip() for line in summary.split('\n')[:5] if line.strip()])
    return {"summary": summary, "trends": trends, "sources_count": 0}


def competitor_analysis_agent(retrieved_text: str) -> Dict[str, Any]:
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
    competitors = []
    if retrieved_text:
        lines = [l.strip() for l in retrieved_text.split('\n') if l.strip()]
        for l in lines[:5]:
            competitors.append({"name": l[:60], "strengths": "Established content", "weaknesses": "Limited customization"})
    return {"competitors": competitors}


def business_model_agent(inputs: Dict[str, Any]) -> Dict[str, Any]:
    stage = inputs.get('business_stage', 'Idea')
    budget = inputs.get('budget', '')
    revenue = "SaaS subscription + professional services"
    pricing = "Tiered pricing: freemium, standard, enterprise"
    return {"revenue_model": revenue, "pricing": pricing, "budget": budget, "stage": stage}


def swot_agent(inputs: Dict[str, Any], retrieved_text: str) -> Dict[str, Any]:
    strengths = "Domain knowledge and low-cost MVP"
    weaknesses = "Data availability and integration"
    opportunities = "Growing demand and under-served markets"
    threats = "Competition from incumbents and regulation"
    return {"strengths": strengths, "weaknesses": weaknesses, "opportunities": opportunities, "threats": threats}


def validation_agent(inputs: Dict[str, Any]) -> Dict[str, Any]:
    # simple heuristic scoring
    scores = {
        "innovation": 8,
        "market_demand": 7,
        "feasibility": 7,
        "scalability": 7,
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
        "retrieved_sources": [r.get('source') or r.get('title') for s, r in (retrieved_rows or [])],
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

    agents_output = {}
    agents_output['idea'] = idea_generation_agent(inputs, retrieved_text)
    agents_output['market'] = market_research_agent(retrieved_text)
    agents_output['competitor'] = competitor_analysis_agent(retrieved_text)
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
