import sys
import subprocess
import glob
import xarray as xr
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

# --- PATH CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent.parent
HARMONIZER_DIR = BASE_DIR / "external" / "metadata-harmonizer"

def _suggest_dataset_id(nc_path: str) -> str:
    """
    It generates a dataset ID based on dates and ONLY data variable names.
    Filters out sensors and platform metadata to avoid long names.
    """
    try:
        with xr.open_dataset(nc_path) as ds:
            # 1. Extract Dates
            date_start_str, date_end_str = "XXXXXX", "XXXXXX"
            t_var = 'time' if 'time' in ds.variables else ('TIME' if 'TIME' in ds.variables else None)
            
            if t_var and ds[t_var].size > 0:
                time_values = ds[t_var].values
                date_start_str = str(time_values.min().astype('datetime64[D]')).replace('-', '')
                date_end_str = str(time_values.max().astype('datetime64[D]')).replace('-', '')

            # 2. Extract ONLY data variables
            exclude_names = {
                'time', 'latitude', 'longitude', 'depth', 'TIME', 'LATITUDE', 'LONGITUDE', 'DEPTH',
                'sensor_id', 'platform_id', 'station_name', 'POSITION_QC', 'TIME_QC', 'DEPTH_QC'
            }

            # Filters: Not in exclude_names, doesn't end in _QC, and not a long sensor ID
            data_vars = []
            for v in ds.data_vars:
                if v not in exclude_names and not v.endswith('_QC') and len(v) < 15:
                    data_vars.append(v)
            
            variables_str = '-'.join(sorted(data_vars))
            if not variables_str: variables_str = 'DATA'
            
            if len(variables_str) > 60:
                variables_str = variables_str[:57] + "..."

            # 3. Depth Logic
            depth_suffix = ""
            v_max = ds.attrs.get("geospatial_vertical_max", 0)
            try:
                depth_val = abs(float(v_max))
                if depth_val > 5:
                    depth_suffix = f"_{round(depth_val)}m"
                elif depth_val <= 5:
                    depth_suffix = "_surface"
            except: pass

            return f"OS_ESTOC_{date_start_str}-{date_end_str}_D_{variables_str}{depth_suffix}"
    except Exception as e:
        print(f"⚠️ Error suggesting ID: {e}")
        return Path(nc_path).stem[:50]
    

def run_generator_and_configurator(csv_folder, yaml_folder, output_dir):
    try:
        work_dir = Path(output_dir)
        # We use a short temporary filename for the initial processing step
        temp_nc = work_dir / "processing_file.nc"

        # --- GENERATOR ---
        print(f"\n[1/2] ⚙️ Executing Generator...")
        csv_files = glob.glob(str(Path(csv_folder) / "*.csv"))
        yaml_files = glob.glob(str(Path(yaml_folder) / "*.yaml"))

        if not csv_files or not yaml_files:
            raise FileNotFoundError("No CSV or YAML files found in the selected folders.")

        # Construction of the command
        cmd_gen = ["python", str(HARMONIZER_DIR / "generator.py"), "-d"] 
        cmd_gen.extend(csv_files)
        cmd_gen.append("-m")
        cmd_gen.extend(yaml_files)
        cmd_gen.extend(["--out", str(temp_nc)])

        subprocess.run(cmd_gen, check=True)

        # --- GENERATING CLEAN DATASET ID ---
        dataset_id = _suggest_dataset_id(str(temp_nc))
        final_nc = work_dir / f"{dataset_id}.nc"

        # Rename the file to the clean dataset ID
        if final_nc.exists(): final_nc.unlink() # Delete if already exists
        temp_nc.rename(final_nc)
        print(f"💎 Final Dataset ID: {dataset_id}")

        # --- ERDDAP CONFIG ---
        print(f"\n[2/2] 📋 Generating datasets.xml...")
        xml_output = work_dir / f"{dataset_id}.xml"

        subprocess.run([
            "python", str(HARMONIZER_DIR / "erddap_config.py"),
            str(final_nc), dataset_id, "/datasets/test", "-o", str(xml_output)
        ], check=True)

        messagebox.showinfo("Success", f"End of pipeline.\n\nFile: {dataset_id}.nc\nFolder: {work_dir}")

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n{e}")

def get_user_inputs():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    csv_dir = filedialog.askdirectory(title="1. Folder with CSV files")
    if not csv_dir: return None

    yaml_dir = filedialog.askdirectory(title="2. Folder with YAML files")
    if not yaml_dir: return None

    output_target = filedialog.askdirectory(title="3. Destination folder for output files")
    if not output_target: return None

    return csv_dir, yaml_dir, output_target

if __name__ == "__main__":
    inputs = get_user_inputs()
    if inputs:
        run_generator_and_configurator(*inputs)