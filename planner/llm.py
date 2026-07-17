# planner/llm.py

import requests
import json
import time

MODEL_NAME = "llama3.2"
OLLAMA_HOST = "http://localhost:11434"
ACTUAL_MODEL_NAME = "llama3.2" # Updated dynamically

def generate_json(prompt: str) -> dict:
    """
    Sends a prompt to the local Ollama instance and returns the parsed JSON response.
    Retries once on JSON parsing or connection failures.
    """
    url = f"{OLLAMA_HOST}/api/generate"
    payload = {
        "model": ACTUAL_MODEL_NAME,
        "prompt": prompt,
        "format": "json",
        "stream": False
    }

    for attempt in range(2):
        try:
            response = requests.post(url, json=payload, timeout=45)
            response.raise_for_status()
            response_json = response.json()
            text_content = response_json.get("response", "").strip()
            
            # Parse the text content as JSON
            return json.loads(text_content)
        except (requests.RequestException, json.JSONDecodeError, ValueError) as e:
            if attempt == 0:
                print(f"Ollama request/parse failed (Error: {e}). Retrying once...")
                time.sleep(1.5)
                continue
            raise RuntimeError(f"Ollama generation failed after 2 attempts: {e}")

def check_ollama_status() -> tuple[bool, str]:
    """
    Checks if Ollama is running locally and whether the required model is pulled.
    Returns (True, "") if ready, or (False, "error message") if not.
    """
    global ACTUAL_MODEL_NAME
    # 1. Check if Ollama service is running
    try:
        response = requests.get(OLLAMA_HOST, timeout=3)
        if response.status_code != 200:
            return False, "Ollama service returned an invalid response."
    except Exception:
        err_msg = (
            "Ollama is not installed or not running.\n\n"
            "To fix this:\n"
            "1. Download and install Ollama from: https://ollama.com/\n"
            "2. Make sure the Ollama application is running on your system.\n"
            "3. Pull the required model by running this command in your terminal:\n"
            f"   ollama pull {MODEL_NAME}\n"
            "4. Restart the application."
        )
        return False, err_msg

    # 2. Check if the required model is pulled
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        if response.status_code == 200:
            models_data = response.json()
            available_models = [m["name"] for m in models_data.get("models", [])]
            
            # Check if MODEL_NAME matches exactly or with a tag prefix (like llama3.2:latest or llama3.2:3b)
            found_model = None
            for model in available_models:
                if model == MODEL_NAME or model.startswith(f"{MODEL_NAME}:"):
                    found_model = model
                    break
            
            if not found_model:
                err_msg = (
                    f"Model '{MODEL_NAME}' is not downloaded in Ollama.\n\n"
                    "To fix this:\n"
                    "1. Open your terminal/command prompt and run:\n"
                    f"   ollama pull {MODEL_NAME}\n"
                    "2. Restart the application."
                )
                return False, err_msg
            
            ACTUAL_MODEL_NAME = found_model
            return True, ""
        else:
            return False, "Failed to retrieve models list from Ollama."
    except Exception as e:
        return False, f"Error checking models: {str(e)}"
