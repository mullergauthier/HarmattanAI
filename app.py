# app.py

import streamlit as st
import pandas as pd
import os
from backend import get_agent_response_sync, list_available_agents, logger # Import backend functions

# --- INITIALIZATION & CONFIGURATION ---
def load_secrets():
    """Loads secrets from Streamlit's secrets manager into environment variables."""
    try:
        # Load Azure secrets
        svc_azure = st.secrets.azure
        os.environ.update({
            "AZURE_TENANT_ID": svc_azure.AZURE_TENANT_ID,
            "AZURE_CLIENT_ID": svc_azure.AZURE_CLIENT_ID,
            "AZURE_CLIENT_SECRET": svc_azure.AZURE_CLIENT_SECRET,
            "AZURE_SUBSCRIPTION_ID": svc_azure.AZURE_SUBSCRIPTION_ID,
            "AZURE_RESOURCE_GROUP_NAME": svc_azure.AZURE_RESOURCE_GROUP_NAME,
            "AZURE_AI_PROJECT_NAME": svc_azure.AZURE_AI_PROJECT_NAME,
            "AZURE_AI_AGENT_AGENT": svc_azure.AZURE_AI_AGENT_AGENT,
            "AZURE_AI_PROJECT_ENDPOINT": svc_azure.AZURE_AI_PROJECT_ENDPOINT
        })
        logger.info("Azure secrets loaded.")
        
        st.session_state.secrets_loaded = True
        
    except Exception as e:
        st.error(f"Essential configuration is missing in Streamlit secrets: {e}")
        logger.error(f"Missing or invalid secrets: {e}")
        st.stop()

# Load secrets only once per session
if "secrets_loaded" not in st.session_state:
    load_secrets()


# --- UI HELPER FUNCTIONS ---
@st.dialog("Recap", width="large")
def show_validation_dialog(validated_data: list[dict], system_name: str):
    """Displays the validation recap dialog."""
    st.write(f"Codes selected for sending to **{system_name}**:")
    if validated_data:
        codes_to_display = [{'Code': row.get('code', 'N/A')} for row in validated_data]
        df = pd.DataFrame(codes_to_display)
        st.table(df)
        st.success("Data ready for transmission (implementation pending).")
    else:
        st.warning("No codes were selected for validation.")

# --- UI STYLING ---
st.markdown(
    """<style>
        div.stButton > button { background-color: #398980; color: #ffffff; border: none; padding: 0.5em 1em; border-radius: 5px; font-weight: bold; cursor: pointer; }
        div.stButton > button:hover { background-color: #2a6a60; }
    </style>""",
    unsafe_allow_html=True
)


# --- SIDEBAR ---
with st.sidebar:
    try:
        st.image("assets/logo_harmattan.png", width=250)
    except Exception:
        st.warning("Logo image not found.")

    # --- AGENT SELECTION ---
    col1, col2 = st.columns([3, 1])
    
    with col2:
        if st.button("🔄", help="Refresh agents list"):
            if "available_agents" in st.session_state:
                del st.session_state.available_agents
            st.rerun()
    
    try:
        # Load available agents from Azure
        if "available_agents" not in st.session_state:
            with st.spinner("Loading available agents..."):
                st.session_state.available_agents = list_available_agents()
        
        available_agents = st.session_state.available_agents
        
        if available_agents:
            # Create a dictionary mapping display names to agent IDs
            agent_options = {f"{agent['name']} ({agent['id'][:8]}...)": agent['id'] for agent in available_agents}
            
            with col1:
                selected_agent_display = st.selectbox(
                    "Select AI Agent:", 
                    list(agent_options.keys()), 
                    key="agent_selection"
                )
            selected_agent_id = agent_options[selected_agent_display]
        else:
            st.error("No agents found in the project.")
            selected_agent_id = None
            
    except Exception as e:
        st.error(f"Failed to load agents: {e}")
        # Fallback to environment variable
        selected_agent_id = None
        st.info("Using default agent from environment configuration.")
    
    system_selection = st.selectbox("Select Target System:", ["Hopital Management", "DEDALUS", "CEGEDIM"], key="system_selection")

    # --- ICD-10 Website and Language Selection ---
    icd_websites = {
        "ICD-10 2019 (EN)": "https://icd.who.int/browse10/2019/en",
        "ICD-10 2019 (FR)": "https://icd.who.int/browse10/2019/fr",
        "ICD-10 2025 (EN)": "https://icd.who.int/browse/2025-01/mms/en",
        "ICD-10 2025 (FR)": "https://icd.who.int/browse/2025-01/mms/fr"
    }
    icd_website_label = st.selectbox(
        "Select ICD-10 Website:",
        list(icd_websites.keys()),
        key="icd_website_selection",
        index=0
    )
    icd_website = icd_websites[icd_website_label]

    # Allow user to add a custom ICD-10 website
    custom_icd_url = st.text_input("Or enter a custom ICD-10 website URL:", key="custom_icd_url")
    if custom_icd_url.strip():
        icd_website = custom_icd_url.strip()

    language_options = ["en", "fr"]
    language = st.selectbox("Select Language:", language_options, key="language_selection", index=0)

    if st.user.is_logged_in:
        with st.expander(f"👤 User: {st.user.name}"):
            st.write(f"**Email:** {st.user.email}")
            if st.button("Logout"):
                st.logout()
    else:
        st.button("Login", on_click=st.login("auth0"))
    
    st.markdown("---")
    st.info("Harmattan AI Assistant v2.0")

# --- MAIN APPLICATION AREA ---
if "agent_response_data" not in st.session_state:
    st.session_state.agent_response_data = None
if "validation_states" not in st.session_state:
    st.session_state.validation_states = {}

try:
    st.image("assets/logo_harmattan.png", width=500)
except Exception:
    st.warning("Main logo image not found.")

st.header("AI Medical Code Assistant")
st.markdown("Paste the doctor's notes below and click 'Analyze Notes' to get suggested codes.")

doctor_notes = st.text_area("Doctor's Notes:", height=200, key="doctor_notes_input", placeholder="Enter clinical notes here...")

if st.button("Analyze Notes", type="primary", disabled=not st.user.is_logged_in):
    if not doctor_notes.strip():
        st.warning("Please paste the doctor's notes into the text area before analyzing.")
    else:
        # Get the selected agent name for display
        agent_display_name = "Azure AI Agent"
        if "available_agents" in st.session_state and st.session_state.available_agents:
            try:
                for agent in st.session_state.available_agents:
                    if agent['id'] == selected_agent_id:
                        agent_display_name = agent['name']
                        break
            except:
                pass
                
        with st.spinner(f"Sending request to {agent_display_name}... Please wait."):
            try:
                # Call the backend to get data with selected agent
                response_data = get_agent_response_sync(
                    doctor_notes, 
                    "Azure",  # Provider is always Azure now
                    icd_website, 
                    language,
                    selected_agent_id  # Pass the selected agent ID
                )
                st.session_state.agent_response_data = response_data
                st.session_state.validation_states = {} # Reset validation on new data
                if response_data:
                    st.success(f"Analysis complete. Found {len(response_data)} potential codes.")
                else:
                    st.info("The analysis did not return any specific codes for the provided notes.")
            except Exception as e:
                # Catch errors from the backend and display them nicely
                st.error(f"An error occurred: {e}")
                st.session_state.agent_response_data = None
                logger.error(f"UI caught an exception from backend: {e}")

if not st.user.is_logged_in:
    st.warning("Please log in using the sidebar to use the analysis feature.")

# --- DISPLAY RESULTS AND VALIDATION FORM ---
st.markdown("---")
st.subheader("Analysis Results")

if st.session_state.agent_response_data:
    results = st.session_state.agent_response_data
    df_resp = pd.DataFrame(results)

    with st.form(key="validation_form"):
        cols_header = st.columns([4, 3, 2, 1, 1.2])
        cols_header[0].markdown("**Excerpt**")
        cols_header[1].markdown("**Description**")
        cols_header[2].markdown("**Code**")
        cols_header[3].markdown("**Link**")
        cols_header[4].markdown("**Validate**")
        st.markdown("---")

        for idx, row in df_resp.iterrows():
            cols = st.columns([4.5,4,1.5,1.5,1])
            cols[0].text(row.get('extract', 'N/A'))
            cols[1].text(row.get('description', 'N/A'))
            cols[2].text(row.get('code', 'N/A'))
            
            url = row.get('url')
            if url and isinstance(url, str):
                cols[3].link_button("Link", url)
            else:
                cols[3].text("-")
            
            validation_key = f"validate_{idx}"
            is_validated = cols[4].checkbox("validation", key=validation_key, label_visibility="hidden")
            st.session_state.validation_states[validation_key] = is_validated
        
        if st.form_submit_button("Save Validated Codes"):
            validated_rows_data = [
                row.to_dict() for i, row in df_resp.iterrows()
                if st.session_state.validation_states.get(f"validate_{i}")
            ]
            show_validation_dialog(validated_data=validated_rows_data, system_name=system_selection)