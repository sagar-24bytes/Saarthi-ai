from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel
from typing import List
import json
from planner.llm import generate_json


# ---- Structured schema ----

class Step(BaseModel):
    tool: str
    args: dict

class Plan(BaseModel):
    goal: str
    steps: List[Step]

parser = PydanticOutputParser(pydantic_object=Plan)

# ---- LangGraph node ----

def planner_node(state):
    user_text = state["user_text"]
    resolved_path = state.get("resolved_path") or "C:/Users/username/Downloads"
    # Standardize to forward slashes for prompt examples
    resolved_path = resolved_path.replace("\\", "/")

    prompt = f"""
You are an AI planning module for Saarthi, a personal desktop assistant.
You must analyze the user's goal and generate a structured plan.

Rules:
- If organizing a folder, ALWAYS:
  1. scan the folder
  2. create required subfolders FIRST
  3. then move files into those subfolders
- Never create a folder that already exists unless it is a subfolder.

Output format MUST be a single JSON object matching this structure:
{{
  "goal": "description of the goal",
  "steps": [
    {{
      "tool": "scan_folder",
      "args": {{"path": "{resolved_path}"}}
    }},
    {{
      "tool": "create_folder",
      "args": {{"path": "{resolved_path}/documents"}}
    }},
    {{
      "tool": "move_file",
      "args": {{
        "source_directory": "{resolved_path}",
        "destination_directory": "{resolved_path}/documents",
        "file_pattern": "*.pdf"
      }}
    }}
  ]
}}

Ensure all keys ("goal", "steps", "tool", "args") are present.
Use only allowed tools: scan_folder, create_folder, move_file, open_folder.

User goal:
"{user_text}"
"""

    try:
        plan_dict = generate_json(prompt)
        # Validate and format with parser
        parsed_plan = parser.parse(json.dumps(plan_dict))
        return {"plan": parsed_plan.dict()}
    except Exception as e:
        print(f"Planner error: {e}")
        return {
            "plan": {
                "error": f"Ollama planning failed: {str(e)}"
            }
        }

