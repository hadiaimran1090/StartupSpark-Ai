from frontend import main as _startupspark_frontend_main

_startupspark_frontend_main()

import streamlit as st
st.stop()
import os
from dotenv import load_dotenv

from src.config import PROJECT_TITLE, SUPPORTED_DOMAINS
from src.rag.retriever import query_supabase
from src.workflow.orchestrator import orchestrate_startup

load_dotenv()

st.set_page_config(page_title=PROJECT_TITLE, page_icon="🚀", layout="wide")

st.title(PROJECT_TITLE)
st.caption("Multi-agent startup idea generator with RAG, LangChain, LangGraph, and Supabase")

# map display names to internal domain keys
display_to_folder = {
    "Healthcare AI": "healthcare_ai",
    "FinTech": "fintech",
    "Education AI": "edtech",
    "Agriculture Tech": "agritech",
    "Cybersecurity": "cybersecurity",
}


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


is_authenticated = bool(st.session_state.get("auth_user"))
selected_domain = SUPPORTED_DOMAINS[0]

with st.sidebar:
    st.header("Create Account")
    with st.form("create_account_form", clear_on_submit=False):
        signup_name = st.text_input("Name")
        signup_email = st.text_input("Email")
        signup_password = st.text_input("Password", type="password")
        signup_password_confirm = st.text_input("Confirm Password", type="password")
        signup_submit = st.form_submit_button("Create Account")

    if signup_submit:
        if not signup_name.strip() or not signup_email.strip() or not signup_password:
            st.error("Name, email, and password are required.")
        elif signup_password != signup_password_confirm:
            st.error("Password and confirm password do not match.")
        elif len(signup_password) < 6:
            st.error("Password must be at least 6 characters.")
        else:
            auth_client = create_supabase_auth_client()
            try:
                if not auth_client:
                    st.error("Supabase credentials are missing in .env")
                else:
                    signup_res = auth_client.auth.sign_up({
                        "email": signup_email.strip(),
                        "password": signup_password,
                        "options": {
                            "data": {
                                "full_name": signup_name.strip()
                            }
                        }
                    })
                    created_user = user_to_dict(getattr(signup_res, "user", None))
                    if created_user:
                        st.session_state["auth_user"] = created_user
                    else:
                        # If provider doesn't return user/session here, try immediate login.
                        login_after_signup = auth_client.auth.sign_in_with_password({
                            "email": signup_email.strip(),
                            "password": signup_password,
                        })
                        logged_user = user_to_dict(getattr(login_after_signup, "user", None))
                        if logged_user:
                            st.session_state["auth_user"] = logged_user
                    st.success("Account created successfully.")
            except Exception as e:
                err = str(e)
                err_lower = err.lower()
                if "rate limit" in err_lower or "email rate limit exceeded" in err_lower:
                    st.warning("Signup rate limit reached. Trying login with the same email/password...")
                    try:
                        if auth_client:
                            login_after_limit = auth_client.auth.sign_in_with_password({
                                "email": signup_email.strip(),
                                "password": signup_password,
                            })
                            logged_user = user_to_dict(getattr(login_after_limit, "user", None))
                            if logged_user:
                                st.session_state["auth_user"] = logged_user
                                st.success("Logged in successfully. Startup form is now unlocked.")
                            else:
                                st.error("Rate limit hit and login did not succeed. Please use Login form or wait a few minutes.")
                        else:
                            st.error("Supabase credentials are missing in .env")
                    except Exception as login_err:
                        st.error(f"Signup rate-limited and login failed: {login_err}")
                else:
                    st.error(f"Account creation failed: {e}")

    st.markdown("---")
    st.header("Login")
    with st.form("login_form", clear_on_submit=False):
        login_email = st.text_input("Login Email")
        login_password = st.text_input("Login Password", type="password")
        login_submit = st.form_submit_button("Login")

    if login_submit:
        if not login_email.strip() or not login_password:
            st.error("Email and password are required.")
        else:
            try:
                auth_client = create_supabase_auth_client()
                if not auth_client:
                    st.error("Supabase credentials are missing in .env")
                else:
                    login_res = auth_client.auth.sign_in_with_password({
                        "email": login_email.strip(),
                        "password": login_password,
                    })
                    logged_user = user_to_dict(getattr(login_res, "user", None))
                    if logged_user:
                        st.session_state["auth_user"] = logged_user
                        st.success("Login successful.")
                    else:
                        st.error("Login failed. Please check credentials.")
            except Exception as e:
                st.error(f"Login failed: {e}")

    if st.button("Logout"):
        try:
            auth_client = create_supabase_auth_client()
            if auth_client:
                auth_client.auth.sign_out()
        except Exception:
            pass
        st.session_state.pop("auth_user", None)
        st.success("Logged out.")

    with st.expander("Current User Profile", expanded=False):
        current_user = st.session_state.get("auth_user")
        if not current_user:
            st.write("No user logged in.")
        else:
            st.write("ID:", current_user.get("id"))
            st.write("Email:", current_user.get("email"))
            full_name = (current_user.get("user_metadata") or {}).get("full_name")
            st.write("Name:", full_name or "N/A")
            st.write("Created At:", current_user.get("created_at"))

    st.markdown("---")
    st.header("Project Setup")
    if not is_authenticated:
        st.info("Please login or create an account to access startup form and report generation.")
    else:
        selected_domain = st.selectbox("Select startup domain", SUPPORTED_DOMAINS)
        st.write("Use this panel to drive the idea generation workflow.")
        st.markdown("---")
        st.subheader("Startup Form (MVP)")
        form_domain = st.selectbox("Domain (form)", SUPPORTED_DOMAINS, index=SUPPORTED_DOMAINS.index(selected_domain))
        problem_statement = st.text_area("Problem Statement", height=80)
        target_audience = st.text_input("Target Audience")
        country_region = st.text_input("Country / Region")
        budget = st.text_input("Budget")
        business_stage = st.selectbox("Business Stage", ["Idea", "MVP", "Existing Startup"])
        additional = st.text_area("Additional Requirements (mobile app, multilingual, etc.)", height=80)
        if st.button("Generate Startup Report (MVP)"):
            # prepare inputs
            domain_key = display_to_folder.get(form_domain, form_domain.lower().replace(" ", "_"))
            inputs = {
                "domain": form_domain,
                "domain_key": domain_key,
                "problem_statement": problem_statement,
                "target_audience": target_audience,
                "country_region": country_region,
                "budget": budget,
                "business_stage": business_stage,
                "additional_requirements": additional,
                # also provide a retriever query field
                "retriever_query": problem_statement,
            }
            with st.spinner("Running orchestrator..."):
                try:
                    report = orchestrate_startup(inputs)
                    st.session_state['last_report'] = report
                    st.success("Report generated — see Preview")
                except Exception as e:
                    st.error(f"Orchestration failed: {e}")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Input")
    startup_goal = st.text_area(
        "Describe what you want to build",
        placeholder="Example: A Healthcare AI startup for patient triage",
        height=140,
        disabled=not is_authenticated,
    )
    run_workflow = st.button("Generate Startup Report", type="primary", disabled=not is_authenticated)
    if not is_authenticated:
        st.info("Login required to generate reports.")

with col2:
    st.subheader("Output Preview")
    if run_workflow and is_authenticated:
        st.info(f"Selected domain: {selected_domain}")
        st.success("Workflow scaffold is ready. Next step: connect LangGraph nodes and RAG retrieval.")
        st.write(startup_goal or "No description provided.")
    else:
        st.write("Your final report will appear here after connecting the workflow.")

    # Show last generated report if exists
    if 'last_report' in st.session_state:
        report = st.session_state['last_report']
        with st.expander('Last Generated Report', expanded=True):
            st.subheader("1. Startup Overview")
            idea = report.get('idea', {})
            st.write(f"**Startup Name:** {idea.get('startup_name')}")
            st.write(f"**Tagline:** {idea.get('tagline')}")
            st.write(f"**Domain:** {report.get('metadata',{}).get('input',{}).get('domain')}")
            st.write(f"**Target Audience:** {report.get('metadata',{}).get('input',{}).get('target_audience')}")

            st.markdown('---')
            st.subheader("2. Problem Statement")
            st.write(report.get('metadata',{}).get('input',{}).get('problem_statement'))

            st.markdown('---')
            st.subheader("3. Proposed Solution")
            st.write(idea.get('core_idea'))

            st.markdown('---')
            st.subheader("4. Market Research (RAG)")
            st.write(report.get('market_research', {}).get('summary'))

            st.markdown('---')
            st.subheader("5. Competitor Analysis")
            comps = report.get('competitor_analysis', {}).get('competitors', [])
            if comps:
                for c in comps:
                    st.write(f"- **{c.get('name')}** — Strengths: {c.get('strengths')}; Weaknesses: {c.get('weaknesses')}")
            else:
                st.write("No competitors found in knowledge base sample.")

            st.markdown('---')
            st.subheader("6. Business Model")
            bm = report.get('business_model', {})
            st.write(f"**Revenue model:** {bm.get('revenue_model')}")
            st.write(f"**Pricing:** {bm.get('pricing')}")

            st.markdown('---')
            st.subheader("7. MVP Features")
            for f in report.get('mvp_features', []):
                st.write(f"- {f}")

            st.markdown('---')
            st.subheader("8. SWOT Analysis")
            sw = report.get('swot_analysis') or report.get('swot', {})
            st.write(f"**Strengths:** {sw.get('strengths')}")
            st.write(f"**Weaknesses:** {sw.get('weaknesses')}")
            st.write(f"**Opportunities:** {sw.get('opportunities')}")
            st.write(f"**Threats:** {sw.get('threats')}")

            st.markdown('---')
            st.subheader("9. Validation Score")
            val = report.get('validation', {})
            scores = val.get('scores', {})
            if not scores:
                scores = {k: val.get(k) for k in ('innovation', 'market_demand', 'feasibility', 'scalability') if val.get(k) is not None}
            for k, v in scores.items():
                st.write(f"{k.capitalize()}: {v}/10")
            st.write(f"**Overall Score:** {val.get('overall')}/10")

            st.markdown('---')
            st.subheader("10. Implementation Roadmap")
            roadmap = report.get('implementation_roadmap', {})
            for k, v in roadmap.items():
                st.write(f"**{k}**: {v}")

            st.markdown('---')
            st.subheader("11. Estimated Budget")
            for k, v in report.get('estimated_budget', {}).items():
                st.write(f"{k.capitalize()}: {v}")

            st.markdown('---')
            st.subheader("12. Future Enhancements")
            for e in report.get('future_enhancements', []):
                st.write(f"- {e}")

            st.markdown('---')
            st.subheader("13. Retrieved Sources (RAG)")
            for s in report.get('retrieved_sources', [])[:10]:
                st.write(f"- {s}")

            import json
            st.download_button("Download report (JSON)", json.dumps(report, indent=2), file_name="startup_report.json")

    st.markdown("---")
    st.subheader("Retrieve Context from Knowledge Base")
    query = st.text_input("Retriever query", "patient triage automation in hospitals")
    top_k = st.slider("Top K", 1, 10, 5)
    retrieval_mode = st.radio("Retrieval mode", ["auto", "rpc", "local"], index=0, help="auto=RPC then fallback; rpc=RPC only; local=local chunk similarity only")
    if st.button("Retrieve Context", disabled=not is_authenticated):
        # normalize selected domain to folder key (use explicit mapping first)
        domain_key = display_to_folder.get(selected_domain, selected_domain.lower().replace(" ", "_"))
        with st.spinner("Retrieving..."):
            try:
                results = query_supabase(query, domain=domain_key, top_k=top_k, mode=retrieval_mode)
            except Exception as e:
                import traceback
                st.error(f"Retrieval failed: {e}")
                st.text(traceback.format_exc())
                results = []

            # Also perform a direct raw RPC call here and show the raw response
            try:
                if retrieval_mode in ("rpc", "auto"):
                    from supabase import create_client
                    from dotenv import load_dotenv
                    # use the deterministic embedding from our ingest helper
                    from src.rag.ingest import deterministic_embedding

                    load_dotenv()
                    SUPABASE_URL = os.getenv('SUPABASE_URL')
                    SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')
                    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
                    emb = deterministic_embedding(query)
                    # run rpc and show raw result for debug
                    raw = client.rpc('match_startup_knowledge', {"query_embedding": emb, "query_domain": domain_key, "match_count": top_k}).execute()
                else:
                    raw = None
            except Exception as e:
                raw = e

        # show results count for debugging
        try:
            results_count = len(results) if results is not None else 0
        except Exception:
            results_count = 0
        st.write(f"Results returned (count): {results_count}")
        if not results:
            st.write("No results found.")
        else:
            # show a small sample of normalized results for debug
            try:
                st.write('Sample results:', [r[1].get('source') for r in results[:3]])
            except Exception:
                st.write('Sample results: (could not read)')
            for score, row in results:
                with st.expander(f"Source: {row.get('source')} — score: {score}"):
                    st.write(row.get("text")[:1000])

        # show raw RPC result if available
        if 'raw' in locals():
            with st.expander('Raw RPC response (debug)'):
                # if it's an exception, show traceback string
                try:
                    st.write(raw)
                except Exception:
                    st.text(str(raw))

    # Debug panel
    with st.expander("Debug: retrieval info", expanded=False):
        domain_key = display_to_folder.get(selected_domain, selected_domain.lower().replace(" ", "_"))
        st.write("Normalized domain key:", domain_key)
        # show how many chunk files exist for this domain
        from pathlib import Path
        chunk_files = list(Path("data/chunks").glob(f"{domain_key}__*.jsonl"))
        st.write("Chunk files found:", len(chunk_files))
        if chunk_files:
            st.write([str(p.name) for p in chunk_files])
        # Show whether Supabase env vars are present in this process
        sup_url = os.getenv('SUPABASE_URL')
        sup_key = os.getenv('SUPABASE_ANON_KEY')
        sup_service = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        st.write('Supabase URL set:', bool(sup_url))
        st.write('Supabase ANON key set:', bool(sup_key))
        st.write('Supabase SERVICE key set:', bool(sup_service))
        if 'results' in locals():
            st.write("Results returned:", len(results) if results else 0)
