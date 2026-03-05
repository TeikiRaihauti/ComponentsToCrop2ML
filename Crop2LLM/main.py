import argparse
import os
from utilities import check_files
from generation import process_unit, process_composite, create_crop2ml_package
from verification import check_code_composite, debug_code, debug_xml, generate_component_all_languages, generate_pyx_composite, generate_pyx_unit, check_code_unit
import concurrent.futures

#-----------------------------------------------------------------
# CONFIGURATION
#-----------------------------------------------------------------
API_KEY_PATH = "./config/api_key.txt"
BIG_MODEL = "gpt-5.2"
SMALL_MODEL = "gpt-5-mini"
COOKIE_CUTTER_TEMPLATE = "./config/cookiecutter-crop2ml/"
LOG_FILE = "Crop2LLM_report.txt"
REPORT_FILE = "Transformation_report.txt"
# simplace/cpp to add
LANGUAGES = ['r', 'cs', 'py', 'f90', 'openalea', 'apsim', 'dssat', 'stics', 'bioma', 'sirius', 'java']
NUMBER_CANDIDATES = 5
MAX_PARALLEL_UNITS = 5
NUMBER_ITERATIONS = 5

UNIT_META = "./config/Agents/Agent-UnitMeta.txt"
COMPOSITE_META = "./config/Agents/Agent-CompositeMeta.txt"
PY_REFACTOR = "./config/Agents/Agent-PyRefactor.txt"
PY_CONSENSUS = "./config/Agents/Agent-PyConsensus.txt"
CYML_TRANSPILE = "./config/Agents/Agent-CyMLTranspile.txt"
ALGO_META = "./config/Agents/Agent-AlgoMeta.txt"
ALGO_CONSENSUS = "./config/Agents/Agent-AlgoConsensus.txt"
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
  ALGO_CONSENSUS,
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
          executor.submit(process_unit, API_KEY_PATH, UNIT_META, PY_REFACTOR, ALGO_META, CYML_TRANSPILE, ALGO_CONSENSUS, PY_CONSENSUS,
                          SMALL_MODEL, BIG_MODEL, NUMBER_CANDIDATES, LOG_FILE, grp, model_composite, output_folder)
          for idx, grp in enumerate(model_units)
        ]
        for fut in concurrent.futures.as_completed(futures):
          xml, functions = fut.result()
          XML_units.append(xml)
          functions_transpiled.append(functions)

      # Process model composite
      print(f"Generating the composite model...")
      composite_metadata, xml_composite, model_composite = process_composite(API_KEY_PATH, COMPOSITE_META, SMALL_MODEL, output_folder, XML_units, model_composite, LOG_FILE, model_units[0][0])

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

    print("Checking if code can be generated...")
    while not code_generated and iteration < NUMBER_ITERATIONS:
      iteration += 1
      with open(report_path, 'a') as rf:
        rf.write(f"GENERATING PYX CODE --- ATTEMPT {iteration} ---\n\n")
      try:
        code_generated = generate_pyx_unit(package, report_path)
      except Exception as e:
        print("Error during code generation, trying to fix it...")
        debug_xml(API_KEY_PATH, DEBUG_CYML, DEBUG_XML, APPLY_XML, APPLY_CODE, CODE_OR_XML, BIG_MODEL, package, report_path, True)

    if not code_generated:
      debug_xml(API_KEY_PATH, DEBUG_CYML, DEBUG_XML, APPLY_XML, APPLY_CODE, CODE_OR_XML, BIG_MODEL, package, report_path, False)
      print("Code generation failed. Please check the report for details.")
    
    iteration = 0
    print("Checking if code generated is correct...")
    while not verif_result and iteration < NUMBER_ITERATIONS:
      iteration += 1
      with open(report_path, 'a') as rf:
        rf.write(f"CHECKING CODE GENERATED --- ATTEMPT {iteration} ---\n\n")
      try:
        verif_result = check_code_unit(package, report_path)
      except Exception as e:
        print("Error during code verification, trying to fix it...")
        debug_code(API_KEY_PATH, DEBUG_CYML, APPLY_XML, APPLY_CODE, CODE_OR_XML, BIG_MODEL, package, report_path, True)
      
    if not verif_result:
      debug_code(API_KEY_PATH, DEBUG_CYML, DEBUG_XML, APPLY_XML, APPLY_CODE, CODE_OR_XML, BIG_MODEL, package, report_path, False)
      print("Code verification failed. Please check the report for details.")

    iteration = 0
    code_generated = False
    print("Checking if composite code can be generated...")
    while not code_generated and iteration < NUMBER_ITERATIONS:
      iteration += 1
      with open(report_path, 'a') as rf:
        rf.write(f"GENERATING COMPOSITE CODE --- ATTEMPT {iteration} ---\n\n")
      try:
        code_generated = generate_pyx_composite(package, report_path)
      except Exception as e:
        print("Error during code composite generation, trying to fix it...")
        debug_xml(API_KEY_PATH, DEBUG_CYML, DEBUG_XML, APPLY_XML, APPLY_CODE, CODE_OR_XML, BIG_MODEL, package, report_path, True)
      
    if not code_generated:
      debug_xml(API_KEY_PATH, DEBUG_CYML, DEBUG_XML, APPLY_XML, APPLY_CODE, CODE_OR_XML, BIG_MODEL, package, report_path, False)
      print("Code generation failed. Please check the report for details.")

    iteration = 0
    verif_result = False
    print("Checking if composite code generated is correct...")
    while not verif_result and iteration < NUMBER_ITERATIONS:
      iteration += 1
      with open(report_path, 'a') as rf:
        rf.write(f"CHECKING CODE COMPOSITE GENERATED --- ATTEMPT {iteration} ---\n\n")
      try:
        verif_result = check_code_composite(package, report_path)
      except Exception as e:
        print("Error during code verification, trying to fix it...")
        debug_code(API_KEY_PATH, DEBUG_CYML, DEBUG_XML, APPLY_XML, APPLY_CODE, CODE_OR_XML, BIG_MODEL, package, report_path, True)
      
    if not verif_result:
      debug_code(API_KEY_PATH, DEBUG_CYML, DEBUG_XML, APPLY_XML, APPLY_CODE, CODE_OR_XML, BIG_MODEL, package, report_path, False)
      print("Code verification failed. Please check the report for details.")
    else:
      print("All files parsed and AST generated successfully.")
      print("Generating the component in all languages...")
      generate_component_all_languages(package, LANGUAGES)
      print("Component generated successfully in all languages/platforms supported !")

  else:
    parser.error("At least one of --unit or --package must be provided.")