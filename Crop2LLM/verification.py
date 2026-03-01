import os
from path import Path
from pycropml.cyml import prefix
from pycropml.topology import Topology
from pycropml.pparse import model_parser
from pycropml import render_cyml
from pycropml.transpiler.main import Main
from pycropml import render_cyml
from pycropml.cyml import transpile_package
from openAI_interaction import debug_cyml_code_unit, debug_cyml_code_composite

#-----------------------------------------------------------------
# Transpile a Crop2ML component in the output folder each languages and platforms supported
#-----------------------------------------------------------------
def generate_component_all_languages(model_package, languages):
  for language in languages:
    print(f"Transpiling into {language}...")
    transpile_package(model_package, language)


#-----------------------------------------------------------------
# Function to check the syntax of the generated code files and the CROP2ML -> language/platform transformation
#-----------------------------------------------------------------
def check_code_generated(model_package, report_file):
  verif_result = False
  report_path = os.path.join(model_package, report_file)
  topology = Topology(model_package.split(os.path.sep)[-1], model_package)
  pkg = Path(model_package)
  output = Path(os.path.join(pkg, 'src'))
  models = model_parser(pkg)
  cyml_rep = Path(os.path.join(output, 'pyx'))

  try:
    m2p = render_cyml.Model2Package(models, dir=output)
    m2p.generate_package()  # generate cyml models in "pyx" directory
    with open(report_path, 'a') as rf:
      rf.write(f"Successfully generated pyx code of each model units.\n\n")
  except Exception as e:
    with open(report_path, 'a') as rf:
      rf.write(f"ERROR Generation when generating the pyx code of model units :\n{e}\n\n")
    raise
  
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

  # Check the modelComposite
  try:
    mc_name = topology.model.name
    T_pyx = topology.algo2cyml()
    fileT = Path(os.path.join(cyml_rep, f"{mc_name}Component.pyx"))
    with open(fileT, "wb") as tg_file:
      tg_file.write(T_pyx.encode('utf-8'))
    with open(report_path, 'a') as rf:
      rf.write(f"Successfully generated composite pyx code.\n\n")
  except Exception as e:
    with open(report_path, 'a') as rf:
      rf.write(f"ERROR Generation when generating the pyx code of the model composite :\n{e}\n\n")
    raise
  
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
def debug_code(api_key, debug_cyml, model, model_package, report_file):
  report_path = os.path.join(model_package, report_file)
  with open(report_path, 'r') as f:
    lines = f.readlines()
  for line in reversed(lines):

    if "ERROR ModelUnit" in line:
      parts = line.split('---')
      filename = parts[1].strip()
      cyml_path = os.path.join(model_package, 'src', 'pyx', filename)
      xml_path = os.path.join(model_package, 'crop2ml', f"unit.{filename.split('.')[0]}.xml")
      error_msg = "".join(lines[lines.index(line)+1:])
      response = debug_cyml_code_unit(api_key, debug_cyml, model, cyml_path, xml_path, error_msg)
      
      with open(report_path, 'a') as rf:
        rf.write(f"To debug this error, try :\n\n {response}\n")
      break

    elif "ERROR ModelComposite" in line:
      parts = line.split('---')
      filename = parts[1].strip()
      cyml_path = os.path.join(model_package, 'src', 'pyx', filename)
      base = filename.split('.')[0].replace("Component", "")
      xml_path = os.path.join(model_package, 'crop2ml', f"composition.{base}.xml")
      algo_metas = [os.path.join(model_package, 'crop2ml', f) for f in os.listdir(os.path.join(model_package, 'crop2ml')) if f.startswith("unit") and f.endswith(".xml")]
      error_msg = "".join(lines[lines.index(line)+1:])
      response = debug_cyml_code_composite(api_key, debug_cyml, model, cyml_path, algo_metas, xml_path, error_msg)
      
      with open(report_path, 'a') as rf:
        rf.write(f"To debug this error, try :\n\n {response}\n")
      break

    elif "ERROR Generation" in line:
      with open(report_path, 'a') as rf:
        rf.write(f"Error when generating the pyx code...")
      break