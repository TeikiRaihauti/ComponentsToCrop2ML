from path import Path
import os
import time
from cookiecutter.main import cookiecutter
import shutil
from openAI_interaction import create_composite_metadata, create_unit_metadata, create_python_code, create_algo_metadata, create_consensus_python
from json2XML import json_to_XML_composite, json_to_XML_unit
from transpiler import transpile_functions
import concurrent.futures
import pycropml
from pycropml.cyml import NAMES, prefix, ext, langs, domain_class, wrapper
from pycropml import render_cyml, nameconvention
from pycropml.code2nbk import Model2Nb
from pycropml.transpiler.generators.pythonGenerator import PythonSimulation
from pycropml.pparse import model_parser
from pycropml.topology import Topology
from pycropml.transpiler.main import Main
import re
import xml.etree.ElementTree as ET
from textwrap import dedent

#-----------------------------------------------------------------
# Function to transform a modelUnit in Crop2ML
#-----------------------------------------------------------------
def process_unit(api_key, unit_meta, py_refactor, algo_meta, cyml_transpile, py_consensus, 
                 small_model, big_model, number_candidates, log_file, group, model_composite, output_folder):
  main_file = group[0]
  helper_files = group[1:]
  model_unit_name = Path(main_file).stem
  codes = []

  # To delete
  start = time.time()

  print(f"Processing descriptive metadata of the model {model_unit_name}...")
  metadata = create_unit_metadata(api_key, unit_meta, small_model, output_folder, main_file, helper_files)

  print(f"Creating {number_candidates} candidates refactored python versions of the model {model_unit_name}...")
  with concurrent.futures.ThreadPoolExecutor() as executor:
    futures = []
    for _ in range(number_candidates):
      futures.append(
        executor.submit(create_python_code, api_key, py_refactor, big_model, main_file, helper_files)
        )
    for fut in concurrent.futures.as_completed(futures):
      code = fut.result()
      codes.append(code)

  print(f"Selecting the best candidate for the model {model_unit_name}...")
  code = create_consensus_python(api_key, py_consensus, big_model, codes, main_file, helper_files, output_folder)
  algo = create_algo_metadata(api_key, algo_meta, small_model, code)

  # To delete
  end = time.time()
  print(f"Time elapsed for processing {model_unit_name}: {end - start} seconds")
  start = time.time()

  print(f"Transpiling each function into CyML of the model {model_unit_name}...")
  functions = transpile_functions(code, algo, metadata, api_key, big_model, cyml_transpile, output_folder)

  # To delete
  end = time.time()
  print(f"Time elapsed for transpiling {model_unit_name}: {end - start} seconds")
  
  if model_composite is None:
    xml = json_to_XML_unit(main_file, output_folder, metadata, algo, log_file)
  else:
    xml = json_to_XML_unit(model_composite, output_folder, metadata, algo, log_file)

  print(f"{model_unit_name} generated successfully !")

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


#-----------------------------------------------------------------
# Transpile a Crop2ML component in the output folder for a specific language or  platform
#-----------------------------------------------------------------
def generate_component(model_package, language):
  namep = model_package.split(os.path.sep)[-1]
  pkg = Path(model_package)
  models = model_parser(pkg)  # parse xml files and create python model object
  output = Path(os.path.join(pkg, 'src'))
  dir_test = Path(os.path.join(pkg, 'test'))
  dir_doc = Path(os.path.join(pkg, 'doc'))

  dir_images = Path(os.path.join(dir_doc, 'images'))
  if not dir_images.is_dir():
      dir_images.mkdir()

  m2p = render_cyml.Model2Package(models, dir=output)
  tg_rep1 = Path(os.path.join(output, language))  # target language models  directory in output
  dir_test_lang = Path(os.path.join(dir_test, language))
  
  if not tg_rep1.is_dir():
    tg_rep1.mkdir()

  namep_ = namep.replace("-", "_")
  tg_rep = Path(os.path.join(tg_rep1, namep_))
  if not tg_rep.is_dir():
    tg_rep.mkdir()

  if not dir_test_lang.is_dir():
    dir_test_lang.mkdir()

  m2p.write_tests()

  # create topology of composite model
  T = Topology(namep, model_package)
  T.topologicalSort()
  mc_name = T.model.name

  # domain class
  if language in domain_class:
    getattr(getattr(pycropml.transpiler.generators, f'{NAMES[language]}Generator'), f'to_struct_{language}')([T.model], tg_rep, mc_name)
  # wrapper
  if language in wrapper:
    getattr(getattr(pycropml.transpiler.generators, f'{NAMES[language]}Generator'), f'to_wrapper_{language}')(T.model, tg_rep, mc_name)
  
  cyml_rep = Path(os.path.join(output, 'pyx'))
  # Transform model unit to languages and platforms
  for k, file in enumerate(cyml_rep.files()):
    with open(file, 'r') as fi:
      source = fi.read()
    name = os.path.split(file)[1].split(".")[0]
    for model in models:
      if name.lower() == model.name.lower() and prefix(model) != "function":
        test = Main(file, language, model, T.model.name)
        test.parse()
        test.to_ast(source)
        code = test.to_source()
        filename = Path(
          os.path.join(tg_rep, f"{nameconvention.signature(model, ext[language])}.{ext[language]}"))
        with open(filename, "wb") as tg_file:
          tg_file.write(code.encode('utf-8'))
        if language in langs:
          Model2Nb(model, code, name, dir_test_lang).generate_nb(language, tg_rep, namep, mc_name)

  # Create Cyml Composite model
  filename = Path(os.path.join(tg_rep, f"{mc_name}Component.{ext[language]}"))
  compoPath = Path(os.path.join(cyml_rep, f"{mc_name}Component.pyx"))
  with open(compoPath, 'r') as fi:
    source = fi.read()
  test = Main(source, language, T.model, T.model.name)
  test.parse()
  test.to_ast(source)
  code = test.translate()
  if code:
    with open(filename, "wb") as tg_file:
      tg_file.write(code.encode('utf-8'))

  # create computing algorithm
  if language == "py":
    simulation = PythonSimulation(T.model, package_name=namep)
    simulation.generate()
    code = ''.join(simulation.result)
    filename = Path(os.path.join(tg_rep, "simulation.py"))
    initfile = Path(os.path.join(tg_rep, "__init__.py"))
    with open(filename, "wb") as tg_file:
      tg_file.write(code.encode("utf-8"))
    with open(initfile, "wb") as tg_file:
      tg_file.write("".encode("utf-8"))

    setup = PythonSimulation(T.model, package_name=namep)
    setup.generate_pyproject()
    code = ''.join(setup.result)
    setupfile = Path(os.path.join(tg_rep1, "pyproject.toml"))
    with open(setupfile, "wb") as tg_file:
      tg_file.write(code.encode("utf-8"))


#-----------------------------------------------------------------
# When the pyx code is fixed, parse and format it into the crop2ml folder
#-----------------------------------------------------------------
def maj_component(package, pyx_folder, crop2ml_folder):
  pyx_files = [f for f in os.listdir(pyx_folder) if f.endswith('.pyx')]
  component_name = Path(package).stem + 'Component.pyx'
  if component_name in pyx_files:
    pyx_files.remove(component_name)

  for pyx_file in pyx_files:
    pyx_path = os.path.join(pyx_folder, pyx_file)
    with open(pyx_path, 'r') as f:
      content = f.read()

    functions = extract_functions(content)

    basename = os.path.splitext(pyx_file)[0]
    xml_file = f"unit.{basename}.xml"
    xml_path = os.path.join(crop2ml_folder, xml_file)
    inputs = set()
    outputs = set()

    if os.path.exists(xml_path):
      tree_xml = ET.parse(xml_path)
      root = tree_xml.getroot()
      for inp in root.findall(".//Input"):
        name = inp.get('name')
        inputs.add(name)
      for out in root.findall(".//Output"):
        name = out.get('name')
        outputs.add(name)

    for func_name, body_source in functions:
      if func_name.startswith('init_'):
        # No signature, no return
        dedented = filter_and_clean_body(body_source, inputs, outputs)

        out_file = os.path.join(crop2ml_folder, 'algo', 'pyx', f"{func_name}.pyx")
        with open(out_file, 'w') as f:
          f.write(dedented)

        if os.path.exists(xml_path):
          for init in root.findall(".//Initialization"):
            init.set('filename', f"algo/pyx/{func_name}.pyx")
            init.set('name', f"{func_name}")
          tree_xml.write(xml_path)

      elif func_name.startswith('model_'):
        # No signature, no return, strip first 6 chars from name ("model_" → "")
        dedented = filter_and_clean_body(body_source, inputs, outputs)

        file_name = func_name[6:]  # remove "model_" prefix
        out_file = os.path.join(crop2ml_folder, 'algo', 'pyx', f"{file_name}.pyx")
        with open(out_file, 'w') as f:
          f.write(dedented)

        if os.path.exists(xml_path):
          for algo in root.findall(".//Algorithm"):
            algo.set('filename', f"algo/pyx/{file_name}.pyx")
          tree_xml.write(xml_path)

      else:
        # Keep full function source as-is (re-extract with signature)
        full_func_pattern = re.compile(
          rf'^(?:cp?def\s+(?:\w+\s+)?|def\s+){re.escape(func_name)}\s*\(.*?\)\s*(?:->.*?)?:\s*\n(?:[ \t]+.+\n?)*',
          re.MULTILINE
        )
        match = full_func_pattern.search(content)
        if match:
          func_source = match.group(0)
          out_file = os.path.join(crop2ml_folder, 'algo', 'pyx', f"{func_name}.pyx")
          with open(out_file, 'w') as f:
            f.write(func_source)


#-----------------------------------------------------------------
# Extract each functions from a pyx file
#-----------------------------------------------------------------
def extract_functions(content):
  functions = []
  lines = content.split('\n')
  
  i = 0
  while i < len(lines):
    line = lines[i]
    match = re.match(r'^(cp?def|def)\s+(?:[\w\[\]* ]+\s+)?(\w+)\s*\(', line)
    if match:
      func_name = match.group(2)
        
      # Handle multi-line signature: keep reading until we find the closing '):' 
      while i < len(lines) and not re.search(r'\).*:\s*$', lines[i]):
        i += 1
      i += 1  # skip the closing line of the signature
      
      # Collect the body (all indented lines after the signature)
      body_lines = []
      while i < len(lines):
        if lines[i].strip() == '' or lines[i].startswith(' ') or lines[i].startswith('\t'):
          body_lines.append(lines[i])
          i += 1
        else:
          break
      functions.append((func_name, '\n'.join(body_lines)))
    else:
      i += 1
  
  return functions


#-----------------------------------------------------------------
# Clean and format each functions depending inputs/outputs of the XML + clean signature and return
#-----------------------------------------------------------------
def filter_and_clean_body(body_source, inputs, outputs):
  body_source = re.sub(r'""".*?"""', '', body_source, flags=re.DOTALL)
  
  lines = body_source.split('\n')
  
  last_return_idx = None
  for idx, line in enumerate(lines):
    if line.strip().startswith('return'):
      last_return_idx = idx
  
  filtered_lines = []
  for idx, line in enumerate(lines):
    stripped = line.strip()
    if stripped.startswith('cdef'):
      match = re.match(r'cdef\s+\w+\s+(\w+)', stripped)
      if match and match.group(1) in (inputs | outputs):
          continue
    if idx == last_return_idx:
      continue
    filtered_lines.append(line)
  
  return dedent('\n'.join(filtered_lines))