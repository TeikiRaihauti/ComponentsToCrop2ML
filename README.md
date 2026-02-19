# Code to Crop2ML - Documentation

## Overview

We developed a workflow as a Python script that automates the conversion of crop model source code into the **Crop2ML** standardized format. It leverages OpenAI's GPT model to refactor, analyze, and document source code through agent-based processing to complete a Crop2ML project structure.

## Purpose

The script facilitates the transformation of crop model implementations, written in various programming languages and software architectures. This process includes:

- **Code Analysis & Documentation**: Extract metadata and create comprehensive descriptions
- **Code Refactoring**: Convert source code to standardized Python modules, in a functional structure
- **Algorithmic Metadata Generation**: Extract algorithm inputs and outputs and parameters
- **XML Generation**: Create Crop2ML-compliant XML model descriptions
- **Project Generation**: Build complete Crop2ML project structures using cookiecutter
- **Code Transpilation**: Convert Python modules to CyML (Crop2ML Language)

## Usage

### Command Line Interface

```bash
python code_to_Crop2ml.py -u <unit_file> [-u <unit_file2> ...] [-c <composite_file>] -o <output_folder>
```

### Arguments

- **`-u, --unit`** (required, multiple): Model unit source file(s) to process
- **`-c, --composite`** (optional): Composite model file (defines how units connect)
- **`-o, --output`** (required): Output folder where results will be saved

### Examples

#### Single Model Unit Processing
```bash
python code_to_Crop2ml.py -u soil_temperature.java -o ./output
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

Each agent configuration file should contain detailed instructions for the respective GPT agent:

- **Agent-UnitMeta.txt**: Instructions to extract model metadata (title, authors, description, etc.)
- **Agent-PyRefactor.txt**: Instructions to refactor code to standardized Python format
- **Agent-AlgoMeta.txt**: Instructions to analyze algorithm structure (init, process, inputs, outputs, tests)
- **Agent-CyMLTranspile.txt**: Instructions to convert Python to CyML
- **Agent-CompositeMeta.txt**: Instructions to analyze composite model structure and links
- **API_KEY_PATH**: The path of the OpenAi API's key
