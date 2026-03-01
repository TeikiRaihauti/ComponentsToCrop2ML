from pathlib import Path
from cookiecutter.main import cookiecutter
import shutil
from openAI_interaction import create_composite_metadata, create_unit_metadata, create_python_code, create_algo_metadata, create_consensus_python
from json2XML import json_to_XML_composite, json_to_XML_unit
from transpiler import transpile_functions
import concurrent.futures


#-----------------------------------------------------------------
# Function to transform a modelUnit in Crop2ML
#-----------------------------------------------------------------
def process_unit(api_key, unit_meta, py_refactor, algo_meta, cyml_transpile, algo_consensus, py_consensus, 
                 small_model, big_model, number_candidates, log_file, group, model_composite, output_folder):
  main_file = group[0]
  helper_files = group[1:]
  model_unit_name = Path(main_file).stem
  codes = []

  print(f"Processing descriptive metadata of the model {model_unit_name}...\n")
  metadata = create_unit_metadata(api_key, unit_meta, small_model, output_folder, main_file, helper_files)

  print(f"Creating {number_candidates} candidates refactored python versions of the model {model_unit_name}...\n")
  with concurrent.futures.ThreadPoolExecutor() as executor:
    futures = []
    for _ in range(number_candidates):
      futures.append(
        executor.submit(create_python_code, api_key, py_refactor, big_model, output_folder, main_file, helper_files)
        )
    for fut in concurrent.futures.as_completed(futures):
      code = fut.result()
      codes.append(code)

  print(f"Selecting the best candidate for the model {model_unit_name}...\n")
  code = create_consensus_python(api_key, py_consensus, big_model, codes, main_file, helper_files, output_folder)
  algo = create_algo_metadata(api_key, algo_meta, big_model, output_folder, code, main_file)

  print(f"Transpiling each function into CyML of the model {model_unit_name}...\n")
  functions = transpile_functions(code, algo, metadata, api_key, big_model, cyml_transpile, output_folder)

  if model_composite is None:
    xml = json_to_XML_unit(main_file, output_folder, metadata, algo, log_file)
  else:
    xml = json_to_XML_unit(model_composite, output_folder, metadata, algo, log_file)

  print(f"{model_unit_name} generated successfully !\n")

  return xml, functions


#-----------------------------------------------------------------
# Function to create a modelComposite in Crop2ML
#-----------------------------------------------------------------
def process_composite(api_key, composite_meta, small_model, output_folder, xml_units, model_composite, log_file, first_file):
  composite_metadata = create_composite_metadata(api_key, composite_meta, small_model, output_folder, xml_units, model_composite)
  if model_composite is None :
    model_composite = first_file
  xml_composite = json_to_XML_composite(model_composite, output_folder, composite_metadata, xml_units, log_file)

  return composite_metadata, xml_composite, model_composite


#-----------------------------------------------------------------
# Function to create a Crop2ML package
#-----------------------------------------------------------------
def create_crop2ml_package(cookiecutter_template, output_folder, model_composite, composite_metadata, XML_units, xml_composite, functions_transpiled, log_file):
  metadata = composite_metadata['metadata']
  project_dir = f"{output_folder}/{Path(model_composite).stem}"
  if Path(project_dir).exists():
    shutil.rmtree(project_dir)

  cookiecutter(cookiecutter_template, 
    no_input=True,
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

  for function_transpiled in functions_transpiled:
    for function in function_transpiled:
      shutil.copy(function, f"{output_folder}/{Path(model_composite).stem}/crop2ml/algo/pyx/")

  shutil.copy(f"{output_folder}/{log_file}", f"{output_folder}/{Path(model_composite).stem}/")

  return project_dir