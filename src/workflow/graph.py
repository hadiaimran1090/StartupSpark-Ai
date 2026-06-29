from src.agents.business_plan_agent import create_business_plan
from src.agents.idea_agent import generate_idea
from src.agents.market_agent import analyze_market
from src.agents.validation_agent import validate_idea


def run_workflow(domain: str, context: str) -> dict:
    idea = generate_idea(domain, context)
    market = analyze_market(domain, context)
    validation = validate_idea(domain, idea)
    business_plan = create_business_plan(domain, idea)

    return {
        "domain": domain,
        "idea": idea,
        "market_analysis": market,
        "validation": validation,
        "business_plan": business_plan,
    }
