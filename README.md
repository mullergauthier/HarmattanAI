# Harmattan AI - Medical Code Assistant

A Streamlit application for extracting and classifying ICD-10 codes from doctor's notes using Azure AI Agents.

## Features

- **ICD-10 Code Extraction**: Automatically extracts relevant medical codes from clinical notes
- **Multi-Agent Support**: Select from available Azure AI agents for specialized analysis
- **Multi-Language Support**: English and French language options
- **Flexible ICD-10 Sources**: Support for multiple WHO website versions + custom URLs
- **Interactive Validation**: UI for reviewing and validating extracted codes
- **Azure-Native**: 100% Azure infrastructure with Azure AI Projects integration

## Architecture

- **Frontend**: Streamlit web application
- **Backend**: Azure AI Projects with AI Agents
- **Authentication**: Azure Client Secret Credential
- **Deployment**: Streamlit Cloud

## Setup

### Requirements

- Python 3.9+
- Azure AI Project with deployed agents
- Azure credentials (tenant ID, client ID, client secret)

### Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd HarmattanAI
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure secrets in `.streamlit/secrets.toml`:
```toml
[azure]
AZURE_TENANT_ID = "your-tenant-id"
AZURE_CLIENT_ID = "your-client-id" 
AZURE_CLIENT_SECRET = "your-client-secret"
AZURE_SUBSCRIPTION_ID = "your-subscription-id"
AZURE_RESOURCE_GROUP_NAME = "your-resource-group"
AZURE_AI_PROJECT_NAME = "your-project-name"
AZURE_AI_AGENT_AGENT = "your-default-agent-id"
AZURE_AI_PROJECT_ENDPOINT = "your-project-endpoint"
```

4. Run the application:
```bash
streamlit run app.py
```

## Usage

1. **Login**: Use the sidebar to authenticate
2. **Select Agent**: Choose from available Azure AI agents
3. **Configure**: Set ICD-10 website and language preferences
4. **Analyze**: Paste doctor's notes and click "Analyze Notes"
5. **Validate**: Review and select relevant codes
6. **Export**: Save validated codes for integration with medical systems

## Deployment

This application is designed for deployment on Streamlit Cloud:

1. Push code to GitHub repository
2. Connect repository to Streamlit Cloud
3. Configure secrets in Streamlit Cloud dashboard
4. Deploy the application

## License

© 2025 Harmattan AI. All rights reserved.
