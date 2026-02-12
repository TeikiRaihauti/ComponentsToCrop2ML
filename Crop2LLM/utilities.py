import os
from pathlib import Path

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
# Function to check if all files exist and are correctly read
#-----------------------------------------------------------------
def check_files(*args, comp, config_files):
  for file_path in args:
    if not os.path.exists(file_path):
      raise FileNotFoundError(f"File {file_path} does not exist")
    try:
      with open(file_path, 'r', encoding='utf-8') as f:
        f.read()
    except Exception as e:
      raise ValueError(f"Cannot read file {file_path}: {e}")
    
    if comp is None:
      continue
    else :
      if not os.path.exists(comp):
        raise FileNotFoundError(f"File {comp} does not exist")
      try:
        with open(file_path, 'r', encoding='utf-8') as f:
          f.read()
      except Exception as e:
        raise ValueError(f"Cannot read file {file_path}: {e}")
  
  for file_path in config_files:
    if not os.path.exists(file_path):
      raise FileNotFoundError(f"Configuration file {file_path} does not exist")
    # Skip reading if it's a directory, only read if it's a file
    if os.path.isfile(file_path):
      try:
        with open(file_path, 'r', encoding='utf-8') as f:
          f.read()
      except Exception as e:
        raise ValueError(f"Cannot read configuration file {file_path}: {e}")