# StartupSpark AI

Multi-agent startup idea generator using RAG, LangChain, LangGraph, Gemini, and Supabase.

## Project Structure

```text
StartupSpark Ai/
	app.py
	requirements.txt
	.env.example
	data/
		raw_pdfs/
		processed/
		chunks/
	reports/
	src/
		config.py
		rag/
		agents/
		workflow/
		utils/
```

## Setup

1. Create and activate a virtual environment.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

2. Install dependencies.

```powershell
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill in your keys.

Required variables:

```env
GOOGLE_API_KEY=your_google_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
SUPABASE_BUCKET_NAME=startupspark-docs
```

4. Run the app.

```powershell
streamlit run app.py
```

## What is already scaffolded

- Streamlit entrypoint in `app.py`
- Shared config in `src/config.py`
- Placeholder agents in `src/agents/`
- Workflow stub in `src/workflow/graph.py`
- RAG helper stubs in `src/rag/`
- Report saving utility in `src/utils/report.py`

## Next implementation steps

1. Load PDFs from `data/raw_pdfs/`
2. Split documents into chunks
3. Create embeddings and store them in Supabase
4. Connect LangGraph nodes to the four agents
5. Replace placeholder logic with Gemini powered prompts

