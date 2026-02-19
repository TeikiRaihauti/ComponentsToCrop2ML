from openai import OpenAI
import os
from pathlib import Path
import json
from utilities import extract_text, extract_extension, language
from prompt_creation import prompt_unit, prompt_composite, prompt_refactor, prompt_transpile

#-----------------------------------------------------------------
# Function to connect to OpenAI's API
# This function reads the API key from a file and initializes the OpenAI client.
#-----------------------------------------------------------------
def extract_api_key(API_KEY_PATH):
  api_key = extract_text(API_KEY_PATH)
  try:
    OpenAI(api_key = api_key)
  except Exception as e:
    print(f"An error occurred while connecting to OpenAI: {e}")
    return None
  return api_key


#-----------------------------------------------------------------
# Function to send instructions and prompt to OpenAI's model
# This function takes instructions, a prompt, an API key, and a model name and returns the response from the model.
#-----------------------------------------------------------------
def send_to_gpt(instructions, prompt, api_key, model, reasoning_effort, text_format, verbosity):
  client = OpenAI(api_key = api_key)

  response = client.responses.create(
    model=model,
    reasoning={"effort": reasoning_effort},
    store=True,
    text={
      "format": {"type": text_format},
      "verbosity": verbosity,
      },
    input=[
      {"role": "developer",
        "content": [{"type": "input_text", "text": instructions}],
      },
      {
        "role": "user",
        "content": [{"type": "input_text", "text": prompt}],
      }
    ],
  )

  response = response.output_text
  if response.startswith("```json"):
    response = response[7:].lstrip()
  if response.endswith("```"):
    response = response[:-3].rstrip()
  return(response)


#-----------------------------------------------------------------
# Function to create metadata JSON file for a unit model 
# This function generates metadata for a given code file and saves it as a JSON file.
#-----------------------------------------------------------------
def create_unit_metadata(api_key_path, agent_descmeta, model, output_path, main_file, helper_files):
  api_key = extract_api_key(api_key_path)
  extension = extract_extension(main_file)
  language_name = language(extension)
  instructions_metadata = extract_text(agent_descmeta)

  prompt = prompt_unit(main_file, language_name, helper_files)
  response_metadata = send_to_gpt(instructions_metadata, prompt, api_key, model, "medium", "json_object", "low")

  os.makedirs(output_path, exist_ok=True)
  base = Path(main_file).stem
  json_metadata_path = output_path + "/" + base + "_metadata.json"
  json_metadata = json.loads(response_metadata)

  with open(json_metadata_path, "w", encoding="utf-8") as f:
    json.dump(json_metadata, f, ensure_ascii=False, indent=4)
  return json_metadata


#-----------------------------------------------------------------
# Function to create metadata JSON file for a composite model 
# This function generates metadata for a given code file and saves it as a JSON file.
#-----------------------------------------------------------------
def create_composite_metadata(api_key_path, agent_compositemeta, model, output_path, modelunits, main_file):
  api_key = extract_api_key(api_key_path)
  instructions_metadata = extract_text(agent_compositemeta)
  prompt = prompt_composite(modelunits, main_file)
  response_metadata = send_to_gpt(instructions_metadata, prompt, api_key, model, "high", "json_object", "low")

  os.makedirs(output_path, exist_ok=True)
  if (main_file is None):
    base = Path(modelunits[0]).stem
  else:
    base = Path(main_file).stem
  json_metadata_path = output_path + "/" + base.replace("unit.", "") + "_composite.json"
  json_metadata = json.loads(response_metadata)

  with open(json_metadata_path, "w", encoding="utf-8") as f:
    json.dump(json_metadata, f, ensure_ascii=False, indent=4)
  return json_metadata

#-----------------------------------------------------------------
# Function to create algorithm metadata JSON file
# This function generates a algorithm metadata for a given code file and saves it as a JSON file.
#-----------------------------------------------------------------
def create_algo_metadata(api_key_path, agent_algometa, model, output_path, python_code, model_name):
  api_key = extract_api_key(api_key_path)
  instructions_json = extract_text(agent_algometa)

  prompt = prompt_refactor(python_code)
  response = send_to_gpt(instructions_json, prompt, api_key, model, "high", "json_object", "low")

  os.makedirs(output_path, exist_ok=True)
  base = Path(model_name).stem
  json_code_path = output_path + "/" + base + "_code.json"
  json_code = json.loads(response)

  with open(json_code_path, "w", encoding="utf-8") as f:
    json.dump(json_code, f, ensure_ascii=False, indent=4)

  return json_code


#-----------------------------------------------------------------
# Function to create python code
# This function generates a refactored python module for a given code file and saves it.
#-----------------------------------------------------------------
def create_python_code(api_key_path, agent_pyrefactor, model, output_path, main_file, helper_files):
  api_key = extract_api_key(api_key_path)
  extension = extract_extension(main_file)
  language_name = language(extension)
  instructions_refactor = extract_text(agent_pyrefactor)

  prompt = prompt_unit(main_file, language_name, helper_files)
  response_refactored = send_to_gpt(instructions_refactor, prompt, api_key, model, "high", "text", "low")

  os.makedirs(output_path, exist_ok=True)
  base = Path(main_file).stem
  python_code_path = output_path + "/" + base + "_code.py"

  with open(python_code_path, "w", encoding="utf-8") as f:
    f.write(response_refactored)
  return response_refactored


#-----------------------------------------------------------------
# Function to transpile code to CyML
# This function generates a CyML module for a given python module and saves it.
#-----------------------------------------------------------------
def create_cyml_code(api_key_path, agent_cymltranspile, model, python_module, algo_meta):
  api_key = extract_api_key(api_key_path)
  instructions_transpile = extract_text(agent_cymltranspile)

  prompt_transpiled = prompt_transpile(python_module, algo_meta)
  response_cyml = send_to_gpt(instructions_transpile, prompt_transpiled, api_key, model, "high", "text", "low")

  return response_cyml