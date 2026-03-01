# Code to Crop2ML - Documentation

## Overview
We developed a workflow as a Python script that automates the conversion of crop model source code into the **Crop2ML** standardized format. It leverages OpenAI's GPT model to refactor, analyze, and document source code through an agent-based workflow to generate a complete Crop2ML package.

## Purpose
The script facilitates the transformation of crop model implementations, written in various programming languages and software architectures into Crop2ML, therefore **facilitates crop model component exchange**. This process includes:

- **Code Analysis & Documentation**: Extract metadata and create comprehensive descriptions
- **Code Refactoring**: Convert source code to standardized Python modules, in a functional structure
- **Algorithmic Metadata Generation**: Extract algorithm inputs, outputs and parameters
- **XML Generation**: Create Crop2ML-compliant XML model descriptions
- **Code Transpilation**: Convert Python modules to CyML (Crop2ML Language)
- **Project Generation**: Build complete Crop2ML project structures using cookiecutter

## Usage

### Command Line Interface

**From platform to Crop2ML**
```bash
python crop2LLM.py -u <unit_file> <helper_file> ... [-u <unit_file2> ...] [-c <composite_file>] -o <output_folder>
```

- **`-u, --unit`** (required, multiple): Model unit source file(s) to process
- **`-c, --composite`** (optional): Composite model file (defines how units connect)
- **`-o, --output`** (required): Output folder where results will be saved

**From Crop2ML to platform**
```bash
python crop2LLM.py -p <Crop2ML package>
```
- **`-p, --package`** (required): The Crop2ML package to transform in all languages/platforms supported


### Examples

#### Single Model Unit Processing
```bash
python crop2LLM.py -u soil_temperature.java -o ./output
```
Processes a single soil temperature model file and generates a Crop2ML component.

#### Multiple Model Units (Composite Model)
```bash
python code_to_Crop2ml.py -u growth.py -u stress.py -u weather.py -c composite.json -o ./output
```
Processes three model units and combines them into a composite model using the composite.json configuration.

#### Multiple Model Units separated in different files
```bash
python code_to_Crop2ml.py -u surface_temperature.cs surface_temperature_info.txt -u soil_layers_temeprature.cs soil_layers_temperature_structure.json -o ./output
```
Generates a soil temperature model combining surface and soil layers temperature modules.


## Configuration Files Required
- **API_KEY_PATH**: The path of the OpenAi API's key
