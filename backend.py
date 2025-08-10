# backend.py

import os
import asyncio
import logging
import json
import re
from typing import Optional, List, Dict

# Azure specific imports
from azure.core.exceptions import HttpResponseError

# OpenTelemetry specific imports
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from azure.monitor.opentelemetry import configure_azure_monitor

# Local imports
from azure_client import get_or_create_project_client, list_available_agents

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
    for lib in ("azure", "opentelemetry", "httpx", "urllib3", "azure.identity"):
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
def azure_agent_chat(
    user_message: str,
    icd_website: str,
    language: str,
    agent_id: Optional[str] = None
) -> str:
    """
    Creates a new thread, sends a system instruction with ICD website and language,
    sends the user message, runs the agent, and returns the agent's reply.
    """
    try:
        project_client = get_or_create_project_client()
        agents_client = project_client.agents
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Azure project client: {e}")
    
    # Use environment variable for agent ID if not provided
    if agent_id is None:
        agent_id = os.environ.get("AZURE_AI_AGENT_AGENT")
        if not agent_id:
            raise ValueError("No agent ID provided and AZURE_AI_AGENT_AGENT not set in environment")
    
    # Create system prompt with ICD website and language
    system_prompt = (
        f"You are an agent tasked with classifying notes from doctors into ICD-10 codes, "
        f"using only the official ICD-10 classification provided by the World Health Organization at {icd_website} (language: {language}).\n\n"
        f"For each input note, extract up to 15 relevant ICD-10 codes. Each code must strictly follow the format: one letter, two digits, a dot, and one digit (e.g., X99.9).\n\n"
        f"Your output should be a JSON array with each element structured as follows:\n\n"
        f"  {{\n    \"extract\": \"str\",       // The input note from the doctor used to codify\n    \"code\": \"str\",          // The ICD-10 code in X99.9 format\n    \"description\": \"str\",   // A short description of the ICD-10 code (in the selected language)\n    \"url\": \"str\"            // The exact URL to the ICD-10 code page on the WHO website\n  }}\n\n"
        f"If no valid ICD-10 code is found, return an empty JSON array. Do not include any additional text or formatting outside of the JSON structure.\n"
        f"A code should only appear once.\n"
        f"If, and only if a patient have more than 65, it's an old people, You can add R54: senility\n"
    )
    
    try:
        # 1. Create a fresh thread using the correct API method
        thread = agents_client.threads.create(body={})
        thread_id = thread.id
        logger.info(f"Created thread: {thread_id}")
        
        # 2. Post the system message first  
        system_message = agents_client.messages.create(
            thread_id=thread_id,
            role="assistant",
            content=system_prompt
        )
        logger.info("Posted system message to thread")
        
        # 3. Post the user's message
        user_message_obj = agents_client.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_message
        )
        logger.info("Posted user message to thread")
        
        # 4. Trigger processing (run the agent)
        run = agents_client.runs.create_and_process(
            thread_id=thread_id,
            agent_id=agent_id
        )
        
        # 5. Check run status
        if run.status == "failed":
            error_msg = f"Agent run failed: {getattr(run, 'last_error', 'Unknown error')}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        logger.info(f"Agent run completed with status: {run.status}")
        
        # 6. Retrieve all messages and return the last assistant reply
        messages = agents_client.messages.list(
            thread_id=thread_id,
            order="desc"  # Get newest messages first
        )
        
        # ItemPaged objects are iterable directly, no need for .data
        for msg in messages:
            if msg.role == "assistant" and msg.content:
                # Handle different content formats
                if hasattr(msg, 'text_messages') and msg.text_messages:
                    response = msg.text_messages[-1].text.value
                    logger.info("Retrieved agent response")
                    return response
                elif isinstance(msg.content, list):
                    for content_item in msg.content:
                        if hasattr(content_item, 'text') and hasattr(content_item.text, 'value'):
                            response = content_item.text.value
                            logger.info("Retrieved agent response")
                            return response
                elif isinstance(msg.content, str):
                    response = msg.content
                    logger.info("Retrieved agent response")
                    return response
        
        logger.warning("No response found from agent")
        return "No reply from agent."
        
    except HttpResponseError as e:
        error_msg = f"HTTP error during agent communication: {e.status_code} {getattr(e, 'message', str(e))}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error during agent communication: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise RuntimeError(error_msg)

async def run_azure_agent(user_input: str, icd_website: str, language: str, agent_id: Optional[str] = None) -> str | None:
    """
    Async wrapper for azure_agent_chat to maintain compatibility with existing code.
    """
    with tracer.start_as_current_span("run_azure_agent") as span:
        try:
            # Run the synchronous azure_agent_chat in a thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                azure_agent_chat, 
                user_input, 
                icd_website, 
                language,
                agent_id
            )
            return response
        except Exception as e:
            logger.error(f"Error in run_azure_agent: {e}", exc_info=True)
            raise ConnectionError(f"Failed to communicate with Azure AI Service: {type(e).__name__}")

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
async def get_agent_response_async(user_input: str, provider: str, icd_website: str, language: str, agent_id: Optional[str] = None) -> list | None:
    """
    Runs the Azure agent, parses the JSON response, and handles errors.
    Returns a list of dictionaries or raises an exception on failure.
    """
    if provider != "Azure":
        raise ValueError(f"Only Azure provider is supported. Invalid provider: {provider}")
    
    raw_response = await run_azure_agent(user_input, icd_website, language, agent_id)

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

def get_agent_response_sync(user_input: str, provider: str, icd_website: str, language: str, agent_id: Optional[str] = None) -> list | None:
    """Synchronous wrapper for the async agent call."""
    # This allows the Streamlit app to call the async logic simply.
    return asyncio.run(get_agent_response_async(user_input, provider, icd_website, language, agent_id))
