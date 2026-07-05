# ⚡ StartupSpark AI – Multi-Agent Startup Strategy Engine ⚡

<p align="center">
  <img src="https://readme-typing-svg.herokuapp.com?font=Fira+Code&weight=500&size=28&pause=1000&color=ADC6FF&center=true&vCenter=true&width=900&lines=StartupSpark+AI+-+Idea+to+Blueprint+in+Minutes;RAG-Powered+%7C+Multi-Agent+%7C+Founder-Ready+Reports" alt="Typing Animation"/>
</p>

---

## 🚀 About the Project

**StartupSpark AI** is a Streamlit-powered platform that turns a raw startup idea into a complete, founder-ready strategy blueprint. It combines Retrieval-Augmented Generation (RAG) over a domain-specific knowledge base with LLM reasoning (Gemini / OpenAI) to generate market research, competitor analysis, business models, SWOT, validation scoring, roadmaps, and budgets — all in one click.

### 🌟 Key Highlights:
- **RAG-Grounded Intelligence:** Retrieves domain-specific context from Supabase before generating any report.
- **Multi-Domain Coverage:** Healthcare AI, FinTech, EdTech, AgriTech, and Cybersecurity knowledge bases.
- **End-to-End Report:** Overview, problem/solution, market, competitors, business model, MVP, SWOT, validation score, roadmap, budget, and future enhancements.
- **Export Anywhere:** One-click PDF and JSON export of every generated report.
- **Persistent History:** Reports are saved per-user in Supabase (with local fallback) so you can revisit past strategies anytime.
- **Sleek Dark UI:** Fully custom "glassmorphism" dashboard built entirely with Streamlit + custom CSS.

---

## 🛠️ Tech Stack

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" />
  <img src="https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white" />
  <img src="https://img.shields.io/badge/Gemini-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white" />
  <img src="https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white" />
  <img src="https://img.shields.io/badge/Supabase-3FCF8E?style=for-the-badge&logo=supabase&logoColor=white" />
  <img src="https://img.shields.io/badge/RAG-2563EB?style=for-the-badge&logo=databricks&logoColor=white" />
  <img src="https://img.shields.io/badge/dotenv-ECD53F?style=for-the-badge&logo=dotenv&logoColor=black" />
</p>

---

## ⚡ Features

### 🧠 AI Strategy Engine
- **RAG Retrieval:** Pulls domain-specific evidence from Supabase before generating a report, with automatic web-search fallback when the knowledge base is thin.
- **Multi-Provider LLM:** Prefers Gemini, falls back to OpenAI, with clear console logging if either provider fails.
- **Structured JSON Output:** Every report follows a strict schema — idea, market research, competitors, business model, SWOT, validation, MVP features, roadmap, budget, and future enhancements.
- **No Hardcoded Fallbacks:** If retrieval or generation genuinely fails, the app tells you exactly why instead of silently faking a report.

### 📊 Founder Dashboard
- **Requirement Forge:** A guided form to capture domain, problem statement, audience, region, budget, and stage.
- **Bento-Grid Report View:** A polished, section-by-section breakdown of the generated strategy.
- **Validation Scorecard:** Visual scoring for innovation, market demand, feasibility, and an overall "Spark Score."
- **Roadmap Timeline & Budget Breakdown:** Phase-by-phase implementation plan with a visual budget allocation.
- **Report Archive:** Revisit, reopen, download, or delete any previously generated report.

### 🔐 Auth & Storage
- **Supabase Auth:** Email/password login and signup.
- **Per-User Report History:** Stored in Supabase with a local JSON fallback if the table isn't set up yet.
- **Secure Export:** Download any report as a styled PDF or raw JSON.

---

## ⚙️ Setup & Installation

### 🔹 Prerequisites
- **Python 3.10+**
- **Supabase Project** (Auth + a `startup_reports` table — see `sql/supabase_startup_reports.sql`)
- **Gemini API Key** (via [Google AI Studio](https://aistudio.google.com/apikey)) and/or **OpenAI API Key**

### 🔹 Steps to Run Locally

1. **Clone the Project**
   ```bash
   git clone https://github.com/your-username/StartupSpark-AI.git
   cd StartupSpark-AI
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**
   Create a `.env` file in the project root:
   ```dotenv
   GOOGLE_API_KEY=your_gemini_api_key
   GEMINI_MODEL=gemini-2.5-flash
   OPENAI_API_KEY=your_openai_api_key
   OPENAI_MODEL=gpt-4o-mini

   SUPABASE_URL=your_supabase_url
   SUPABASE_ANON_KEY=your_supabase_anon_key
   SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
   SUPABASE_BUCKET_NAME=your_bucket_name

   ENABLE_EXTERNAL_SEARCH=1
   ```
   > ⚠️ Never commit your `.env` file or share your service-role key — it bypasses all Supabase row-level security.

4. **Set Up Supabase**
   - Enable Email Auth in your Supabase project.
   - Run `sql/supabase_startup_reports.sql` in the Supabase SQL editor to create the reports table.

5. **Run the App**
   ```bash
   streamlit run app.py
   ```

---

## 🤖 Agents & Workflow

StartupSpark AI works like a virtual founder team. A single orchestration pipeline (`orchestrate_startup` → `generate_llm_report`) coordinates a **Retrieval Agent** and nine **specialist reasoning agents**, each responsible for one section of the final report. They run as one grounded, structured LLM pass — not isolated processes — so every section stays consistent with the same retrieved evidence and user inputs.

### 🔎 Retrieval Agent
- **Role:** Gathers evidence before any reasoning happens.
- **How it works:** Queries the Supabase knowledge base (`query_supabase`) scoped to the selected domain (Healthcare AI, FinTech, EdTech, AgriTech, Cybersecurity).
- **Fallback:** If retrieved context is too thin (< 350 characters), it automatically supplements with a live DuckDuckGo web search (`external_web_context`) so the report is never generated from an empty knowledge base.
- **Output:** A deduplicated set of source excerpts passed to every downstream agent as shared context.

### 💡 Idea Agent
Crafts a distinctive `startup_name`, tagline, core idea, and the specific AI/RAG/automation approach — explicitly instructed to avoid generic "Domain + AI" naming patterns.

### 📈 Market Research Agent
Produces a grounded market summary, key trends, and TAM/CAGR estimates (reasoned from retrieved evidence where available), plus evidence notes citing the source material.

### 🥊 Competitor Analysis Agent
Identifies direct, indirect, or adjacent competitors relevant to the user's problem and region, each with a specific strength and weakness — normalized on the frontend to handle either a list or object response shape.

### 💰 Business Model Agent
Defines the revenue model, pricing strategy, and target buyer/user segments, calibrated to the user's stated budget and business stage.

### ⚖️ SWOT Agent
Generates Strengths, Weaknesses, Opportunities, and Threats specific to the idea — not generic boilerplate — rendered as a four-quadrant grid in the report.

### ✅ Validation Agent
Scores the idea on Innovation, Market Demand, Feasibility, and Scalability, then computes an overall "Spark Score" with a short rationale.

### 🧩 MVP Agent
Breaks the idea down into concrete, buildable MVP features tailored to the stage (Idea / MVP / Growth).

### 🗺️ Roadmap Agent
Lays out a phased implementation plan (Phase 1 → Phase 4) with concrete milestones and timeframes, visualized as a timeline.

### 💼 Budget Agent
Allocates the user's available budget across categories, sized to fit what they specified — visualized with proportional bars and a total seed estimate.

### 🚀 Future Enhancements Agent
Suggests forward-looking features and expansion ideas beyond the initial MVP.

### 🔗 How It All Connects

```
User Input (Requirement Forge)
        │
        ▼
Retrieval Agent  ──►  Supabase RAG  ──►  Web Search Fallback (if thin)
        │
        ▼
Single structured LLM call (Gemini → OpenAI fallback)
   generates all 9 specialist sections as one JSON report
        │
        ▼
Report validated (required keys checked) → saved to Supabase/local history
        │
        ▼
Rendered as an interactive bento-grid report + exportable PDF/JSON
```

If the Retrieval Agent finds no usable context, or both LLM providers fail, the pipeline raises a clear error instead of silently generating a fake/hardcoded report — so you always know whether you're looking at a grounded result.

---

## 🌟 Support & Contribution

Loved this project? Give it a **⭐ Star** on GitHub to show your support! 🚀

<p align="center">
  <img src="https://readme-typing-svg.herokuapp.com?size=22&duration=3000&color=ADC6FF&center=true&vCenter=true&width=600&lines=Contributions+are+Welcome!;Star+the+Repo+if+you+like+it!" alt="Typing SVG">
</p>
