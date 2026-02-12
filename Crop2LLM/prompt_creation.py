import os
import json
from utilities import extract_text
#-----------------------------------------------------------------
# Function to create a prompt adapted to Agent-DescMeta/Agent-PyRefactor
# This function constructs a prompt based on the main file and the programming language.
#-----------------------------------------------------------------
def prompt_unit(main_file, language_name):
  main_file_name = os.path.basename(main_file)
  
  prompt = f"Analyze the following crop model source code, written in {language_name}. The main file to process is {main_file_name}.\n"
  prompt += f"The content is marked clearly with --- START FILE --- at the start and --- END FILE --- at the end.\n"
  prompt += f"Follow the system instructions.\n\n"
  prompt += f"--- START FILE ---\n{extract_text(main_file)}\n--- END FILE ---"
  
  return prompt


#-----------------------------------------------------------------
# Function to create a prompt adapted to Agent-AlgoMeta
# This function constructs a prompt based on the refactored code.
#-----------------------------------------------------------------
def prompt_refactor(code_refactored):
  prompt = f"Analyze the following Python crop model source code and follow the system instructions.\n"
  prompt += f"The Python code is marked clearly with --- START FILE --- at the start and --- END FILE --- at the end.\n\n"
  prompt += f"--- START FILE ---\n{code_refactored}\n--- END FILE ---"
  return prompt


#-----------------------------------------------------------------
# Function to create a prompt adapted to Agent-CyMLTranspile
# This function constructs a prompt based on the refactored code.
#-----------------------------------------------------------------
def prompt_transpile(code_refactored, algo_meta):
  prompt = f"Analyze the following Python crop model source code along with its JSON documentation and follow the system instructions.\n"
  prompt += f"The JSON documentation is marked clearly with --- START DOCUMENTATION --- at the start and --- END DOCUMENTATION --- at the end.\n"
  prompt += f"The Python code is marked clearly with --- START FILE --- at the start and --- END FILE --- at the end.\n\n"
  prompt += f"--- START DOCUMENTATION ---\n{json.dumps(algo_meta, indent=4)}\n--- END DOCUMENTATION ---\n\n"
  prompt += f"--- START FILE ---\n{code_refactored}\n--- END FILE ---"
  return prompt


#-----------------------------------------------------------------
# Function to create a prompt adapted to Agent-CompositeMeta
# This function constructs a prompt based on the XML files of each model units.
#-----------------------------------------------------------------
def prompt_composite(XML_files, composite):
  prompt = ""
  if composite is not None:
    prompt += f"Analyze the following file representing the composite crop model and follow the system instructions.\n"
    prompt += f"The composite is marked clearly with --- START COMPOSITE --- at the start and --- END COMPOSITE --- at the end.\n\n"
    prompt += f"--- START COMPOSITE ---\n{extract_text(composite)}\n--- END COMPOSITE ---\n\n"
  else :
    prompt += f"Analyze the following XML representing the model units of a composite crop model and follow the system instructions.\n"
    prompt += f"Each file is marked clearly with --- START FILE --- at the start and --- END FILE --- at the end.\n\n"

  for file in XML_files:
    prompt += f"--- START FILE ---\n{extract_text(file)}\n--- END FILE ---\n\n"
  return prompt