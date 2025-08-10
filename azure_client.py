# azure_client.py

import os
import logging
from typing import Optional, List, Dict

# Azure specific imports
from azure.identity import ClientSecretCredential
from azure.core.exceptions import ClientAuthenticationError, HttpResponseError, ResourceNotFoundError
from azure.ai.projects import AIProjectClient

# Initialize logger
logger = logging.getLogger(__name__)

# --- AZURE CREDENTIALS AND CLIENT INITIALIZATION ---
def get_azure_credential() -> ClientSecretCredential:
    """
    Creates Azure credentials using client secret from environment variables.
    These should be set by the Streamlit app from secrets.toml.
    """
    try:
        credential = ClientSecretCredential(
            tenant_id=os.environ["AZURE_TENANT_ID"],
            client_id=os.environ["AZURE_CLIENT_ID"],
            client_secret=os.environ["AZURE_CLIENT_SECRET"],
        )
        # Test the credential
        token = credential.get_token("https://ai.azure.com/.default")
        logger.info("Azure credentials validated successfully")
        return credential
    except KeyError as key_err:
        logger.error(f"Missing required environment variable: {key_err}")
        raise KeyError(f"Missing required environment variable: {key_err}") from key_err
    except Exception as e:
        logger.error(f"Failed to create Azure credentials: {e}")
        raise RuntimeError(f"Azure credential initialization failed: {e}")

def create_project_client() -> AIProjectClient:
    """
    Constructs an AIProjectClient using environment variables.
    """
    try:
        # Use the project endpoint from your secrets
        project_endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
        subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
        resource_group = os.environ["AZURE_RESOURCE_GROUP_NAME"]
        project_name = os.environ["AZURE_AI_PROJECT_NAME"]
        credential = get_azure_credential()
        
        client = AIProjectClient(
            endpoint=project_endpoint,
            credential=credential,
            subscription_id=subscription_id,
            resource_group_name=resource_group,
            project_name=project_name,
        )
        logger.info("AIProjectClient initialized successfully")
        return client
    except KeyError as key_err:
        logger.error(f"Missing required environment variable: {key_err}")
        raise KeyError(f"Missing required environment variable: {key_err}") from key_err
    except Exception as ex:
        logger.error(f"Failed to initialize AIProjectClient: {ex}")
        raise RuntimeError(f"Failed to initialize AIProjectClient: {ex}") from ex

# Initialize global clients - use lazy initialization
PROJECT_CLIENT = None

def get_or_create_project_client() -> AIProjectClient:
    """
    Gets the global PROJECT_CLIENT or creates it if not initialized.
    """
    global PROJECT_CLIENT
    if PROJECT_CLIENT is None:
        PROJECT_CLIENT = create_project_client()
    return PROJECT_CLIENT

def list_available_agents(limit: int = 100) -> List[Dict[str, str]]:
    """
    Returns a list of dicts with 'id' and 'name' for all agents in the project.
    """
    try:
        project_client = get_or_create_project_client()
        agents_client = project_client.agents
        agents = agents_client.list_agents(limit=limit)
        return [{"id": ag.id, "name": ag.name} for ag in agents]
    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        raise RuntimeError(f"Failed to list agents: {e}")
