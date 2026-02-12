import argparse
import os
from path import Path
from pycropml.cyml import prefix
from pycropml.topology import Topology
from pycropml.pparse import model_parser
from pycropml import render_cyml
from pycropml.transpiler.main import Main
from pycropml import render_cyml
from pycropml.pparse import model_parser
from pycropml.cyml import transpile_package

#-----------------------------------------------------------------
# Function to check the syntax of the generated code files and the CROP2ML -> language/platform transformation
#-----------------------------------------------------------------
def check_code_generated(model_package, languages):
  topology = Topology(model_package.split(os.path.sep)[-1], model_package)
  pkg = Path(model_package)
  output = Path(os.path.join(pkg, 'src'))
  models = model_parser(pkg)

  m2p = render_cyml.Model2Package(models, dir=output)
  m2p.generate_package()  # generate cyml models in "pyx" directory

  cyml_rep = Path(os.path.join(output, 'pyx'))
  
  for language in languages:
    for k, file in enumerate(cyml_rep.files()):
      with open(file, 'r') as fi:
        source = fi.read()
      name = os.path.split(file)[1].split(".")[0]
      for model in models:  # in the case we haven't the same order
        if name.lower() == model.name.lower() and prefix(model) != "function":
          test = Main(file, language, model, topology.model.name)

          try:
            test.parse()
          except Exception as e:
            print(f"Error parsing {file} for language {language}: {e}")
            raise

          try:
            test.to_ast(source)
          except Exception as e:
            print(f"Error generating AST for {file} in language {language}: {e}")
            raise
          
          try:
            test.to_source()
          except Exception as e: 
            print(f"Error generating source code for {file} in language {language}: {e}") 
            raise


#-----------------------------------------------------------------
# Simulation section
#-----------------------------------------------------------------
LANGUAGES = ['cs','cpp','py','f90','java','simplace','sirius', 'openalea','apsim','dssat','stics','bioma']

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Package crop2ml")
  parser.add_argument('-p', '--package', required=True, help='Model package directory')
  args = parser.parse_args()
  package = args.package
  
  # Verify the transpiled code
  print("Checking if code generated is correct...")
  try:
    check_code_generated(package, LANGUAGES)
  except Exception as e:
    print(f"Error during transpilation: {e}")
    raise

  # Transpile in all languages
  for language in LANGUAGES:
    print(f"Transpiling into {language}...")
    transpile_package(package, language)