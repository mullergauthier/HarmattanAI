# HarmattanAI: AI Coding Agent Instructions

## Project Overview
- **Purpose:** Streamlit app for extracting/classifying ICD-10 codes from clinical notes using Azure AI Agents (via `azure-ai-projects`).
- **Architecture:**
  - `app.py`: Streamlit UI, user input, agent selection, and results display.
  - `backend.py`: Handles Azure AI Projects API, agent invocation, and response parsing.
  - `assets/`: Logos and static images.
  - `.streamlit/`: Theme config (`config.toml`), secrets (`secrets.toml`).

## Key Patterns & Workflows
- **Agent Selection:**
  - Agents are dynamically listed from Azure AI Projects (`list_available_agents`).
  - User selects agent in sidebar; agent ID is passed to backend for each request.
- **Secrets Management:**
  - All Azure credentials are loaded from `st.secrets.azure` and set as environment variables at runtime.
  - Never hardcode secrets; always use `os.environ[...]` for credentials in backend.
- **Backend Invocation:**
  - Use `get_agent_response_sync(note, provider, icd_website, language, agent_id)` for all agent calls.
  - Backend expects `agent_id` for each request; fallback to env var if not provided.
- **ICD-10 Source Selection:**
  - UI allows selection of official WHO ICD-10 URLs or custom URLs.
  - Language selection is passed to backend and used in agent prompt.
- **Validation Workflow:**
  - Results are displayed in a table with checkboxes for validation.
  - Validated codes can be reviewed in a dialog before export/integration.

## Development Workflows
- **Run app:** `streamlit run app.py`
- **Test components:** Import from `backend.py` or use scripts in `batch_processing/scripts/`
- **All tests in** `test/test_function.py` (no complex frameworks)
- **Update** `README.md` for new features and add a dated changelog entry
- **Ignore unnecessary files in** `.gitignore`
- **Use latest Azure SDKs and Python 3.12 features**
- **No Docker or containerization**

## Instructions

- Use existing code, SDKs, and functions where possible
- Write code and comments in English
- Keep documentation in `README.md` only
- Keep everything simple and avoid over-engineering

## Tech Stack

- **Python 3.12**
- **Streamlit** (UI)
- **Azure AI Projects SDK** (`azure-ai-projects`)
- **Azure AI Agents SDK** (`azure-ai-agents`)
- **Azure AI Inference SDK** (`azure-ai-inference`)
- **Azure Identity** (`azure-identity`)
- **python-dotenv** (env management)
- **openpyxl** (Excel)
- **PyMuPDF** (PDF)
- **aiofiles** (async I/O)

## Development Philosophy

- Rapid prototyping and experimentation are the main goals.
- Keep code simple, readable, and functional.
- Avoid over-engineering, complex error handling, or production-level reliability.
- Manual testing and print statements are sufficient for validation.

## Conventions & Integration
- **Azure AI Projects:**
  - All agent operations use `AIProjectClient` and its subclients (`threads`, `messages`, `runs`).
  - Use direct iteration for paged results (no `.data` attribute).
- **Error Handling:**
  - Errors are logged and surfaced in the UI with user-friendly messages.
  - Backend uses robust try/except blocks for all Azure calls.
- **Frontend/Backend Separation:**
  - UI logic is in `app.py`; all Azure logic is in `backend.py`.
  - Only import from `backend.py` in `app.py`.
- **Testing/Debugging:**
  - Use `streamlit run app.py` for local testing.
  - Debug logs are written to `debug.log` (excluded from git).
- **Deployment:**
  - Designed for Streamlit Cloud; secrets must be set in the cloud dashboard.
  - `.gitignore` excludes secrets, logs, cache, and virtualenvs.

## Examples
- **Agent Selection:**
  ```python
  available_agents = list_available_agents()
  selected_agent_id = ... # from UI
  response = get_agent_response_sync(..., selected_agent_id)
  ```
- **Secrets Loading:**
  ```python
  os.environ["AZURE_TENANT_ID"] = st.secrets.azure.AZURE_TENANT_ID
  ```
- **Paged Results:**
  ```python
  for msg in agents_client.messages.list(...):
      ...
  ```

## Key Files
- `app.py`: Main UI, agent selection, ICD-10 config, validation
- `backend.py`: Azure AI Projects integration, agent invocation
- `.streamlit/config.toml`: UI theme
- `.streamlit/secrets.toml`: Azure credentials (never commit)
- `requirements.txt`: Only Azure/Streamlit dependencies

---

**If anything is unclear or missing, ask for clarification or examples from the user before proceeding.**
