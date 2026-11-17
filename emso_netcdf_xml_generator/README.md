# EMSO NetCDF & ERDDAP XML Generator

This script automates the generation of **NetCDF files** and corresponding **ERDDAP `datasets.xml` configurations** from CSV data and YAML metadata, using the EMSO **metadata-harmonizer** tools `generator.py`and `erddap_config.py`.

It provides a simple **GUI-based workflow** (folder selection dialogs) and produces:
- A harmonized NetCDF file with a clean, meaningful dataset ID
- An ERDDAP-compatible XML configuration file

## IMPORTANT NOTES

* CSV and YAML files must be compatible with the metadata-harmonizer tools (you can find some examples within the `examples/workflow_output` folder on this repo).
* ERDDAP dataset path is currently hardcoded as `/datasets/test`. You might change it in line 102 of `emso_netcdf_xml_generator.py`, or by manually editing the final XML.
* The beginning of the dataset ID is currently hardcoded as `OS_ESTOC_` to reference our platform. You might change it in line 58 of `emso_netcdf_xml_generator.py`, or by manually changing the filename.


## Expected Directory Structure

```text
project/
├── emso_netcdf_xml_generator/
|   └── emso_netcdf_xml_generator.py
└── external/
    └── metadata-harmonizer/
        ├── generator.py
        └── erddap_config.py
```

##  Inputs

When running the script, you will be asked to select:

1. **CSV folder**
   - One or more `.csv` files containing the data
2. **YAML folder**
   - One or more `.yaml` metadata files
3. **Output folder**
   - Destination for the generated `.nc` and `.xml` files

##  How to Run

```bash

python emso_netcdf_xml_generator.py

```
A sequence of dialogs will guide you through the process.
