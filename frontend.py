import json
import os

import streamlit as st
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
                max-width: 1180px;
                padding: 1.25rem 1.25rem 3rem;
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
                font-size: .78rem;
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
                min-height: 620px;
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
                font-size: clamp(2rem, 4vw, 3.25rem);
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

            .auth-title {
                text-align: center;
                margin: 2rem 0 .7rem;
                font-size: clamp(2.2rem, 7vw, 4rem);
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
                grid-template-columns: 1fr 1fr;
                gap: .5rem;
                padding: .45rem;
                border: 1px solid rgba(173, 198, 255, .14);
                border-radius: 1rem;
                background: rgba(19, 27, 46, .9);
                max-width: 360px;
                margin: 0 auto;
            }

            .stRadio [role="radio"] {
                justify-content: center;
                min-height: 3.25rem;
                border-radius: .8rem;
                color: #d8e2ff !important;
                font-family: Sora, sans-serif;
                font-size: 1.05rem;
                font-weight: 800;
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

            @media (max-width: 760px) {
                .navlinks { display: none; }
                .trait-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                .footerline { flex-direction: column; text-align: center; }
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
    if st.button("←", key="auth_back", help="Back to landing"):
        set_page("landing")
        st.rerun()

    left, center, right = st.columns([0.28, 0.44, 0.28])
    with center:
        st.markdown(
            '<div class="auth-brand-large"><span class="bolt">S</span><span>StartupSpark AI</span></div>',
            unsafe_allow_html=True,
        )
        
        selected_mode = st.radio(
            "Authentication mode",
            ["Login", "Sign Up"],
            index=1 if st.session_state.get("auth_mode") == "signup" else 0,
            horizontal=True,
            label_visibility="collapsed",
        )
        st.session_state["auth_mode"] = "signup" if selected_mode == "Sign Up" else "login"

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

        st.markdown(
            """
            <div style="display:flex;align-items:center;gap:1rem;margin:1.5rem 0;color:#aeb7cd;">
                <div style="height:1px;background:rgba(173,198,255,.16);flex:1;"></div>
                <span>Or continue with</span>
                <div style="height:1px;background:rgba(173,198,255,.16);flex:1;"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        social_a, social_b = st.columns(2)
        with social_a:
            if st.button("Google", use_container_width=True):
                try:
                    auth_client = create_supabase_auth_client()
                    if not auth_client:
                        st.error("Supabase credentials are missing in .env")
                    else:
                        oauth_res = auth_client.auth.sign_in_with_oauth(
                            {
                                "provider": "google",
                                "options": {"redirect_to": "http://localhost:8501"},
                            }
                        )
                        oauth_url = getattr(oauth_res, "url", None)
                        if not oauth_url and isinstance(oauth_res, dict):
                            oauth_url = oauth_res.get("url")
                        if oauth_url:
                            st.link_button("Continue with Google", oauth_url, use_container_width=True)
                        else:
                            st.info("Google OAuth request started. Complete it in the browser if Supabase opens the provider page.")
                except Exception as exc:
                    st.error(f"Google login failed: {exc}")
        with social_b:
            st.button("GitHub", use_container_width=True, disabled=True)


def dashboard_page():
    topbar(show_auth=False)
    user = st.session_state.get("auth_user") or {}
    name = (user.get("user_metadata") or {}).get("full_name") or user.get("email") or "Founder"
    left, right = st.columns([0.72, 0.28])
    with left:
        st.markdown(
            f"""
            <div class="eyebrow">Command Center</div>
            <h1 class="hero-title" style="text-align:left;font-size:clamp(2rem,4vw,3.8rem);margin-left:0;">
                Build the next startup blueprint, <span class="gradient-text">{name}</span>
            </h1>
            """,
            unsafe_allow_html=True,
        )
    with right:
        if st.button("Logout", use_container_width=True):
            try:
                auth_client = create_supabase_auth_client()
                if auth_client:
                    auth_client.auth.sign_out()
            except Exception:
                pass
            st.session_state.pop("auth_user", None)
            set_page("landing")
            st.rerun()

    with st.form("startup_report_form"):
        c1, c2 = st.columns(2)
        with c1:
            domain = st.selectbox("Startup Domain", SUPPORTED_DOMAINS)
            target_audience = st.text_input("Target Audience", placeholder="Example: small clinic owners")
            country_region = st.text_input("Country / Region", placeholder="Example: Pakistan, GCC, USA")
            budget = st.text_input("Budget", placeholder="Example: 10000")
        with c2:
            business_stage = st.selectbox("Business Stage", ["Idea", "MVP", "Existing Startup"])
            problem_statement = st.text_area(
                "Problem Statement",
                height=148,
                placeholder="Describe the customer pain, workflow gap, or market problem.",
            )
            additional = st.text_area(
                "Additional Requirements",
                height=100,
                placeholder="Mobile app, multilingual, WhatsApp alerts, analytics, etc.",
            )
        submitted = st.form_submit_button("Generate Startup Report", type="primary", use_container_width=True)

    if submitted:
        inputs = {
            "domain": domain,
            "domain_key": DISPLAY_TO_FOLDER.get(domain, domain.lower().replace(" ", "_")),
            "problem_statement": problem_statement,
            "target_audience": target_audience,
            "country_region": country_region,
            "budget": budget,
            "business_stage": business_stage,
            "additional_requirements": additional,
            "retriever_query": problem_statement,
        }
        with st.spinner("Running multi-agent startup analysis..."):
            try:
                st.session_state["last_report"] = orchestrate_startup(inputs)
                st.success("Report generated.")
            except Exception as exc:
                st.error(f"Orchestration failed: {exc}")

    report = st.session_state.get("last_report")
    if report:
        render_report(report)

    with st.expander("Knowledge Base Retrieval"):
        query = st.text_input("Retriever Query", "patient triage automation in hospitals")
        top_k = st.slider("Top K", 1, 10, 5)
        mode = st.radio("Retrieval Mode", ["auto", "rpc", "local"], horizontal=True)
        domain_key = DISPLAY_TO_FOLDER.get(SUPPORTED_DOMAINS[0], "healthcare_ai")
        if st.button("Retrieve Context"):
            with st.spinner("Retrieving context..."):
                results = query_supabase(query, domain=domain_key, top_k=top_k, mode=mode)
            st.write(f"Results returned: {len(results) if results else 0}")
            for score, row in results or []:
                with st.expander(f"{row.get('source') or row.get('title')} | score: {score}"):
                    st.write((row.get("text") or "")[:1000])


def render_report(report):
    idea = report.get("idea") or {}
    validation = report.get("validation") or {}
    market = report.get("market_research") or {}
    business = report.get("business_model") or {}

    st.markdown('<h2 class="section-title">Generated Startup Blueprint</h2>', unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3)
    m1.metric("Startup", idea.get("startup_name") or "Generated Idea")
    m2.metric("Validation", f"{validation.get('overall', 'N/A')}/10")
    m3.metric("Revenue Model", business.get("revenue_model") or "TBD")

    overview, market_tab, roadmap, export = st.tabs(["Overview", "Market", "Roadmap", "Export"])
    with overview:
        st.subheader(idea.get("startup_name") or "Startup Overview")
        st.write(idea.get("tagline") or "")
        st.write(idea.get("core_idea") or "")
        st.markdown("**AI Solution**")
        st.write(idea.get("ai_solution") or "")
        st.markdown("**MVP Features**")
        for feature in report.get("mvp_features", []):
            st.write(f"- {feature}")

    with market_tab:
        st.markdown("**Market Research**")
        st.write(market.get("summary") or "No market summary available.")
        st.markdown("**Competitor Analysis**")
        competitors = (report.get("competitor_analysis") or {}).get("competitors", [])
        if competitors:
            for competitor in competitors:
                st.write(
                    f"- **{competitor.get('name')}** | Strengths: {competitor.get('strengths')} | "
                    f"Weaknesses: {competitor.get('weaknesses')}"
                )
        else:
            st.write("No competitors found in current knowledge base sample.")

    with roadmap:
        st.markdown("**Implementation Roadmap**")
        for phase, detail in (report.get("implementation_roadmap") or {}).items():
            st.write(f"- **{phase.replace('_', ' ').title()}**: {detail}")
        st.markdown("**Estimated Budget**")
        for key, value in (report.get("estimated_budget") or {}).items():
            st.write(f"- **{key.title()}**: {value}")
        st.markdown("**Future Enhancements**")
        for enhancement in report.get("future_enhancements", []):
            st.write(f"- {enhancement}")

    with export:
        st.download_button(
            "Download Report JSON",
            json.dumps(report, indent=2),
            file_name="startup_report.json",
            mime="application/json",
            use_container_width=True,
        )
        st.markdown("**Retrieved Sources**")
        for source in report.get("retrieved_sources", [])[:10]:
            st.write(f"- {source}")


def main():
    st.set_page_config(page_title=PROJECT_TITLE, page_icon="⚡", layout="wide")
    inject_styles()
    st.session_state.setdefault("page", "landing")
    st.session_state.setdefault("auth_mode", "login")
    query_page = st.query_params.get("page")
    query_mode = st.query_params.get("mode")
    if query_page == "auth":
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
