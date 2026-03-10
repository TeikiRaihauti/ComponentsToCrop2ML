import argparse
import os
import sys
from utilities import check_files
from generation import maj_component, process_unit, process_composite, create_crop2ml_package, generate_component
from verification import check_code_composite, debug_code, debug_xml, generate_pyx_composite, generate_pyx_unit, check_code_unit
import concurrent.futures
import time

#-----------------------------------------------------------------
# CONFIGURATION
#-----------------------------------------------------------------
API_KEY_PATH = "./config/api_key.txt"
BIG_MODEL = "gpt-5.3-codex"
SMALL_MODEL = "gpt-5-mini"
COOKIE_CUTTER_TEMPLATE = "./config/cookiecutter-crop2ml/"
LOG_FILE = "Crop2LLM_report.txt"
REPORT_FILE = "Transformation_report.txt"
LANGUAGES = ['r', 'cs', 'py', 'f90', 'apsim', 'dssat', 'stics', 'bioma', 'sirius', 'java', 'openalea', 'simplace','cpp']
NUMBER_CANDIDATES = 3
MAX_PARALLEL_UNITS = 5
NUMBER_ITERATIONS = 20

UNIT_META = "./config/Agents/Agent-UnitMeta.txt"
COMPOSITE_META = "./config/Agents/Agent-CompositeMeta.txt"
PY_REFACTOR = "./config/Agents/Agent-PyRefactor.txt"
PY_CONSENSUS = "./config/Agents/Agent-PyConsensus.txt"
CYML_TRANSPILE = "./config/Agents/Agent-CyMLTranspile.txt"
ALGO_META = "./config/Agents/Agent-AlgoMeta.txt"
DEBUG_CYML = "./config/Agents/Agent-DebugCode.txt"
DEBUG_XML = "./config/Agents/Agent-DebugXML.txt"
APPLY_CODE = "./config/Agents/Agent-ApplyCode.txt"
APPLY_XML = "./config/Agents/Agent-ApplyXML.txt"
CODE_OR_XML = "./config/Agents/Agent-CodeOrXML.txt"
CONFIG_FILES = [
  API_KEY_PATH,
  UNIT_META,
  COMPOSITE_META,
  PY_REFACTOR,
  PY_CONSENSUS,
  CYML_TRANSPILE,
  ALGO_META,
  DEBUG_CYML,
  DEBUG_XML,
  APPLY_CODE,
  APPLY_XML,
  CODE_OR_XML
]

#-----------------------------------------------------------------
# Simulation section
# Generate a complete Crop2ML component from model units and composite in the output folder defined
#-----------------------------------------------------------------
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Transform crop model components into Crop2ML component and vice-versa.")
  parser.add_argument('-u', '--unit', action='append', nargs='+', required=False, help='Model unit files (can be specified multiple times)')
  parser.add_argument('-c', '--composite', required=False, help='Model composite file')
  parser.add_argument('-o', '--output', required=False, help='Output folder')
  parser.add_argument('-p', '--package', required=False, help='Model package directory')
  args = parser.parse_args()

  if args.unit is not None :
    if args.package is not None :
      parser.error("You must choose between --unit and --package, not both.")

    elif args.output is None:
      parser.error("Output folder must be specified when using --unit.")

    #-----------------------------------------------------------------
    # SECTION : From crop model component to Crop2ML 
    else :
      model_units = args.unit
      model_composite = args.composite
      output_folder = args.output
      XML_units = []
      codes = []
      functions_transpiled = []

      check_files(*model_units, comp=model_composite, config_files=CONFIG_FILES, log_file=LOG_FILE, output_folder=output_folder)

      # Process each model unit concurrently
      print("Generating modelunits...")
      with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_PARALLEL_UNITS) as executor:
        futures = [
          executor.submit(process_unit, API_KEY_PATH, UNIT_META, PY_REFACTOR, ALGO_META, CYML_TRANSPILE, PY_CONSENSUS,
                          SMALL_MODEL, BIG_MODEL, NUMBER_CANDIDATES, LOG_FILE, grp, model_composite, output_folder)
          for idx, grp in enumerate(model_units)
        ]
        for fut in concurrent.futures.as_completed(futures):
          xml, functions = fut.result()
          XML_units.append(xml)
          functions_transpiled.append(functions)

      # To delete
      start = time.time()

      # Process model composite
      print(f"Generating the composite model...")
      composite_metadata, xml_composite, model_composite = process_composite(API_KEY_PATH, COMPOSITE_META, SMALL_MODEL, output_folder, XML_units, model_composite, LOG_FILE, model_units[0][0])
      
      # To delete
      end = time.time()
      print(f"Time elapsed for processing composite: {end - start} seconds")
      
      # Create cookiecutter project
      print(f"Generating Crop2ML project for the model component...")
      project_dir = create_crop2ml_package(COOKIE_CUTTER_TEMPLATE, output_folder, model_composite, composite_metadata, XML_units, xml_composite, functions_transpiled, LOG_FILE)

      print(f"Crop2ML package generated successfully in {project_dir} !")
      print(f"Check {LOG_FILE} for more details during the automatic transformation !")

  #-----------------------------------------------------------------
  # SECTION : From Crop2ML to crop model component
  elif args.package is not None:
    package = args.package
    verif_result = False
    code_generated = False
    iteration = 0
    report_path = os.path.join(package, REPORT_FILE)

    check_files([], comp=None, config_files=CONFIG_FILES, log_file=REPORT_FILE, output_folder=package)

    # To delete
    start = time.time()

    print("Checking code generated...")
    while not code_generated and iteration < NUMBER_ITERATIONS:
      iteration += 1
      with open(report_path, 'a') as rf:
        rf.write(f"GENERATING PYX CODE --- ATTEMPT {iteration} ---\n\n")
      try:
        code_generated = generate_pyx_unit(package, report_path)
      except Exception as e:
        print("Error during code generation, trying to fix it...")
      if not code_generated:
        debug_xml(API_KEY_PATH, DEBUG_XML, APPLY_XML, BIG_MODEL, package, report_path, iteration < NUMBER_ITERATIONS)

    if not code_generated:
      print("Code generation failed. Please check the report for details.")
      sys.exit()
    
    iteration = 0
    while not verif_result and iteration < NUMBER_ITERATIONS:
      iteration += 1
      with open(report_path, 'a') as rf:
        rf.write(f"CHECKING CODE GENERATED --- ATTEMPT {iteration} ---\n\n")
      try:
        verif_result = check_code_unit(package, report_path)
      except Exception as e:
        print("Error during code verification, trying to fix it...")
      if not verif_result:
        debug_code(API_KEY_PATH, DEBUG_CYML, APPLY_XML, APPLY_CODE, CODE_OR_XML, BIG_MODEL, package, report_path, iteration < NUMBER_ITERATIONS)
      
    if not verif_result:
      print("Code verification failed. Please check the report for details.")
      sys.exit()

    iteration = 0
    code_generated = False
    while not code_generated and iteration < NUMBER_ITERATIONS:
      iteration += 1
      with open(report_path, 'a') as rf:
        rf.write(f"GENERATING COMPOSITE CODE --- ATTEMPT {iteration} ---\n\n")
      try:
        code_generated = generate_pyx_composite(package, report_path)
      except Exception as e:
        print("Error during code composite generation, trying to fix it...")
      if not code_generated:
        debug_xml(API_KEY_PATH, DEBUG_CYML, DEBUG_XML, APPLY_XML, APPLY_CODE, CODE_OR_XML, BIG_MODEL, package, report_path, iteration < NUMBER_ITERATIONS)
      
    if not code_generated:
      print("Code generation failed. Please check the report for details.")
      sys.exit()

    iteration = 0
    verif_result = False
    while not verif_result and iteration < NUMBER_ITERATIONS:
      iteration += 1
      with open(report_path, 'a') as rf:
        rf.write(f"CHECKING CODE COMPOSITE GENERATED --- ATTEMPT {iteration} ---\n\n")
      try:
        verif_result = check_code_composite(package, report_path)
      except Exception as e:
        print("Error during code verification, trying to fix it...")
      if not verif_result:
        debug_code(API_KEY_PATH, DEBUG_CYML, APPLY_XML, APPLY_CODE, CODE_OR_XML, BIG_MODEL, package, report_path, iteration < NUMBER_ITERATIONS)
      
    if not verif_result:
      print("Code verification failed. Please check the report for details.")
      sys.exit()

    else:
      print("All files parsed and AST generated successfully.")
      pyx_folder = os.path.join(package, 'src', 'pyx')
      crop2ml_folder = os.path.join(package, 'crop2ml')
      maj_component(package, pyx_folder, crop2ml_folder)

      for language in LANGUAGES:
        print(f"Transpiling into {language}...")
        try:
          generate_component(package, language)
          with open(report_path, 'a') as rf:
            rf.write(f"Component generated successfully in {language}.\n")
        except Exception as e:
          with open(report_path, 'a') as rf:
            rf.write(f"Error occurred while generating component for {language}: \n{e}\n")
          continue
    
    # To delete
      end = time.time()
      print(f"Time elapsed for debugging: {end - start} seconds")

  else:
    parser.error("At least one of --unit or --package must be provided.")



  #generate_component(package, "bioma")