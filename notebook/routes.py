from fastapi import APIRouter, Request, UploadFile, File, BackgroundTasks, HTTPException, Form
from typing import List, Dict, Any
from pydantic import BaseModel
import nbformat
from nbformat.v4 import new_notebook, new_code_cell
import subprocess
import json
import pandas as pd
import asyncio
import logging
from contextlib import contextmanager
import os
import textwrap
import base64
import glob


# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

router = APIRouter()

@contextmanager
def cleanup_files(*files):
    try:
        yield
    finally:
        for file in files:
            try:
                if os.path.exists(file):
                    os.remove(file)
                    logger.debug(f"Cleaned up file: {file}")
            except Exception as e:
                logger.error(f"Error cleaning up {file}: {str(e)}")

class AnalysisRequest(BaseModel):
    reqs: str
    scripts: str

@router.post("/analyze-data")
def data_analysis(
    reqs: str = Form(...),
    scripts: str = Form(...),
    files: List[UploadFile] = File(...)
):
    logger.info("Starting data analysis request")
    logger.debug(f"Received requirements: {reqs}")
    logger.debug(f"Received scripts: {scripts}")
    logger.debug(f"Received files: {[f.filename for f in files]}")

    temp_files = []
    notebook_filename = 'temp_notebook.ipynb'
    executed_notebook_filename = 'executed_notebook.ipynb'
    output_dir = '/notebook_output'
    
    results = {}
    
    try:
        # Create base output directory with full permissions
        os.makedirs(output_dir, mode=0o777, exist_ok=True)
        logger.debug(f"Created base output directory: {output_dir}")
        
        # Parse the JSON strings into Python dictionaries
        logger.debug("Attempting to parse JSON data")
        try:
            reqs_dict = json.loads(reqs)
            scripts_dict = json.loads(scripts)
            logger.debug(f"Successfully parsed JSON. Requirements keys: {list(reqs_dict.keys())}")
            logger.debug(f"Scripts keys: {list(scripts_dict.keys())}")
            
            # Create table-specific directories with full permissions
            for table_name in scripts_dict.keys():
                table_dir = os.path.join(output_dir, table_name)
                os.makedirs(table_dir, mode=0o777, exist_ok=True)
                logger.debug(f"Created table-specific directory: {table_dir}")

                # Fix the script to use correct path
                modified_script = scripts_dict[table_name]
                modified_script = modified_script.replace(
                    f"'{table_name}/{table_name}_figure_",
                    f"'/notebook_output/{table_name}/{table_name}_figure_"
                )
                modified_script = modified_script.replace(
                    f"'/notebook_output/{table_name}/notebook_output/{table_name}/",
                    f"'/notebook_output/{table_name}/"
                )
                scripts_dict[table_name] = modified_script
                logger.debug(f"Updated script paths for {table_name}")

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid JSON format: {str(e)}")

        if not files:
            logger.error("No files were provided in the request")
            raise HTTPException(status_code=400, detail="No files were provided")
            
        dfs = {}
        # Create temporary directory for CSV files
        logger.debug("Creating temporary directory for CSV files")
        os.makedirs("temp_csv", exist_ok=True)
        
        for file in files:
            logger.info(f"Processing file: {file.filename}")
            # Extract the original table name from the file key (remove 'file_' prefix)
            table_name = file.filename
            if table_name.startswith('file_'):
                table_name = table_name[5:]  # Remove 'file_' prefix
                logger.debug(f"Extracted table name: {table_name} from filename: {file.filename}")
            
            try:
                # Synchronously read file contents
                contents = file.file.read()
                logger.debug(f"Successfully read contents of file: {file.filename}")
            except Exception as e:
                logger.error(f"Error reading file {file.filename}: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Error reading file {file.filename}: {str(e)}")

            # Save CSV to temporary file
            temp_csv = f"temp_csv/{table_name}.csv"
            logger.debug(f"Saving contents to temporary file: {temp_csv}")
            try:
                with open(temp_csv, "wb") as f:
                    f.write(contents)
                temp_files.append(temp_csv)
                logger.debug(f"Successfully saved file: {temp_csv}")
            except Exception as e:
                logger.error(f"Error saving temporary file {temp_csv}: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error saving temporary file: {str(e)}")

            # Read the CSV file
            try:
                logger.debug(f"Attempting to read CSV file: {temp_csv}")
                dfs[table_name] = pd.read_csv(temp_csv)
                logger.debug(f"Successfully loaded DataFrame for {table_name} with shape {dfs[table_name].shape}")
            except Exception as e:
                logger.error(f"Error reading CSV file {table_name}: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Error reading CSV file {table_name}: {str(e)}")
            
        if not dfs:
            logger.error("No valid CSV files were processed")
            raise HTTPException(status_code=400, detail="No valid CSV files were processed")
            
        for tablename in dfs.keys():    
            logger.info(f"Processing table: {tablename}")
            if tablename not in reqs_dict:
                logger.error(f"No requirements found for table {tablename}")
                raise HTTPException(status_code=400, detail=f"No requirements found for table {tablename}")
            if tablename not in scripts_dict:
                logger.error(f"No script found for table {tablename}")
                raise HTTPException(status_code=400, detail=f"No script found for table {tablename}")
                
            requirements = reqs_dict[tablename]
            script = scripts_dict[tablename]
            logger.debug(f"Requirements for {tablename}: {requirements}")
            logger.debug(f"Script length for {tablename}: {len(script)}")
            
            # Create a new notebook
            logger.debug("Creating new notebook")
            nb = new_notebook()

            # Add cells to notebook
            logger.debug("Adding cells to notebook")
            # First cell: Install requirements
            install_cell = new_code_cell(f"""%%time
!pip install {requirements}""")
            nb.cells.append(install_cell)
            
            # Second cell: Import statements and setup
            setup_cell = new_code_cell("""import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os

%matplotlib inline
plt.style.use('seaborn-v0_8')

# Create output directory for figures in shared volume
os.makedirs('/notebook_output', exist_ok=True)""")
            nb.cells.append(setup_cell)
            
            # Third cell: Load df

            df_code = textwrap.dedent(f"""
                # Load and preview the df
                {tablename} = pd.read_csv('temp_csv/{tablename}.csv')
                print("data shape:", {tablename}.shape)
                print("\\nFirst few rows:")
                print({tablename}.head())
                print("Columns:", {tablename}.columns.tolist())
            """)
            
            df_cell = new_code_cell(df_code)

            nb.cells.append(df_cell)

            # Fourth cell: Modify the script to use the shared volume output directory
            # Create subdirectory for each table in the output dir
            table_dir_cell = new_code_cell(f"""
            # Create subdirectory for {tablename} if it doesn't exist
            os.makedirs('/notebook_output/{tablename}', exist_ok=True)
            """)
            nb.cells.append(table_dir_cell)
            
            # Update the script to use the shared volume path
            modified_script = script.replace("'{tablename}/", "'/notebook_output/{tablename}/")
            modified_script = modified_script.replace("notebook_output/", "/notebook_output/")
            script_cell = new_code_cell(modified_script)
            nb.cells.append(script_cell)

            # Write the notebook to a file
            logger.debug(f"Writing notebook to file: {notebook_filename}")
            try:
                with open(notebook_filename, 'w') as f:
                    nbformat.write(nb, f)
                temp_files.append(notebook_filename)
                logger.debug(f"Successfully wrote notebook to {notebook_filename}")
            except Exception as e:
                logger.error(f"Error writing notebook file: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error writing notebook file: {str(e)}")

            # Execute the notebook using synchronous subprocess
            logger.info("Executing notebook")
            try:
                import subprocess
                
                cmd = [
                    'jupyter', 'nbconvert', 
                    '--to', 'notebook',
                    '--execute',
                    '--ExecutePreprocessor.timeout=600',  # Increased to 10 minutes
                    notebook_filename,
                    '--output', executed_notebook_filename
                ]
                
                logger.debug(f"Running command: {' '.join(cmd)}")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=600  # Added 10 minute timeout for the subprocess itself
                )
                
                stdout_text = result.stdout
                stderr_text = result.stderr
                
                logger.debug(f"Notebook execution stdout:\n{stdout_text}")
                if stderr_text:
                    logger.error(f"Notebook execution stderr:\n{stderr_text}")
                
                if result.returncode != 0:
                    error_msg = stderr_text or "Unknown error"
                    logger.error(f"Notebook execution failed with return code {result.returncode}. Error: {error_msg}")
                    raise HTTPException(status_code=500, detail=f"Notebook execution failed: {error_msg}")

                temp_files.append(executed_notebook_filename)
                logger.info("Notebook execution completed successfully")

            except Exception as e:
                logger.error(f"Error during notebook execution: {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Error during notebook execution: {str(e)}")
            
        # Simply return success since files are saved in volume
        return {
            "message": "Analysis completed successfully",
            "status": "success"
        }
    
    except Exception as e:
        logger.error(f"Unexpected error in data analysis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up only temporary files, not output files
        for file in temp_files:
            try:
                if os.path.exists(file) and ('temp_' in file or file in [notebook_filename, executed_notebook_filename]):
                    os.remove(file)
                    logger.debug(f"Cleaned up temporary file: {file}")
            except Exception as e:
                logger.error(f"Error cleaning up {file}: {str(e)}")



@router.post("/train-data")
def train_data(
    reqs: str = Form(...),
    scripts: str = Form(...),
    file: UploadFile = File(...)
):
    logger.info("Starting training data request")
    logger.debug(f"Received requirements: {reqs}")
    logger.debug(f"Received scripts: {scripts}")
    logger.debug(f"Received file: {file.filename}")

    temp_files = []
    notebook_filename = 'temp_training_notebook.ipynb'
    executed_notebook_filename = 'executed_training_notebook.ipynb'
    output_dir = '/notebook_output'
    
    try:
        # Create base output directory with full permissions
        os.makedirs(output_dir, mode=0o777, exist_ok=True)
        logger.debug(f"Created base output directory: {output_dir}")
        
        # Create temporary directory for CSV files
        logger.debug("Creating temporary directory for CSV files")
        os.makedirs("temp_csv", exist_ok=True)
        
        # Process the single file
        table_name = file.filename
        if table_name.startswith('file_'):
            table_name = table_name[5:]  # Remove 'file_' prefix
            logger.debug(f"Extracted table name: {table_name} from filename: {file.filename}")
        
        try:
            # Synchronously read file contents
            contents = file.file.read()
            logger.debug(f"Successfully read contents of file: {file.filename}")
        except Exception as e:
            logger.error(f"Error reading file {file.filename}: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Error reading file {file.filename}: {str(e)}")

        # Save CSV to temporary file
        temp_csv = f"temp_csv/{table_name}.csv"
        logger.debug(f"Saving contents to temporary file: {temp_csv}")
        try:
            with open(temp_csv, "wb") as f:
                f.write(contents)
            temp_files.append(temp_csv)
            logger.debug(f"Successfully saved file: {temp_csv}")
        except Exception as e:
            logger.error(f"Error saving temporary file {temp_csv}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error saving temporary file: {str(e)}")

        # Read the CSV file with memory optimization
        try:
            logger.debug(f"Attempting to read CSV file with memory optimization: {temp_csv}")
            # Use low_memory=True and chunk processing for large files
            try:
                # First check file size
                file_size_mb = os.path.getsize(temp_csv) / (1024 * 1024)
                logger.debug(f"CSV file size: {file_size_mb:.2f} MB")
                
                # If file is large, use chunks to read
                if file_size_mb > 100:  # More than 100MB
                    logger.info(f"Large CSV detected ({file_size_mb:.2f} MB), using chunked reading")
                    
                    # Count the lines to display progress
                    with open(temp_csv, 'r') as f:
                        line_count = sum(1 for _ in f)
                    logger.debug(f"CSV has {line_count} lines")
                    
                    # Read in smaller chunks
                    chunk_size = min(100000, max(1000, line_count // 10))
                    logger.debug(f"Reading in chunks of {chunk_size} rows")
                    
                    df = pd.read_csv(temp_csv, low_memory=True, chunksize=chunk_size)
                    df = pd.concat([chunk for chunk in df], ignore_index=True)
                else:
                    df = pd.read_csv(temp_csv, low_memory=True)
            except Exception as chunk_err:
                logger.warning(f"Chunked reading failed: {str(chunk_err)}, falling back to standard reading")
                df = pd.read_csv(temp_csv)
                
            # Memory optimization for numeric columns
            for col in df.columns:
                if df[col].dtype == 'float64':
                    df[col] = pd.to_numeric(df[col], downcast='float')
                elif df[col].dtype == 'int64':
                    df[col] = pd.to_numeric(df[col], downcast='integer')
                elif df[col].dtype == 'object':
                    if df[col].nunique() < df.shape[0] // 2:
                        df[col] = df[col].astype('category')
                        
            logger.debug(f"Successfully loaded optimized DataFrame for {table_name} with shape {df.shape}")
        except Exception as e:
            logger.error(f"Error reading CSV file {table_name}: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Error reading CSV file {table_name}: {str(e)}")
        
        # Create a new notebook
        logger.debug("Creating new notebook")
        nb = new_notebook()
        
        # Table subdirectory
        os.makedirs(f"{output_dir}/{table_name}", mode=0o777, exist_ok=True)

        # Add cells to notebook
        logger.debug("Adding cells to notebook")
        # First cell: Install requirements - Using the requirements string directly
        install_cell = new_code_cell(f"""%%time
!pip install {reqs} psutil""")
        nb.cells.append(install_cell)
        
        # Second cell: Import statements and setup with memory monitoring
        setup_cell = new_code_cell("""import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
import gc
import psutil

%matplotlib inline
plt.style.use('seaborn-v0_8')

# Create output directory for figures in shared volume
os.makedirs('/notebook_output', exist_ok=True)

# Monitor memory usage
def get_memory_usage():
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    return f"Current memory usage: {mem_info.rss / (1024 * 1024):.2f} MB"

print(get_memory_usage())

# Memory optimization function
def optimize_dataframe_memory(df):
    start_mem = df.memory_usage().sum() / (1024*1024)
    print(f"DataFrame memory usage before optimization: {start_mem:.2f} MB")
    
    for col in df.columns:
        if df[col].dtype == 'float64':
            df[col] = pd.to_numeric(df[col], downcast='float')
        elif df[col].dtype == 'int64':
            df[col] = pd.to_numeric(df[col], downcast='integer')
        elif df[col].dtype == 'object':
            if df[col].nunique() < df.shape[0] // 2:
                df[col] = df[col].astype('category')
                
    end_mem = df.memory_usage().sum() / (1024*1024)
    print(f"DataFrame memory usage after optimization: {end_mem:.2f} MB")
    print(f"Memory decreased by {(start_mem - end_mem) / start_mem * 100:.1f}%")
    
    return df

# Memory safety for array operations
def safe_operation(operation_description, func, *args, **kwargs):
    try:
        print(f"Attempting: {operation_description}")
        print(f"Memory before: {get_memory_usage()}")
        result = func(*args, **kwargs)
        print(f"Memory after: {get_memory_usage()}")
        print(f"{operation_description} completed successfully")
        return result
    except Exception as e:
        print(f"Error in {operation_description}: {str(e)}")
        gc.collect()
        print(f"Memory after error & garbage collection: {get_memory_usage()}")
        raise
""")
        nb.cells.append(setup_cell)
        
        # Third cell: Load df with memory optimization
        df_code = textwrap.dedent(f"""
            # Load and preview the df with memory optimization
            print("Loading dataframe...")
            {table_name} = pd.read_csv('temp_csv/{table_name}.csv')
            print("Initial load complete")
            print(f"Original shape: {{{table_name}.shape}}")
            
            # Run garbage collection to free memory from read_csv operations
            gc.collect()
            print(get_memory_usage())
            
            # Apply memory optimization
            {table_name} = optimize_dataframe_memory({table_name})
            
            # Sample data if it's too large
            if {table_name}.shape[0] > 100000:
                print(f"Dataframe is large ({{{table_name}.shape[0]}} rows), sampling 100,000 rows for analysis")
                {table_name}_full = {table_name}  # Keep reference to full dataset
                {table_name} = {table_name}.sample(n=100000, random_state=42)
                print(f"Sampled shape: {{{table_name}.shape}}")
            
            print("\\nFirst few rows:")
            print({table_name}.head())
            print("Columns:", {table_name}.columns.tolist())
            
            # Run garbage collection again
            gc.collect()
            print(get_memory_usage())
        """)
        
        df_cell = new_code_cell(df_code)
        nb.cells.append(df_cell)

        # Fourth cell: Create subdirectory for output
        table_dir_cell = new_code_cell(f"""
        # Create subdirectory for {table_name} if it doesn't exist
        os.makedirs('/notebook_output/{table_name}', exist_ok=True)
        """)
        nb.cells.append(table_dir_cell)
        
        # Add memory profiling around user script
        script_wrapper = f"""
# Before script execution
print("\\n--- Starting user script execution ---")
print(get_memory_usage())

try:
    # Original user script
{textwrap.indent(scripts, '    ')}
    
    # After script execution
    print("\\n--- User script completed successfully ---")
except Exception as script_error:
    print(f"\\n--- Error in user script: {{str(script_error)}} ---")
    # Try to continue and avoid full notebook failure
    
# Force garbage collection
gc.collect()
print(f"Final memory usage: {{get_memory_usage()}}")
"""
        
        modified_script = script_wrapper.replace(f"'{table_name}/", f"'/notebook_output/{table_name}/")
        modified_script = modified_script.replace("notebook_output/", "/notebook_output/")
        script_cell = new_code_cell(modified_script)
        nb.cells.append(script_cell)

        # Write the notebook to a file
        logger.debug(f"Writing notebook to file: {notebook_filename}")
        try:
            with open(notebook_filename, 'w') as f:
                nbformat.write(nb, f)
            temp_files.append(notebook_filename)
            logger.debug(f"Successfully wrote notebook to {notebook_filename}")
        except Exception as e:
            logger.error(f"Error writing notebook file: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error writing notebook file: {str(e)}")

        # Execute the notebook using synchronous subprocess
        logger.info("Executing training notebook")
        try:
            import subprocess
            
            cmd = [
                'jupyter', 'nbconvert', 
                '--to', 'notebook',
                '--execute',
                '--ExecutePreprocessor.timeout=600',  # 10 minutes
                '--ExecutePreprocessor.allow_errors=True',  # Continue on cell errors
                notebook_filename,
                '--output', executed_notebook_filename
            ]
            
            logger.debug(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=600  # 10 minute timeout
            )
            
            stdout_text = result.stdout
            stderr_text = result.stderr
            
            logger.debug(f"Notebook execution stdout:\n{stdout_text}")
            if stderr_text:
                logger.error(f"Notebook execution stderr:\n{stderr_text}")
            
            if result.returncode != 0:
                error_msg = stderr_text or "Unknown error"
                logger.error(f"Training notebook execution failed with return code {result.returncode}. Error: {error_msg}")
                raise HTTPException(status_code=500, detail=f"Training notebook execution failed: {error_msg}")

            temp_files.append(executed_notebook_filename)
            logger.info("Training notebook execution completed successfully")

        except Exception as e:
            logger.error(f"Error during training notebook execution: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error during training notebook execution: {str(e)}")
        
        # Extract metrics from executed notebook before cleanup
        metrics = {}
        training_log = ""
        try:
            if os.path.exists(executed_notebook_filename):
                with open(executed_notebook_filename, 'r', encoding='utf-8') as nb_file:
                    executed_nb = nbformat.read(nb_file, as_version=4)

                for cell in executed_nb.cells:
                    if cell.cell_type == 'code' and hasattr(cell, 'outputs'):
                        for output in cell.outputs:
                            text = ""
                            if output.output_type == 'stream' and hasattr(output, 'text'):
                                text = output.text
                            elif output.output_type == 'execute_result' and 'text/plain' in output.get('data', {}):
                                text = output['data']['text/plain']
                            training_log += text

                            if '###METRICS_START###' in text:
                                try:
                                    start = text.index('###METRICS_START###') + len('###METRICS_START###')
                                    end = text.index('###METRICS_END###')
                                    metrics_json = text[start:end].strip()
                                    # Sanitize common JSON issues from numpy
                                    metrics_json = metrics_json.replace('NaN', 'null').replace('Infinity', '"Infinity"').replace('-Infinity', '"-Infinity"')
                                    metrics = json.loads(metrics_json)
                                except (ValueError, json.JSONDecodeError) as parse_err:
                                    logger.warning(f"Failed to parse metrics JSON: {parse_err}")
        except Exception as metrics_err:
            logger.warning(f"Failed to extract metrics from notebook: {metrics_err}")

        # Extract model weights if saved to shared volume
        model_weights = None
        model_path = f"/notebook_output/{table_name}/{table_name}_model.pkl"
        try:
            if os.path.exists(model_path):
                with open(model_path, 'rb') as model_file:
                    model_weights = base64.b64encode(model_file.read()).decode('utf-8')
                logger.info(f"Model weights loaded from {model_path} ({len(model_weights)} chars base64)")
            else:
                logger.warning(f"Model file not found at {model_path}")
        except Exception as model_err:
            logger.warning(f"Failed to read model weights: {model_err}")

        return {
            "message": "Training analysis completed successfully",
            "status": "success",
            "metrics": metrics,
            "training_log": training_log[-2000:] if len(training_log) > 2000 else training_log,
            "model_weights": model_weights,
            "model_path": model_path if model_weights else None
        }
    
    except Exception as e:
        logger.error(f"Unexpected error in training data analysis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up only temporary files, not output files
        for file in temp_files:
            try:
                if os.path.exists(file) and ('temp_' in file or file in [notebook_filename, executed_notebook_filename]):
                    os.remove(file)
                    logger.debug(f"Cleaned up temporary file: {file}")
            except Exception as e:
                logger.error(f"Error cleaning up {file}: {str(e)}")