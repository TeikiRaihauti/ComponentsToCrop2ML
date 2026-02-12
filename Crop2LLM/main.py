from pathlib import Path
from cookiecutter.main import cookiecutter
import argparse
import shutil
from utilities import check_files
from openAI_interaction import create_python_code, create_unit_metadata, create_algo_metadata, create_composite_metadata
from json2XML import json_to_XML_composite, json_to_XML_unit
from transpiler import transpile_functions

#-----------------------------------------------------------------
#CONFIGURATION
#-----------------------------------------------------------------
API_KEY_PATH = "./config/api_key.txt"
BIG_MODEL = "gpt-5.2"
SMALL_MODEL = "gpt-5-mini"
COOKIE_CUTTER_TEMPLATE = "./config/cookiecutter-crop2ml/"
LANGUAGES = ['cs','cpp','py','f90','java','simplace','sirius', 'openalea','apsim','dssat','stics','bioma']

UNIT_META = "./config/Agents/Agent-UnitMeta.txt"
COMPOSITE_META = "./config/Agents/Agent-CompositeMeta.txt"
PY_REFACTOR = "./config/Agents/Agent-PyRefactor.txt"
CYML_TRANSPILE = "./config/Agents/Agent-CyMLTranspile.txt"
ALGO_META = "./config/Agents/Agent-AlgoMeta.txt"
CONFIG_FILES = [
    UNIT_META,
    COMPOSITE_META,
    PY_REFACTOR,
    CYML_TRANSPILE,
    ALGO_META,
    API_KEY_PATH
]

#-----------------------------------------------------------------
# Simulation section
#-----------------------------------------------------------------
if __name__ == "__main__":
  # Read arguments from command line
  parser = argparse.ArgumentParser(description="Process crop model units and composite.")
  parser.add_argument('-u', '--unit', nargs='+', required=True, help='Model unit files (can be specified multiple times)')
  parser.add_argument('-c', '--composite', required=False, help='Model composite file')
  parser.add_argument('-o', '--output', required=True, help='Output folder')
  args = parser.parse_args()

  model_units = args.unit
  model_composite = args.composite
  output_folder = args.output
  desc_metas = []
  algo_metas = []
  XML_units = []
  codes = []
  check_files(*model_units, comp=model_composite, config_files=CONFIG_FILES)
  
  # Process each model unit
  for i in range(len(model_units)):
    model_unit_name = Path(model_units[i]).stem

    print(f"Processing descriptive metadata of the model unit {i+1} : {model_unit_name}...")
    metadata = create_unit_metadata(API_KEY_PATH, UNIT_META, SMALL_MODEL, output_folder, model_units[i])
    desc_metas.append(metadata)

    print(f"Refactoring the model...")
    code = create_python_code(API_KEY_PATH, PY_REFACTOR, BIG_MODEL, output_folder, model_units[i])
    codes.append(code)

    print(f"Processing algorithmic metadata...")
    algo = create_algo_metadata(API_KEY_PATH, ALGO_META, BIG_MODEL, output_folder, code, model_units[i])
    algo_metas.append(algo)

    print(f"Generating XML file for the model unit {i+1} : {model_unit_name}...")
    if model_composite is None :
      XML_units.append(json_to_XML_unit(model_units[0], output_folder, metadata, algo))
    else :
      XML_units.append(json_to_XML_unit(model_composite, output_folder, metadata, algo))

  # Process model composite
  print(f"Generating the composite model...")
  composite_metadata = create_composite_metadata(API_KEY_PATH, COMPOSITE_META, SMALL_MODEL, output_folder, XML_units, model_composite)
  if model_composite is None :
    model_composite = model_units[0]
  xml_composite = json_to_XML_composite(model_composite, output_folder, composite_metadata, XML_units)

  # Create cookiecutter project
  print(f"Generating Crop2ML project for the model component")
  metadata = composite_metadata['metadata']
  cookiecutter(COOKIE_CUTTER_TEMPLATE, 
    no_input=True,
    overwrite_if_exists=True,
    extra_context={'project_name':Path(model_composite).stem, 
                  'repo_name':Path(model_composite).stem,
                  'author_name': metadata['Authors'],
                  'description': metadata['Extended description'], 
                  'open_source_license':"MIT"},
    output_dir=output_folder)
  
  # Move generated files to the cookiecutter project directory
  for xml_file in XML_units:
    shutil.copy(xml_file, f"{output_folder}/{Path(model_composite).stem}/crop2ml/")
  shutil.copy(xml_composite, f"{output_folder}/{Path(model_composite).stem}/crop2ml/")

  # Transpile each code to CyML
  print("Transpiling into CyML...")
  for i in range(len(codes)):
    transpile_functions(codes[i], algo_metas[i], desc_metas[i], API_KEY_PATH, BIG_MODEL, CYML_TRANSPILE, model_composite, output_folder)
