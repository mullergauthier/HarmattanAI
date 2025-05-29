# backend.py

import os
import asyncio
import logging
import json
import re
import httpx
import certifi

# Azure specific imports
from azure.identity import ClientSecretCredential
from azure.identity.aio import ClientSecretCredential as AsyncClientSecretCredential
from azure.core.exceptions import ClientAuthenticationError, HttpResponseError, ResourceNotFoundError
from semantic_kernel.agents import AzureAIAgent, AzureAIAgentSettings
from azure.ai.projects import AIProjectClient

# OpenAI specific imports
from openai import OpenAI

# OpenTelemetry specific imports
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from azure.monitor.opentelemetry import configure_azure_monitor

# --- LOGGING CONFIGURATION ---
def setup_logging():
    """Configures the application logger."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filename="debug.log",
        filemode="w",
    )
    logger = logging.getLogger(__name__)
    # Suppress verbose logs
    for lib in ("azure", "opentelemetry", "httpx", "urllib3", "azure.identity", "openai"):
        logging.getLogger(lib).setLevel(logging.WARNING)
    logging.getLogger("opentelemetry.instrumentation.instrumentor").setLevel(logging.ERROR)
    logging.getLogger("opentelemetry.trace").setLevel(logging.ERROR)
    logging.getLogger("opentelemetry._logs._internal").setLevel(logging.ERROR)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logging.getLogger().addHandler(console)
    return logger

logger = setup_logging()
tracer = trace.get_tracer("HarmattanAI_Backend")
AGENT_CALL_TIMEOUT = 120.0

# --- AZURE AGENT INVOCATION ---
async def run_azure_agent(user_input: str) -> str | None:
    """Invokes the Azure AI Agent."""
    with tracer.start_as_current_span("run_azure_agent") as span:
        try:
            creds_async = AsyncClientSecretCredential(
                tenant_id=os.environ["AZURE_TENANT_ID"],
                client_id=os.environ["AZURE_CLIENT_ID"],
                client_secret=os.environ["AZURE_CLIENT_SECRET"]
            )
            async with creds_async, AzureAIAgent.create_client(credential=creds_async) as client:
                settings = AzureAIAgentSettings.create()
                agent_def = await asyncio.wait_for(
                    client.agents.get_agent(agent_id=os.environ["AZURE_AI_AGENT_AGENT"]),
                    timeout=AGENT_CALL_TIMEOUT
                )
                agent = AzureAIAgent(client=client, definition=agent_def, settings=settings)
                api_response = await asyncio.wait_for(
                    agent.get_response(messages=user_input),
                    timeout=AGENT_CALL_TIMEOUT
                )
            return str(api_response)
        except (ClientAuthenticationError, HttpResponseError, asyncio.TimeoutError, Exception) as e:
            logger.error(f"Error in run_azure_agent: {e}", exc_info=True)
            # Re-raise a generic exception to be caught by the dispatcher
            raise ConnectionError(f"Failed to communicate with Azure AI Service: {type(e).__name__}")


# --- OPENAI AGENT INVOCATION ---
async def run_openai_agent(user_input: str) -> str | None:
    """Invokes the OpenAI API with SSL verification handling."""
    with tracer.start_as_current_span("run_openai_agent") as span:
        if "OPENAI_API_KEY" not in os.environ:
            raise ValueError("OpenAI API key is not configured.")
        
        try:
            # Create a custom httpx client to handle SSL verification
            with httpx.Client(verify=None) as http_client:
                client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], http_client=http_client)
                response = client.responses.create(
                model="gpt-4o",
                input=[
                    {
                    "role": "system",
                    "content": [
                        {
                        "type": "input_text",
                        "text": "You are an agent tasked with classifying notes from French doctors into ICD-10 codes, using only the official ICD-10 classification provided by the World Health Organization at https://icd.who.int/browse10/2019/en#.\n\nFor each input note, extract up to 15 relevant ICD-10 codes. Each code must strictly follow the format: one letter, two digits, a dot, and one digit (e.g., X99.9).\n\nYour output should be a JSON  with each element structured as follows:\n\n  {\n    \"extract\": \"str\",       // The input note from the doctor used to codify\n    \"code\": \"str\",          // The ICD-10 code in X99.9 format\n    \"description\": \"str\",   // A short description of the ICD-10 code\n    \"url\": \"str\"            // The exact URL to the ICD-10 code page on the WHO website\n  }\n... : ...\n  // up to 15 items\n\nIf no valid ICD-10 code is found, return an empty JSON . Do not include any additional text or formatting outside of the JSON structure.\nA code should only appear once. \nIf, and only if a patient have more than 65, it's an old people, You can add R54  : senility\n"
                        }
                    ]
                    },
                    {
                    "role": "user",
                    "content": [
                        {
                        "type": "input_text",
                        "text": user_input
                        }
                    ]
                    }
                ],
                text={
                    "format": {
                    "type": "text"
                    }
                },
                reasoning={},
                tools=[
                    {
                    "type": "web_search_preview",
                    "user_location": {
                        "type": "approximate",
                        "country": "FR"
                    },
                    "search_context_size": "low"
                    }
                ],
                temperature=1,
                max_output_tokens=2048,
                top_p=1,
                store=True
                )
            return response.output_text
        except httpx.ConnectError as e:
            logger.error(f"SSL Connection Error calling OpenAI API: {e}", exc_info=True)
            raise ConnectionError("SSL Connection Failed: Could not verify the server's certificate.")
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}", exc_info=True)
            raise ConnectionError(f"Failed to communicate with OpenAI Service: {type(e).__name__}")


# --- DATA PROCESSING ---
def extract_json_from_string(text: str) -> str | None:
    """Extracts JSON content potentially wrapped in markdown code fences."""
    if not text:
        logger.warning("Input text for JSON extraction is empty or None.")
        return None
    match = re.search(r'```(?:json)?\s*([\[\{].*[\]\}])\s*```|([\[\{].*[\]\}])', text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1) if match.group(1) else match.group(2)
    logger.warning("Could not find JSON object or array in the agent's response.")
    return None

# --- MAIN DISPATCHER ---
async def get_agent_response_async(user_input: str, provider: str) -> list | None:
    """
    Runs the selected agent, parses the JSON response, and handles errors.
    Returns a list of dictionaries or raises an exception on failure.
    """
    raw_response = None
    if provider == "Azure":
        raw_response = await run_azure_agent(user_input)
    elif provider == "OpenAI":
        raw_response = await run_openai_agent(user_input)
    else:
        raise ValueError(f"Invalid provider selected: {provider}")

    if raw_response is None:
        logger.error("Agent returned no response.")
        raise ValueError("Agent returned no response.")

    json_string = extract_json_from_string(raw_response)
    if json_string is None:
        logger.error(f"Failed to extract JSON from raw response: {raw_response}")
        raise ValueError("Could not extract valid JSON data from the agent's response.")

    try:
        data = json.loads(json_string)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
        else:
            raise TypeError("The agent returned data in an unexpected format.")
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON response: {e}", exc_info=True)
        raise ValueError("Failed to parse the JSON data received from the agent.")

def get_agent_response_sync(user_input: str, provider: str) -> list | None:
    """Synchronous wrapper for the async agent call."""
    # This allows the Streamlit app to call the async logic simply.
    return asyncio.run(get_agent_response_async(user_input, provider))