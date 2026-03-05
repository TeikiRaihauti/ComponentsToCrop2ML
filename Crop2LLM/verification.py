import os
from path import Path
import pycropml
from pycropml.cyml import NAMES, prefix, ext, langs, domain_class, wrapper
from pycropml.topology import Topology
from pycropml.pparse import model_parser
from pycropml import render_cyml, nameconvention
from pycropml.transpiler.main import Main
from pycropml.code2nbk import Model2Nb
from pycropml.transpiler.generators.pythonGenerator import PythonSimulation
from openAI_interaction import create_debug_code_composite, create_debug_code_unit, create_debug_xml_composite, create_debug_xml_unit

#-----------------------------------------------------------------
# Transpile a Crop2ML component in the output folder each languages and platforms supported
#-----------------------------------------------------------------
def generate_component_all_languages(model_package, languages):
  for language in languages:
    print(f"Transpiling into {language}...")
    
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
      name = os.path.split(file)[1].split(".")[0]
      for model in models:
        if name.lower() == model.name.lower() and prefix(model) != "function":
          test = Main(file, language, model, T.model.name)
          code = test.to_source()
          filename = Path(
            os.path.join(tg_rep, f"{nameconvention.signature(model, ext[language])}.{ext[language]}"))
          with open(filename, "wb") as tg_file:
            tg_file.write(code.encode('utf-8'))
          if language in langs:
            Model2Nb(model, code, name, dir_test_lang).generate_nb(language, tg_rep, namep, mc_name)

    # Create Cyml Composite model
    filename = Path(os.path.join(tg_rep, f"{mc_name}Component.{ext[language]}"))
    code = T.compotranslate(language).encode('utf-8')
    if code:
      with open(filename, "wb") as tg_file:
        tg_file.write(code)

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
# Function to check if the pyx code of each model unit can be generated
#-----------------------------------------------------------------
def generate_pyx_unit(model_package, report_path):
  code_generated = False
  pkg = Path(model_package)
  output = Path(os.path.join(pkg, 'src'))
  models = model_parser(pkg)
  m2p = render_cyml.Model2Package(models, dir=output)

  try:
    for model in models:          
      m2p.generate_component(model)
    m2p.generate_package()  # generate cyml models in "pyx" directory
    with open(report_path, 'a') as rf:
      rf.write(f"Successfully generated pyx code of each model units.\n\n")
      code_generated = True
  except Exception as e:
    with open(report_path, 'a') as rf:
      rf.write(f"ERROR ModelUnit-Generation when generating pyx code --- {model.name} ---:\n{e}\n\n")
    raise
  return code_generated


#-----------------------------------------------------------------
# Function to check if the pyx code of model composite can be generated
#-----------------------------------------------------------------
def generate_pyx_composite(model_package, report_path):
  code_generated = False
  topology = Topology(model_package.split(os.path.sep)[-1], model_package)
  pkg = Path(model_package)
  output = Path(os.path.join(pkg, 'src'))
  cyml_rep = Path(os.path.join(output, 'pyx'))

  try:
    mc_name = topology.model.name
    T_pyx = topology.algo2cyml()
    fileT = Path(os.path.join(cyml_rep, f"{mc_name}Component.pyx"))
    with open(fileT, "wb") as tg_file:
      tg_file.write(T_pyx.encode('utf-8'))
    with open(report_path, 'a') as rf:
      rf.write(f"Successfully generated composite pyx code.\n\n")
    code_generated = True
  except Exception as e:
    with open(report_path, 'a') as rf:
      rf.write(f"ERROR ModelComposite-Generation when generating the pyx code of the model composite :\n{e}\n\n")
    raise

  return code_generated


#-----------------------------------------------------------------
# Function to check the syntax of the generated code files and the CROP2ML -> language/platform transformation
#-----------------------------------------------------------------
def check_code_unit(model_package, report_path):
  verif_result = False
  topology = Topology(model_package.split(os.path.sep)[-1], model_package)
  pkg = Path(model_package)
  output = Path(os.path.join(pkg, 'src'))
  models = model_parser(pkg)
  cyml_rep = Path(os.path.join(output, 'pyx'))
  
  # Check each modelUnit
  for k, file in enumerate(cyml_rep.files()):
    with open(file, 'r') as fi:
      source = fi.read()
    name = os.path.split(file)[1].split(".")[0]
    for model in models:
      if name.lower() == model.name.lower() and prefix(model) != "function":
        test = Main(file, 'cs', model, topology.model.name)

        try:
          test.parse()
          with open(report_path, 'a') as rf:
            rf.write(f"Successfully parsed {os.path.basename(file)}\n\n")
        except Exception as e:
          with open(report_path, 'a') as rf:
            rf.write(f"ERROR ModelUnit when parsing --- {os.path.basename(file)} ---\n{e}\n\n")
          raise

        try:
          test.to_ast(source)
          with open(report_path, 'a') as rf:
            rf.write(f"Successfully generated AST for {os.path.basename(file)}\n\n")
        except Exception as e:
          with open(report_path, 'a') as rf:
            rf.write(f"ERROR ModelUnit when generating AST --- {os.path.basename(file)} ---\n{e}\n\n")
          raise
  verif_result = True
  return verif_result


#-----------------------------------------------------------------
# Function to check the syntax of the generated composite and the CROP2ML -> language/platform transformation
#-----------------------------------------------------------------
def check_code_composite(model_package, report_path):
  verif_result = False
  topology = Topology(model_package.split(os.path.sep)[-1], model_package)
  mc_name = topology.model.name
  T_pyx = topology.algo2cyml()
  test = Main(T_pyx, 'cs', topology.model, topology.model.name)

  try:
    test.parse()
    with open(report_path, 'a') as rf:
      rf.write(f"Successfully parsed composite model --- {mc_name}Component.pyx ---\n\n")
  except Exception as e:
    with open(report_path, 'a') as rf:
      rf.write(f"ERROR ModelComposite when parsing --- {mc_name}Component.pyx --- :\n{e}\n\n")
    raise

  try:
    test.to_ast(T_pyx)
    with open(report_path, 'a') as rf:
      rf.write(f"Successfully generated the AST for the composite model --- {mc_name}Component.pyx ---\n\n")
  except Exception as e:
    with open(report_path, 'a') as rf:
      rf.write(f"ERROR ModelComposite when generating the AST --- {mc_name}Component.pyx --- :\n{e}\n\n")
    raise

  with open(report_path, 'a') as rf:
    rf.write("All files parsed and AST generated successfully.\n")
    verif_result = True

  return verif_result


#-----------------------------------------------------------------
# Function to check if the code generated in the output folder is correct by verifying the syntax and AST of the generated files
#-----------------------------------------------------------------
def debug_code(api_key, debug_cyml, apply_xml, apply_code, code_or_xml, model, model_package, report_path, apply_correction):
  with open(report_path, 'r') as f:
    lines = f.readlines()
  for line in reversed(lines):

    if "ERROR ModelUnit" in line:
      parts = line.split('---')
      filename = parts[1].strip()
      cyml_path = os.path.join(model_package, 'src', 'pyx', filename)
      xml_path = os.path.join(model_package, 'crop2ml', f"unit.{filename.split('.')[0]}.xml")
      error_msg = "".join(lines[lines.index(line)+1:])
      response, response_xml, response_code, file_to_modify = create_debug_code_unit(
                                                              api_key, debug_cyml, code_or_xml, apply_code,
                                                              apply_xml, model, cyml_path, xml_path, 
                                                              error_msg, apply_correction)
      break

    elif "ERROR ModelComposite" in line:
      parts = line.split('---')
      filename = parts[1].strip()
      cyml_path = os.path.join(model_package, 'src', 'pyx', filename)
      base = filename.split('.')[0].replace("Component", "")
      xml_path = os.path.join(model_package, 'crop2ml', f"composition.{base}.xml")
      algo_metas = [os.path.join(model_package, 'crop2ml', f) for f in os.listdir(os.path.join(model_package, 'crop2ml')) if f.startswith("unit") and f.endswith(".xml")]
      error_msg = "".join(lines[lines.index(line)+1:])
      response, response_xml, response_code, file_to_modify = create_debug_code_composite(
                                                              api_key, debug_cyml, code_or_xml, apply_code,
                                                              apply_xml, model, cyml_path, xml_path, algo_metas,
                                                              error_msg, apply_correction)
      break

  if apply_correction:
    if file_to_modify == "XML" or file_to_modify == "BOTH":
      with open(xml_path, 'w') as rf:
        rf.write(response_xml)
    if file_to_modify == "CODEBASE" or file_to_modify == "BOTH":
      with open(cyml_path, 'w') as rf:
        rf.write(response_code)
    
  else :
    with open(report_path, 'a') as rf:
      rf.write(f"To debug this error, try :\n\n {response}\n")


#-----------------------------------------------------------------
# Function to check if the code generated in the output folder is correct by verifying the syntax and AST of the generated files
#-----------------------------------------------------------------
def debug_xml(api_key, debug_xml, apply_xml, model, model_package, report_path, apply_correction):
  with open(report_path, 'r') as f:
    lines = f.readlines()
  for line in reversed(lines):

    if "ERROR ModelUnit-Generation" in line:
      parts = line.split('---')
      filename = parts[1].strip()
      xml_path = os.path.join(model_package, 'crop2ml', f"unit.{filename.split('.')[0]}.xml")
      error_msg = "".join(lines[lines.index(line)+1:])
      response = create_debug_xml_unit(api_key, debug_xml, apply_xml, model, xml_path, error_msg, apply_correction)
      break

    elif "ERROR ModelComposite-Generation" in line:
      parts = line.split('---')
      filename = parts[1].strip()
      base = filename.split('.')[0].replace("Component", "")
      xml_path = os.path.join(model_package, 'crop2ml', f"composition.{base}.xml")
      algo_metas = [os.path.join(model_package, 'crop2ml', f) for f in os.listdir(os.path.join(model_package, 'crop2ml')) if f.startswith("unit") and f.endswith(".xml")]
      error_msg = "".join(lines[lines.index(line)+1:])
      response = create_debug_xml_composite(api_key, debug_xml, apply_xml, model, xml_path, algo_metas, error_msg, apply_correction)
      break

  if apply_correction:
    with open(xml_path, 'w') as rf:
      rf.write(response)
  else:
    with open(report_path, 'a') as rf:
      rf.write(f"To debug this error, try :\n\n {response}\n")