from openai import OpenAI
import os
from pathlib import Path
import json
import xml.dom.minidom
import xml.etree.ElementTree as ET
import ast
from cookiecutter.main import cookiecutter
import argparse
import shutil



# TO-DO
#-----------------------------------------------------------------
#1 - Integration into Crop2ML
#1.1   - Get arguments from the command line (input folder output_folder -main_files)
#2 - Composite model support (prompt + response from GPT)
#3 - Add error handling for
#3.1   - Instructions extraction
#3.2   - File reading
#3.3   - Prompt creation
#3.4   - Response from GPT (process not found, etc...)
#4 - Documentation
#-----------------------------------------------------------------

#-----------------------------------------------------------------
# Function to extract text from a file
# This function reads the content of a file and returns it as a string.
#-----------------------------------------------------------------
def extract_text(file_path):
  with open(file_path, "r", encoding="utf-8", errors="replace") as file:
    return file.read()


#-----------------------------------------------------------------
# Function to extract the file extension from a file path
#-----------------------------------------------------------------
def extract_extension(file_path):
  fichier = Path(file_path)
  return fichier.suffix


#-----------------------------------------------------------------
# Function to determine the programming language based on file extension
# This function checks the file extension and returns the corresponding language name.
#-----------------------------------------------------------------
def language(extension):
  if extension == ".py":
    return "Python"
  elif extension == ".java":
    return "Java"
  elif extension == ".cs":
    return "C#"
  elif extension == ".cpp":
    return "C++"
  elif extension == ".for":
    return "Fortran"
  elif extension == ".f90":
    return "Fortran90"
  elif extension == ".pyx":
    return "Cython"
  else:
    return "Unknown"


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
# Function to create a prompt adapted to Agent-DescMeta/Agent-PyRefactor
# This function constructs a prompt based on the main file and the programming language.
#-----------------------------------------------------------------
def create_prompt_main_file(main_file, language_name):
  main_file_name = os.path.basename(main_file)
  
  prompt = f"Analyze the following crop model source code, written in {language_name}. The main file to process is {main_file_name}.\n"
  prompt += f"The content is marked clearly with --- START FILE --- at the start and --- END FILE --- at the end.\n"
  prompt += f"Follow the system instructions.\n\n"
  prompt += f"--- START FILE ---\n{extract_text(main_file)}\n--- END FILE ---"
  
  return prompt


#-----------------------------------------------------------------
# Function to create a prompt adapted to Agent-AlgoMeta and Agent-CyMLTranspile
# This function constructs a prompt based on the refactored code.
#-----------------------------------------------------------------
def create_prompt_refactor(code_refactored):
  prompt = f"Analyze the following Python crop model source code and follow the system instructions.\n\n"
  prompt += f"The content is marked clearly with --- START FILE --- at the start and --- END FILE --- at the end.\n"
  prompt += f"--- START FILE ---\n{code_refactored}\n--- END FILE ---"
  return prompt


#-----------------------------------------------------------------
# Function to create a prompt adapted to Agent-CompositeMeta
# This function constructs a prompt based on the XML files of each model units.
#-----------------------------------------------------------------
def create_prompt_composite(XML_files, composite):
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


#-----------------------------------------------------------------
# Function to create a prompt adapted to Agent-MetaMerge
# This function constructs a prompt based on the k candidates.
#-----------------------------------------------------------------
def create_prompt_python_consensus(python_path, folder_path, main_file, language_name, nb_iterations):
  main_file_path = None
  for root, dirs, files in os.walk(folder_path):
    if main_file in files:
      main_file_path = os.path.join(root, main_file)
      break
  if main_file_path is None:
    raise FileNotFoundError(f"File {main_file} is not there.")
  main_file_no_ext = Path(main_file).stem
  
  prompt = f"You will be provided {nb_iterations} python module, corresponding to interfaces of the source code file {main_file} written in {language_name}.\n"
  prompt += f"The source file is marked clearly with --- SOURCE CODE FILE: filename --- at the start and --- END SOURCE CODE FILE --- at the end.\n"
  prompt += f"Each python module is marked clearly with --- PYTHON MODULE N --- at the start and --- END PYTHON MODULE N --- at the end.\n"
  prompt += f"Follow the system instructions.\n\n"
  prompt += f"--- SOURCE CODE FILE: {main_file} ---\n{extract_text(main_file_path)}\n--- END SOURCE CODE FILE ---"
 
  for i in range(1, nb_iterations + 1):
    json_file_path = f"{python_path}{i}/{main_file_no_ext}_code.py"
    prompt += f"\n\n--- PYTHON MODULE {i} ---\n{extract_text(json_file_path)}\n--- END PYTHON MODULE {i} ---"
  
  return prompt


#-----------------------------------------------------------------
# Function to create a prompt for the GPT model
# This function constructs a prompt based on the number of files in the specified folder, the main file, and the programming language.
#-----------------------------------------------------------------
def create_prompt_all_files(folder_path, main_file, list_files, language_name):
  nb_files = len(list_files)

  main_file_path = None
  for root, dirs, files in os.walk(folder_path):
    if main_file in files:
      main_file_path = os.path.join(root, main_file)
      break
  if main_file_path is None:
    raise FileNotFoundError(f"File {main_file} is not there.")
  
  prompt = f"Analyze the {nb_files} following crop model source code, written in {language_name}. The main file to process is {main_file}, the rest is auxiliary files for context only.\n"
  prompt += f"Each file is marked clearly with --- FILE: filename --- at the start and --- END FILE --- at the end.\n"
  prompt += f"Follow the system instructions.\n\n"
  prompt += f"--- FILE: {main_file} ---\n{extract_text(main_file_path)}\n--- END FILE ---"
  
  if nb_files > 0:
    for file in list_files:
      prompt += f"\n\n--- FILE: {os.path.basename(file)} ---\n{extract_text(file)}\n--- END FILE ---"
  
  return prompt


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
# Function to convert JSON data to XML format
# This function takes a file path and JSON data, then converts the data into a Crop2ML-friendly XML format.
#-----------------------------------------------------------------
def json_to_xml(file_path, json_metadata, json_code):
  metadata = json_metadata['metadata']
  init = json_code['init']
  process = json_code['process']
  inputs = json_code.get('inputs',[])
  outputs = json_code.get('outputs',[])
  functions = json_code.get('functions', [])
  tests = json_code['tests']

  # Create XML tree
  root = ET.Element('ModelUnit', {
    "modelid": Path(file_path).stem + "." + metadata['Title'],
    "name": metadata['Title'],
    "timestep": "1",
    "version":  metadata['Model version']
  })

  # Description section
  desc = ET.SubElement(root, 'Description')
  ET.SubElement(desc, 'Title').text = metadata.get('Title','')
  ET.SubElement(desc, 'Authors').text = metadata.get('Authors', '')
  ET.SubElement(desc, 'Institution').text = metadata.get('Institution', '')
  ET.SubElement(desc, 'URI').text = metadata.get('URI', '')
  ET.SubElement(desc, 'Reference').text = metadata.get('DOI', '')
  ET.SubElement(desc, 'ExtendedDescription').text = metadata.get('Extended description', '')
  ET.SubElement(desc, 'ShortDescription').text = metadata.get('Short description', '')

  # I/O section
  xml_inputs = ET.SubElement(root, 'Inputs')
  add_inputs(xml_inputs, inputs)

  xml_outputs = ET.SubElement(root, 'Outputs')
  add_outputs(xml_outputs, outputs)

  # Initialization
  if init['name'] != '-':
    ET.SubElement(root, 'Initialization', {
      'name': f"init_{metadata['Title']}",
      'language': 'cyml',
      'filename': f"algo/pyx/init_{metadata['Title']}.pyx"
    })

  # Functions
  if functions != '-' and functions != []:
    for func in functions:
      ET.SubElement(root, 'Function', {
        'name': func['name'],
        'description': func['description'],
        'language': 'cyml',
        'type': 'external',
        'filename': f"algo/pyx/{func['name']}.pyx"
      })

  # Main Algorithm
  ET.SubElement(root, 'Algorithm', {
    'language': 'cyml',
    'platform': '',
    'filename': 'algo/pyx/' + metadata['Title'] + ".pyx"
  })

  # Parametersets
  add_tests(root, tests, inputs)

  return ET.tostring(root, encoding='utf-8')


# Function: convert JSON 'inputs' to Crop2ML-friendly XML inputs
def add_inputs(xml_inputs, json_inputs):
  for input in json_inputs:
    attrs = {
        'name': str(input['name']),
        'description': str(input.get('description', '')),
        'inputtype': str(input.get('inputtype', ''))
    }
    if input.get('inputtype') == 'parameter':
      attrs['parametercategory'] = str(input.get('category', ''))
    else:
      attrs['variablecategory'] = str(input.get('category', ''))
    attrs['datatype'] = str(input.get('datatype', ''))
    if input.get('datatype') == "DOUBLEARRAY" or input.get('datatype') == "DOUBLELIST":
      attrs['len'] = str(input.get('len', ''))
    attrs['max'] = str(input.get('max', ''))
    attrs['min'] = str(input.get('min', ''))
    attrs['default'] = str(input.get('default', ''))
    attrs['unit'] = str(input.get('unit', ''))
    attrs['uri'] = str(input.get('uri', ''))

    ET.SubElement(xml_inputs, 'Input', attrs)


# Function: convert JSON 'outputs' to Crop2ML-friendly XML outputs
def add_outputs(xml_outputs, json_outputs):
  for output in json_outputs:
    attrs = {
      'name': str(output['name']),
      'description': str(output.get('description', '')),
      'variablecategory': str(output.get('category', '')),
      'datatype': str(output.get('datatype', ''))
    }
    if output.get('datatype') == 'DOUBLEARRAY' or output.get('datatype') == 'DOUBLELIST':
      attrs['len'] = str(output.get('len', ''))
    attrs['max'] = str(output.get('max', ''))
    attrs['min'] = str(output.get('min', ''))
    attrs['unit'] = str(output.get('unit', ''))
    attrs['uri'] = str(output.get('uri', ''))
    ET.SubElement(xml_outputs, 'Output', attrs)


# Function: convert JSON 'tests' to Crop2ML-friendly XML test
def add_tests(root_XML, json_tests, json_inputs):
  parametersSets = ET.SubElement(root_XML, 'Parametersets')
  testSets = ET.SubElement(root_XML, 'Testsets')

  if json_tests == [] or json_tests[0] == "-":
    return
  
  parameter_inputs = []
  variable_inputs = []
  inputtype_by_name = {inp['name']: inp.get('inputtype', '') for inp in json_inputs}

  for test in json_tests:
    test_inputs = test['inputs']
    test_outputs = test['outputs']

    for test_input in test_inputs:
      name = test_input['name']
      if inputtype_by_name.get(name) is not None:
        if inputtype_by_name.get(name) == 'parameter':
          parameter_inputs.append(test_input)
        else:
          variable_inputs.append(test_input)

    if len(parameter_inputs) > 0:
      parameterset = ET.SubElement(parametersSets, 'Parameterset', {
        'name': "p_" + test.get('name'),
        'description': test.get('description', '')
      })
      for parameter_input in parameter_inputs:
        ET.SubElement(parameterset, 'Param', name=parameter_input.get('name')).text = str(parameter_input.get('value'))

    if len(variable_inputs) > 0 or len(test_outputs) > 0:
      testset = ET.SubElement(testSets, 'Testset', {
        'name': "t_" + test.get('name'),
        'description': test.get('description', '')
      })
      if len(parameter_inputs) > 0:
        testset.set('parameterset', "p_" + test.get('name'))
      test = ET.SubElement(testset, 'Test', name=testset.get('name'))
      for variable_input in variable_inputs:
        ET.SubElement(test, 'InputValue', name=variable_input.get('name')).text = str(variable_input.get('value'))
      for test_output in test_outputs:
        ET.SubElement(test, 'OutputValue', name=test_output.get('name')).text = str(test_output.get('value'))


#-----------------------------------------------------------------
# Function to convert JSON data to XML format
# This function takes a file path and JSON data, then converts the data into a Crop2ML-friendly XML format.
#-----------------------------------------------------------------
def json_to_xml_composite(file_path, json_metadata, XML_units):
  metadata = json_metadata['metadata']
  link_data = json_metadata.get('links', [])
  name = os.path.basename(file_path)

  # Create XML tree
  root = ET.Element('ModelComposition', {
    "name": name,
    "id": name + "." + name,
    "version": metadata['Model version'],
    "timestep": "1",
  })

  # Description section
  desc = ET.SubElement(root, 'Description')
  ET.SubElement(desc, 'Title').text = name
  ET.SubElement(desc, 'Authors').text = metadata.get('Authors', '')
  ET.SubElement(desc, 'Institution').text = metadata.get('Institution', '')
  ET.SubElement(desc, 'Reference').text = metadata.get('DOI', '')
  ET.SubElement(desc, 'ExtendedDescription').text = metadata.get('Extended description', '')
  ET.SubElement(desc, 'ShortDescription').text = metadata.get('Short description', '')

  # Composition section
  composition = ET.SubElement(root, 'Composition')
  for unit_path in XML_units:
    unit = extract_text(unit_path)
    root_unit = ET.fromstring(unit)
    ET.SubElement(composition, 'Model', {
      'name': root_unit.attrib.get("name"),
      'id': root_unit.attrib.get("modelid"),
      'filename': f"unit.{root_unit.attrib.get('name')}.xml"
    })

  links_elem = ET.SubElement(composition, 'Links')

  internal_sources = set()
  internal_targets = set()
  for link in link_data:
    internal_sources.add(link['Source variable name'])
    internal_targets.add(link['Target variable name'])

  for unit_path in XML_units:
    unit = extract_text(unit_path)
    root_unit = ET.fromstring(unit)
    unit_name = root_unit.attrib.get("name")
    for input_elem in root_unit.findall('.//Input'):
      input_name = input_elem.attrib.get('name')
      if input_name not in internal_sources:
        ET.SubElement(links_elem, 'InputLink', {
          'target': f"{unit_name}.{input_name}", 
          'source': input_name
        })

  for link in link_data:
    ET.SubElement(links_elem, 'InternalLink', {
      'target': f"{link['Target model unit']}.{link['Target variable name']}", 
      'source': f"{link['Source model unit']}.{link['Source variable name']}" 
    })
  
  for unit_path in XML_units:
    unit = extract_text(unit_path)
    root_unit = ET.fromstring(unit)
    unit_name = root_unit.attrib.get("name")
    for output_elem in root_unit.findall('.//Output'):
      output_name = output_elem.attrib.get('name')
      if output_name not in internal_targets:
        ET.SubElement(links_elem, 'OutputLink', {
          'target': output_name,
          'source': f"{unit_name}.{output_name}"
        })
  
  return ET.tostring(root, encoding='utf-8')


#-----------------------------------------------------------------
# Function to create metadata JSON file for a unit model 
# This function generates metadata for a given code file and saves it as a JSON file.
#-----------------------------------------------------------------
def create_unit_metadata(api_key_path, agent_descmeta, model, output_path, main_file):
  api_key = extract_api_key(api_key_path)
  extension = extract_extension(main_file)
  language_name = language(extension)
  instructions_metadata = extract_text(agent_descmeta)

  prompt = create_prompt_main_file(main_file, language_name)
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
  prompt = create_prompt_composite(modelunits, main_file)
  response_metadata = send_to_gpt(instructions_metadata, prompt, api_key, model, "medium", "json_object", "low")

  os.makedirs(output_path, exist_ok=True)
  base = Path(main_file).stem
  json_metadata_path = output_path + "/" + base + "_composite.json"
  json_metadata = json.loads(response_metadata)

  with open(json_metadata_path, "w", encoding="utf-8") as f:
    json.dump(json_metadata, f, ensure_ascii=False, indent=4)
  return json_metadata


#-----------------------------------------------------------------
# Function to create python code
# This function generates a refactored python module for a given code file and saves it.
#-----------------------------------------------------------------
def create_code(api_key_path, agent_pyrefactor, model, output_path, main_file):
  api_key = extract_api_key(api_key_path)
  extension = extract_extension(main_file)
  language_name = language(extension)
  instructions_refactor = extract_text(agent_pyrefactor)

  prompt = create_prompt_main_file(main_file, language_name)
  response_refactored = send_to_gpt(instructions_refactor, prompt, api_key, model, "high", "text", "low")

  os.makedirs(output_path, exist_ok=True)
  base = Path(main_file).stem
  python_code_path = output_path + "/" + base + "_code.py"

  with open(python_code_path, "w", encoding="utf-8") as f:
    f.write(response_refactored)
  return response_refactored


#-----------------------------------------------------------------
# Function to create a consensus python code from k candidates 
# This function generates a refactored python module for k given python code file and saves it.
#-----------------------------------------------------------------
def python_consensus(api_key_path, agent_pyconsensus, model, python_path, folder_path, output_path, main_file, nb_iterations):
  api_key = extract_api_key(api_key_path)
  extension = extract_extension(folder_path + main_file)
  language_name = language(extension)
  instructions_consensus = extract_text(agent_pyconsensus)

  prompt = create_prompt_python_consensus(python_path, folder_path, main_file, language_name, nb_iterations)
  response_refactored = send_to_gpt(instructions_consensus, prompt, api_key, model, "high", "text", "low")

  os.makedirs(output_path, exist_ok=True)
  base, _ = os.path.splitext(main_file)
  python_code_path = output_path + base + ".py"

  with open(python_code_path, "w", encoding="utf-8") as f:
    f.write(response_refactored)
  return response_refactored


#-----------------------------------------------------------------
# Function to transpile code to CyML
# This function generates a CyML module for a given python module and saves it.
#-----------------------------------------------------------------
def transpile(api_key_path, agent_cymltranspile, model, output_path, python_module, python_name):
  api_key = extract_api_key(api_key_path)
  instructions_transpile = extract_text(agent_cymltranspile)

  prompt_transpiled = create_prompt_refactor(python_module)
  response_cyml = send_to_gpt(instructions_transpile, prompt_transpiled, api_key, model, "high", "text", "low")

  os.makedirs(output_path, exist_ok=True)
  base = Path(python_name).stem
  cyml_code_path = output_path + "/" + base + ".pyx"

  with open(cyml_code_path, "w", encoding="utf-8") as f:
    f.write(response_cyml)
  return response_cyml


#-----------------------------------------------------------------
# Function to create algorithm metadata JSON file
# This function generates a algorithm metadata for a given code file and saves it as a JSON file.
#-----------------------------------------------------------------
def create_algo_metadata(api_key_path, agent_algometa, model, output_path, python_code, model_name):
  api_key = extract_api_key(api_key_path)
  instructions_json = extract_text(agent_algometa)

  prompt = create_prompt_refactor(python_code)
  response = send_to_gpt(instructions_json, prompt, api_key, model, "high", "json_object", "low")

  os.makedirs(output_path, exist_ok=True)
  base = Path(model_name).stem
  json_code_path = output_path + "/" + base + "_code.json"
  json_code = json.loads(response)

  with open(json_code_path, "w", encoding="utf-8") as f:
    json.dump(json_code, f, ensure_ascii=False, indent=4)

  return json_code


#-----------------------------------------------------------------
# Function to create Crop2ML XML file from JSON metadata and algorithm
# This function generates a Crop2ML XML file from given JSON metadata and algorithm.
#-----------------------------------------------------------------
def JSON_to_XML_unit(model_composite, output_path, name_file, json_metadata, json_algo):
  base = Path(name_file).stem
  xml_path = output_path + "/" + "unit." + base + ".xml"
  xml_data = json_to_xml(model_composite, json_metadata, json_algo)
  dom = xml.dom.minidom.parseString(xml_data)
  with open(xml_path, 'w', encoding='utf-8') as f:
    f.write(dom.toprettyxml())
  return xml_path


#-----------------------------------------------------------------
# Function to create Crop2ML XML file from JSON metadata and algorithm
# This function generates a Crop2ML XML file from given JSON metadata and algorithm.
#-----------------------------------------------------------------
def JSON_to_XML_composite(model_composite, output_path, json_metadata, XML_units):
  base = Path(model_composite).stem
  xml_path = output_path + "/" + "composition." + base + ".xml"
  xml_data = json_to_xml_composite(model_composite, json_metadata, XML_units)
  dom = xml.dom.minidom.parseString(xml_data)
  with open(xml_path, 'w', encoding='utf-8') as f:
    f.write(dom.toprettyxml())
  return xml_path

#-----------------------------------------------------------------
# Function to extract functions from a Python code string and save each to a separate file
# This function parses the Python code string, detects each function definition, and creates a new file for each function containing only that function.
#-----------------------------------------------------------------
def extract_functions_to_files(python_code, algo_meta, filename, output_folder):
  try:
    tree = ast.parse(python_code)
  except SyntaxError as e:
    print(f"Syntax error in code: {e}")
    return
  
  lines = python_code.splitlines()
  for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
      function_name = node.name
      start_line = node.lineno - 1
      if node.decorator_list:
        for decorator in node.decorator_list:
          start_line = min(start_line, decorator.lineno - 1)
      end_line = node.end_lineno
      body_start = node.body[0].lineno - 1 if node.body else end_line
      body_lines = lines[body_start:end_line]
      
      if function_name == algo_meta.get('init', {}).get('name') or function_name == algo_meta.get('process', {}).get('name'):
        if function_name == algo_meta.get('init', {}).get('name'):
          file_name = f"init_{filename}"
        elif function_name == algo_meta.get('process', {}).get('name'):
          file_name = filename
      
        if node.body and isinstance(node.body[-1], ast.Return):
          function_lines = lines[body_start : node.body[-1].lineno - 1]
        else:
          function_lines = body_lines
        function_code = '\n'.join(function_lines)
      else:
        file_name = function_name
        function_code = '\n'.join(lines[start_line:end_line])
      
      file_path = os.path.join(output_folder, f"{file_name}.py")
      with open(file_path, 'w', encoding='utf-8') as f:
        f.write(function_code)


#-----------------------------------------------------------------
#CONFIGURATION
#-----------------------------------------------------------------
UNIT_META = "./Agent-UnitMeta.txt"
COMPOSITE_META = "./Agent-CompositeMeta.txt"
PY_REFACTOR = "./Agent-PyRefactor.txt"
PY_CONSENSUS = "./Agent-PyConsensus.txt"
CYML_TRANSPILE = "./Agent-CyMLTranspile.txt"
ALGO_META = "./Agent-AlgoMeta.txt"
API_KEY_PATH = "./api_key.txt"
MODEL = "gpt-5"
COOKIE_CUTTER_TEMPLATE = "../cookiecutter-crop2ml"

COMPONENTS_DICT = {
  "ApsimCampbell/": "SoilTemperature.cs",
  "BiomaSurfacePartonSoilSWATC/": "SoilTemperatureSWAT.cs",
  "DSSAT_ST_standalone/": "STEMP.for"
}

first_index_component = 1
last_index_component = 1#len(COMPONENTS_DICT) - 1
number_iteration = 3
component_keys = list(COMPONENTS_DICT.keys())
component_values = list(COMPONENTS_DICT.values())

#-----------------------------------------------------------------
# Simulation section
#-----------------------------------------------------------------
if __name__ == "__main__":
  # Read arguments from command line
  parser = argparse.ArgumentParser(description="Process crop model units and composite.")
  parser.add_argument('-u', '--unit', action='append', required=True, help='Model unit files (can be specified multiple times)')
  parser.add_argument('-c', '--composite', required=False, help='Model composite file')
  parser.add_argument('-o', '--output', required=True, help='Output folder')
  
  args = parser.parse_args()
  
  model_units = args.unit
  model_composite = args.composite
  output_folder = args.output
  algo_metas = []
  XML_units = []
  codes = []
  
  # Process each model unit
  for i in range(len(model_units)):
    print(f"Processing descriptive metadata of the model unit {Path(model_units[i]).name}")
    metadata = create_unit_metadata(API_KEY_PATH, UNIT_META, MODEL, output_folder, model_units[i])

    print(f"Refactoring the model unit {Path(model_units[i]).name}")
    code = create_code(API_KEY_PATH, PY_REFACTOR, MODEL, output_folder, model_units[i])
    codes.append(code)

    print(f"Processing algorithmic metadata of the model unit {Path(model_units[i]).name}")
    algo = create_algo_metadata(API_KEY_PATH, ALGO_META, MODEL, output_folder, code, model_units[i])
    algo_metas.append(algo)
    if model_composite is None :
      XML_units.append(JSON_to_XML_unit(model_units[0], output_folder, model_units[i], metadata, algo))
    else :
      XML_units.append(JSON_to_XML_unit(model_composite, output_folder, model_units[i], metadata, algo))
    
    #print("Transpiling into CyML...")
    #cyml = transpile(API_KEY_PATH, CYML_TRANSPILE, MODEL, output_folder, code, model_units[i])
    #extract_functions_to_files(code, f"{output_folder}/crop2ml/algo/pyx/")'''

  # Process model composite
  print(f"Processing metadata of the composite model")
  composite_metadata = create_composite_metadata(API_KEY_PATH, COMPOSITE_META, MODEL, output_folder, XML_units, model_composite)
  if model_composite is None :
    model_composite = model_units[0]
  xml_composite = JSON_to_XML_composite(model_composite, output_folder, composite_metadata, XML_units)

  # Create cookiecutter project
  print(f"Generating Crop2ML project for the model component")
  metadata = composite_metadata['metadata']
  cookiecutter(COOKIE_CUTTER_TEMPLATE, 
    no_input=True, 
    extra_context={'project_name':Path(model_composite).stem, 
                  'repo_name':Path(model_composite).stem,
                  'author_name': metadata['Authors'],
                  'description': metadata['Extended description'], 
                  'open_source_license':"MIT"},
    output_dir=output_folder)
  
  # Move generated files to the cookiecutter project directory
  for i in range(len(codes)):
    extract_functions_to_files(codes[i], algo_metas[i], Path(model_units[i]).name, f"{output_folder}/{Path(model_composite).stem}/crop2ml/algo/pyx/")
  for xml_file in XML_units:
    shutil.copy(xml_file, f"{output_folder}/{Path(model_composite).stem}/crop2ml/")
  shutil.copy(xml_composite, f"{output_folder}/{Path(model_composite).stem}/crop2ml/")