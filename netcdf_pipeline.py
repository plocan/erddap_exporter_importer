import os
import glob
import sys
import subprocess
import json
import xarray as xr
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

# --- PATH CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent
UTILS_DIR = BASE_DIR / "external" / "Utils"
HARMONIZER_DIR = BASE_DIR / "external" / "metadata-harmonizer"

sys.path.append(str(UTILS_DIR))

try:
    from complete_metadata.complete_metadata import complete_metadata_dict, extract_func
    from yaml_generator.yaml_generator import process_json
    from netcdf_to_csv.netcdf_to_csv import export_to_csv
except ImportError as e:
    print(f"❌ Error when importing Utils: {e}")
    sys.exit(1)

# ---------------------------------------------------------
# 🟢 HELPER FUNCTION: Suggest Dataset ID
# ---------------------------------------------------------
def _suggest_dataset_id(nc_path: str) -> str:
    """Genera un DatasetID sugerido basado en fechas y variables del NC inicial."""
    try:
        with xr.open_dataset(nc_path) as ds:
            # 1. Extract dates
            date_start_str = "XXXXXX"
            date_end_str = "XXXXXX"
            
            # Find 'time' or 'TIME'
            t_var = 'time' if 'time' in ds.variables else ('TIME' if 'TIME' in ds.variables else None)
            
            if t_var and ds[t_var].size > 0:
                time_values = ds[t_var].values
                start_time = time_values.min()
                end_time = time_values.max()

                # Format to YYYYMMDD
                date_start_str = str(start_time.astype('datetime64[D]')).replace('-', '')
                date_end_str = str(end_time.astype('datetime64[D]')).replace('-', '')

            # 2. Extract Variables
            exclude_names = {
                'time', 'latitude', 'longitude', 'depth', 
                'sensor_id', 'platform_id', 'station_name',
                'TIME', 'LATITUDE', 'LONGITUDE', 'DEPTH'
            }
            
            data_vars = []
            for var_name in ds.data_vars:
                if var_name not in exclude_names and not var_name.endswith('_QC'):
                    data_vars.append(var_name)
                    
            variables_str = '-'.join(sorted(data_vars))
            if not variables_str: variables_str = 'NOVAR'

            # 3. Extract depth info
            depth_suffix = ""
            v_max = ds.attrs.get("geospatial_vertical_max", 0)
            
            try:
                depth_val = abs(float(v_max))
                # If the absolute depth is greater than 5m, add the suffix
                if depth_val > 5:
                    depth_suffix = f"_{round(depth_val)}m"
                elif depth_val <= 5:
                    depth_suffix = "_surface"
            except (ValueError, TypeError):
                # If the metadata doesn't exist or is not numeric, do nothing
                pass

            # 3. Build Dataset ID
            return f"OS_ESTOC_{date_start_str}-{date_end_str}_D_{variables_str}{depth_suffix}"

    except Exception as e:
        print(f"⚠️ WARNING: Suggested Dataset ID could not be generated: {e}")
        return Path(nc_path).stem
    

def run_pipeline(input_nc, template_json, sensors_csv, output_base_dir):    
    dataset_id = _suggest_dataset_id(input_nc)
    print(f"\n Suggested Dataset ID: {dataset_id}")
    
    # Create the workflow folder in the destination chosen by the user
    work_dir = Path(output_base_dir) / f"WORKFLOW_{Path(input_nc).stem}"
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[1/5] 📝 Step 1: Completing metadata...")
    meta_raw = extract_func(input_nc)
    meta_final = complete_metadata_dict(meta_raw, template_json, sensors_csv)
    
    json_path = work_dir / f"{Path(input_nc).stem}_metadata.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(meta_final, f, indent=4, ensure_ascii=False)

    print(f"\n[2/5] 📂 Step 2: Generating YAML files...")
    process_json(str(json_path))
    yaml_dir = work_dir / Path(json_path).stem

    print(f"\n[3/5] 📊 Step 3: Exporting data to CSV...")
    export_to_csv(input_nc, str(json_path), str(work_dir))

    print(f"\n[4/5] Step 4: Executing Generator (EMSO)...")
    nc_final = work_dir / f"{dataset_id}.nc"

# 1. Search for all YAML files (explicit list)
    yaml_files = glob.glob(str(yaml_dir / "*.yaml"))
    
    # 2. Search for all CSV files (explicit list)
    # This avoids trying to read the JSON or subdirectories as data
    csv_files = glob.glob(str(work_dir / "*.csv"))
    
    if not yaml_files:
        raise FileNotFoundError(f"No YAML files were found in {yaml_dir}")
    if not csv_files:
        raise FileNotFoundError(f"No CSV files were found in {work_dir}")

    # 3. Build the command with expanded lists
    comando_generator = [
        "python", str(HARMONIZER_DIR / "generator.py"),
        "-d"
    ]
    comando_generator.extend(csv_files)  # Add the CSV files one by one
    
    comando_generator.append("-m")
    comando_generator.extend(yaml_files) # Add the YAML files one by one
    
    comando_generator.extend(["--out", str(nc_final)])

    # 4. Execution with debug info
    print(f"DEBUG: Sending {len(csv_files)} CSV files and {len(yaml_files)} YAML files.")
    subprocess.run(comando_generator, check=True)

    print(f"\n[5/5] Step 5: Generating ERDDAP configuration XML...")
    xml_output = work_dir / f"{dataset_id}.xml"

    subprocess.run([
        "python", str(HARMONIZER_DIR / "erddap_config.py"),
        str(nc_final),
        dataset_id,
        "/datasets/test",
        "-o", str(xml_output)
    ], check=True)

    messagebox.showinfo("Done", f"Pipeline completed successfully.\nResults in: {work_dir}")


def get_user_inputs():
    """It opens windows for selecting files and folders"""
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True) # It ensures the window stays on top

    print("📂 Selecting input files...")
    
    nc_in = filedialog.askopenfilename(title="1. Select the initial NetCDF file", filetypes=[("NetCDF", "*.nc")])
    if not nc_in: return None
    
    json_maestro = filedialog.askopenfilename(title="2. Select the JSON template", filetypes=[("JSON", "*.json")])
    if not json_maestro: return None
    
    sensors_csv = filedialog.askopenfilename(title="3. Select the list of Sensors (CSV)", filetypes=[("CSV", "*.csv")])
    if not sensors_csv: return None
    
    output_target = filedialog.askdirectory(title="4. Select where to save the results folder")
    if not output_target: return None

    return nc_in, json_maestro, sensors_csv, output_target


if __name__ == "__main__":
    inputs = get_user_inputs()
    if inputs:
        nc, js, csv, out = inputs
        try:
            run_pipeline(nc, js, csv, out)
        except Exception as e:
            messagebox.showerror("Error", f"Error during execution:\n{e}")
    else:
        print("Execution cancelled by the user.")