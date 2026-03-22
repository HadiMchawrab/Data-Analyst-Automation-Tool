import sys
import os
from pathlib import Path
import base64

project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from typing import TypedDict, List, Dict
from langgraph.graph import StateGraph
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
import pandas as pd
import json
import logging
from dotenv import load_dotenv
import requests
from utils import parse_llm_json

logger = logging.getLogger(__name__)

if not load_dotenv():
    logging.warning("Failed to load .env file. Ensure it exists and is properly configured.")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
if not CLAUDE_API_KEY:
    raise ValueError("CLAUDE_API_KEY is not set. Please check your .env file.")

NOTEBOOK_URL = os.getenv("NOTEBOOK_URL", "http://notebook:7000")
CLAUDE_SONNET_MODEL = "claude-3-7-sonnet-20250219"
GPT_MODEL = "gpt-4o"


def get_claude_model():
    return ChatAnthropic(model_name=CLAUDE_SONNET_MODEL, temperature=0, anthropic_api_key=CLAUDE_API_KEY, max_tokens=8192)


def get_gpt_model():
    return ChatOpenAI(model_name=GPT_MODEL, temperature=0, openai_api_key=os.getenv("OPENAI_API_KEY"), max_tokens=4052)

class State(TypedDict):
    tables: List[Dict[str, List[str]]]
    adjusted_columns: Dict[str, List[str]]
    data_frames: dict
    csv_files: List[str]
    topic: str
    Relationship: str
    ML_Models: List[str]
    DF_Info: dict
    Analysis: dict
    Pictures: dict
    Pictures_Analysis: dict
    Reqs: dict
    scripts: dict
    executed_notebook: dict
    chosen_models: str
    explained_models: str
    Last_Analysis: str
    Last_Model: str
    Last_DF: str
    FinalReqs: str
    FinalScripts: str





graph_builder = StateGraph(State)


def into_data_frames(state: State) -> State:
    # state['tables'] is a set of dictionaries {'table1': ['col1', 'col2'], 'table2': ['col1', 'col2']} 
    # hence we need to loop over the set, and for each table, make it a data frame and store it in state['data_frames']
    data_frames = {}
    adjusted_columns = {} # I want to store the adjusted columns in a set of dictionaries {'table1': ['col1:datatype', 'col2:datatype'], 'table2': ['col1:datatype', 'col2:datatype']} hence we need to find the type of each column in each data frame and insert them into this variable
    for table in state['tables']: 
        for table_name, columns in table.items():
            # Create a DataFrame from the CSV file in csv_test directory
            csv_file = f"csv_test/{table_name}.csv"
            if os.path.exists(csv_file):
                try:
                    available_df = pd.read_csv(csv_file)
                    available_columns = available_df.columns.tolist()
                    valid_columns = [col for col in columns if col in available_columns]
                    if len(valid_columns) < len(columns):
                        missing_columns = [col for col in columns if col not in available_columns]
                        logging.warning(f"Some requested columns for {table_name} don't exist in the CSV: {missing_columns}")
                    if valid_columns:
                        df = pd.read_csv(csv_file, usecols=valid_columns)
                        data_frames[table_name] = df
                        column_dtypes = []
                        for col in valid_columns:
                            dtype_str = str(df[col].dtype)
                            column_dtypes.append(f"{col}:{dtype_str}")
                        adjusted_columns[table_name] = column_dtypes
                    else:
                        logging.warning(f"None of the requested columns for {table_name} exist in the CSV.")
                except Exception as e:
                    logging.error(f"Error reading {csv_file}: {str(e)}")
            else:
                logging.warning(f"CSV file {csv_file} does not exist. Skipping this table.")
    logging.info(f"Data frames created: {adjusted_columns}")
    return {'data_frames': data_frames, 'adjusted_columns': adjusted_columns}



def generate_analysis(state: State) -> State:
    ans = {}
    Reqs = {}
    scripts = {}
    
    # Extract table names from adjusted_columns dictionary
    table_names = list(state['adjusted_columns'].keys())
    logging.info(f"Tables for analysis: {table_names}")
    
    for table_name in table_names:
        # Generate analysis for each DataFrame using CLAUDE
        logging.info(f"Generating analysis for {table_name}")
        adjusted_columns = state['adjusted_columns'][table_name]
        adjusted_columns_str = str(adjusted_columns)
        ml_models_str = str(state['ML_Models'])
        logging.info(f"Generating analysis for {table_name} with columns: {adjusted_columns_str} and ML models: {ml_models_str}")
        input_messages= [SystemMessage(content = """
                                                You will be generating python scripts to run on the data frame to generate the analysis and get visualization.
                                                I will then be sending the data you generated with the Data frames in a jupyter notebook to run the scripts and generate the analysis and get visualization.
                                                The scripts will be run in a single code cell, I dont want you to gererate big ammounts of code, just the scripts to run on the data frame to generate the analysis and get visualization and not to run models, limit the scripts to 200 lines of code max
                                                As a result of the scripts, I need to get pictures such as relationships between the columns, heat maps and so on.
                                                """), 
                     HumanMessage(content = f"""Return the response **only** in this strict JSON format, with no additional text or explanations:
                                 ```json
                                    {'{'}
                                        "Reqs": "All the requirements to be installed to run the below scripts seperated by a single space between each requirement, and the requirements should be in a single line",
                                        "Scripts": "You will continue working assuming that there is pandas dataframe called {table_name} which is defined to have these columns {adjusted_columns_str}. 
                                                    You shouldn't re-write the before lines continue from there. 
                                                    Your goal: generate a full working code, knowing that you need to generate images and analysis and give a set of visualizations of this current dataframe (which is given, so you shouldn't write it in your code, assume you have a dataframe called {table_name} ) we need to make analysis of the data to understand more how we can use ML models to tackle this topic {state['topic']}. Your goal is not to write an ML algorithm but just to provided illustraiotns analysis, distributions, heatmpas, boxplots, correlation table ... on the dataframe called: {table_name}.
                                                    The scripts to run on the data frame to generate the analysis and get a set of visualizations not to train the models on our dataset, but rather to get visualizations on the data we have which would be relevant to use later when we want to choose the best ML Model , you can also either use the whole data frame or choose a subset of the columns (limit the scripts to 200 lines of code max, which will be running in a single code cell) and call the dataframe "{table_name}", exactly as it is. 

                                                    IF you want to show the correlation table, you dont need columns that are strings, you should look at the columns that have type either int or float using this info {adjusted_columns_str}, and you can use the correlation table.                                        
                                                    Also make use of other relationships between the columns and the ML models to generate the analysis and get visualizations, while taking into consideration the type of the data you are using in order not to get an error. 
                                                    

                                                    Rules: 
                                                    Inside your working directory which is notebook_output, 
                                                    You need to create a subdirectory for this table name = {table_name} in the main directory: notebook_directory, which is already created so no need to recreate notebook_output, and save the pictures in it. 
                                                    
                                                    And so on.
                                                    
                                                    
                                                    Example of the code you should generate:
                                                    in python:
                                                        
                                                        os.makedirs('{table_name}', exist_ok=True)
                                                        plt.title('Correlation Matrix')
                                                        plt.savefig('notebook_output/{table_name}/{table_name}_figure_1.png')
                                                        plt.savefig('notebook_output/{table_name}/{table_name}_figure_2.png')
                                                        plt.savefig('notebook_output/{table_name}/{table_name}_figure_3.png')
                                                        plt.savefig('notebook_output/{table_name}/{table_name}_figure_4.png')
                                                        plt.savefig('notebook_output/{table_name}/{table_name}_figure_5.png')
                                                    Dont generate code inside a for loop, it will give an error in tha naming and saving of the files, just generate the code to save the figures in the above format, and dont add any other paths or directories to the directory I just gave you in teh 5 above examples, in any figure you want to save, use the above convention, just 2 directories and the file name
                                                    Dont add any other paths or directories to the directory I just gave you in teh 5 above examples, in any figure you want to save, use the above convention, just 2 directories and the file name"
                                    {'}'}```
                                    YOU NEED TO RETURN THE JSON RESPONSE ONLY, STARTING with ```json and ending with ```, so I can parse it easily
                                    """),
                     HumanMessage(content = f"""The topic is: {state['topic']}"""),
                     HumanMessage(content = f"""The columns in this data frame are: {adjusted_columns_str}"""),
                     HumanMessage(content = f"""The ML models are: {ml_models_str}""")
                     ]
                                  

        
        logging.info(f"Generating analysis for {table_name}")
        ai_message = get_gpt_model().invoke(input_messages)
        parsed_json = parse_llm_json(ai_message.content, f"generate_analysis ({table_name})")

        Reqs[table_name] = parsed_json.get("Reqs", "No Reqs returned")
        scripts[table_name] = parsed_json.get("Scripts", "No Scripts returned")        
        
    return {'Analysis': ans, 'Reqs': Reqs, 'scripts': scripts}


def send_to_notebook(reqs: dict, scripts: dict, dfs: dict):
    logger = logging.getLogger(__name__)
    logger.info("Starting send_to_notebook function")
    
    csvs = []
    file_handles = []
    try:
        # Create csv_adjusted directory if it doesn't exist
        os.makedirs("csv_adjusted", exist_ok=True)
        logger.debug("Created csv_adjusted directory")
        
        files = []
        # Convert DataFrames to CSV files and prepare files dict
        for table_name, df in dfs.items():
            logger.info(f"Processing table: {table_name}")
            csv_file = f"csv_adjusted/{table_name}.csv"
            logger.debug(f"Saving DataFrame to {csv_file}")
            
            try:
                df.to_csv(csv_file, index=False)
                csvs.append(csv_file)
                logger.debug(f"Successfully saved DataFrame to {csv_file}")
            except Exception as e:
                logger.error(f"Error saving DataFrame to CSV: {str(e)}")
                raise
            
            try:
                # Open file and create file handle
                file_handle = open(csv_file, 'rb')
                file_handles.append(file_handle)
                # Add to files list in the correct format for requests
                files.append(('files', (table_name, file_handle, 'text/csv')))
                logger.debug(f"Created file handle and added to files list for {table_name}")
            except Exception as e:
                logger.error(f"Error creating file handle: {str(e)}")
                raise

        # Prepare the data as JSON strings
        try:
            data = {
                'reqs': json.dumps(reqs),
                'scripts': json.dumps(scripts)
            }
            logger.debug("Successfully prepared JSON data")
        except Exception as e:
            logger.error(f"Error preparing JSON data: {str(e)}")
            raise
        
        try:
            logger.debug(f"Sending POST request to notebook service with {len(files)} files")
            response = requests.post(
                f"{NOTEBOOK_URL}/analyze-data",
                data=data,
                files=files,
                timeout=600  # 10 minute timeout
            )
            logger.debug(f"Received response with status code: {response.status_code}")
            
            if response.status_code == 422:
                logger.error(f"Validation error response: {response.text}")
                return {"error": f"Request validation failed: {response.text}"}
            
            response_json = response.json()
            logger.info("Successfully received and parsed response from notebook service")
            return response_json
        except requests.Timeout:
            logger.error("Timeout error while sending data to notebook service")
            return {"error": "Request timed out while sending data to notebook service"}
        except requests.RequestException as e:
            logger.error(f"Error sending request to notebook service: {str(e)}")
            return {"error": f"Failed to send request to notebook service: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error while communicating with notebook service: {str(e)}", exc_info=True)
            return {"error": f"Unexpected error: {str(e)}"}
    
    finally:
        logger.debug("Starting cleanup process")
        # Close all file handles
        for handle in file_handles:
            try:
                handle.close()
                logger.debug("Closed file handle")
            except Exception as e:
                logger.error(f"Error closing file handle: {str(e)}")
        
        # Clean up temporary CSV files after handles are closed
        for csv_file in csvs:
            try:
                if os.path.exists(csv_file):
                    os.remove(csv_file)
                    logger.debug(f"Removed temporary file: {csv_file}")
            except Exception as e:
                logger.error(f"Error cleaning up {csv_file}: {str(e)}")


def call_notebook_service(state: State) -> State:
    """
    Node to call the notebook FastAPI service and return the executed notebook.
    """
    logger = logging.getLogger(__name__)
    reqs = state.get("Reqs", {})
    scripts = state.get("scripts", {})
    dfs = state.get("data_frames", {})
    
    try:
        notebook_result = send_to_notebook(reqs, scripts, dfs)
        return state
    except Exception as e:
        logger.error(f"Error in call_notebook_service: {str(e)}")
        raise


def analyze_images(state: State) -> State:
    ml_mod = {}
    model_analysis = {}
    Last_Analysis = str
    Last_Model = str
    Last_DF = str
    images_bytes = {}  # Store base64 encoded images per table

    # Get table names from the data_frames state
    table_names = list(state['data_frames'].keys())
    logger.info(f"Processing tables: {table_names}")
    
    for table_name in table_names:
        table_image_messages = []
        table_images = []  # Store images for this table
        j = 1
        
        while True:
            image_path = f"/notebook_output/{table_name}/{table_name}_figure_{j}.png"
            logger.debug(f"Checking for image: {image_path}")
            
            if not os.path.exists(image_path):
                logger.debug(f"No more images found for table {table_name} after {j-1} images")
                break
                
            try:
                with open(image_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                    table_image_messages.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"}
                    })
                    table_images.append(b64)  # Store the base64 string
                    logger.debug(f"Successfully encoded image {j} for table {table_name}")
            except Exception as e:
                logger.error(f"Error processing image {image_path}: {str(e)}")
                break
                
            j += 1
        
        if table_images:  # Store images for this table if any were found
            images_bytes[table_name] = table_images
            
        if table_image_messages:  # Only analyze if we found images
            messages = [
                SystemMessage(content=(
                    "You are an expert data scientist. "
                    "Analyze the set of exploratory plots provided and extract key insights "
                    "about data distribution, feature relationships, and any anomalies. "
                    "Then recommend the single best ML model for this dataset."
                )),
                HumanMessage(content = f"""Return the response *only* in this strict JSON format, with no additional text or explanations:     
                            ```json
                                        {'{'}
                                            "RecommendedModel": "one of the set of ML models: {state['ML_Models']}, and the model should be in a single line",
                                            "Insights": "Why we chose this model based on the analysis of the images"
                                        {'}'}```"""),
                HumanMessage(content=table_image_messages)
            ]

            try:
                logging.info(f"Sending analysis request for table {table_name}")
                ai_message = get_gpt_model().invoke(messages)
                parsed_json = parse_llm_json(ai_message.content, f"analyze_images ({table_name})")
                ml_mod[table_name] = parsed_json.get("RecommendedModel", "No Model returned")
                model_analysis[table_name] = parsed_json.get("Insights", "No Insights returned")
            except Exception as e:
                logger.error(f"Error analyzing images for table {table_name}: {str(e)}")
                ml_mod[table_name] = "Analysis failed"
                model_analysis[table_name] = f"Error: {str(e)}"

    stringified_models_analysis = str(state['explained_models'])
    stringified_models = str(state['chosen_models'])

    messages = [
    SystemMessage(content=f"""(
        "You are an expert data scientist. "
        "Analyze the dataframes within the variables given the explanation {stringified_models_analysis}on why each ML model is being used in each dataframe"
        "From these inferences, check which is the most understandable in why we chose the model  "
        "Then recommend the single best data frame and its compatible ML model."
    )"""),
    HumanMessage(content = f"""Return the response *only* in this strict JSON format, with no additional text or explanations:     
                ```json
                            {'{'}
                                "Last_DF": "one of the set of tables models: {state['tables']}",
                                "Last_Model":"model from {stringified_models} should be in a single line",
                                "Last_Analysis": "the analysis of the last model and the last data frame",
                                
                            {'}'}```""")
        ]

    ai_message2 = get_gpt_model().invoke(messages)
    parsed_json2 = parse_llm_json(ai_message2.content, "analyze_images (best model selection)")

    Last_DF = parsed_json2.get("Last_DF", "No Last DF returned")
    Last_Model = parsed_json2.get("Last_Model", "No Last Model returned")
    Last_Analysis = parsed_json2.get("Last_Analysis", "No Last Analysis returned")



    return {'chosen_models': Last_Model, 'explained_models': Last_Analysis, 'Last_DF': Last_DF, 'images_bytes': images_bytes}






def generate_train(state: State) -> State:
    stringified_analysis = str(state['Analysis'])
    stringified_model = str(state['chosen_models'])

    messages = [
    SystemMessage(content=("You are an expert data scientist. "
        "Given the ML model to use and the analysis and the data frame, generate a python script that would train the model on the data frame."
       
    )),
    HumanMessage(content = f"""Return the response *only* in this strict JSON format, with no additional text or explanations:     
                ```json
                            {'{'}
                                "LRequiremenets": "All the requirements to be installed to run the below scripts seperated by a single space between each requirement, and the requirements should be in a single line",
                                "LScripts": "Generate a full python text, which would run the dataframe {state['Last_DF']} and train the model {stringified_model} on it, and the script should be in a single line and separated by \n. Also save ethe result of the training in a file called {state['Last_DF']}_model.pkl, and the path should be relative to the notebook that will be running the scripts."
                                
                            {'}'}```""")
                            ]

    ai_message = get_gpt_model().invoke(messages)
    parsed_json3 = parse_llm_json(ai_message.content, "generate_train")
    logging.info(f"Training script generated successfully")
    Final_Scripts = parsed_json3.get("LScripts", "No Last DF returned")
    Final_Reqs = parsed_json3.get("LRequiremenets", "No Last Model returned")

    return {'FinalReqs': Final_Reqs, 'FinalScripts': Final_Scripts}


def send_to_training(reqs: str, scripts: str, dfs: dict):
    """
    Sends a single dataframe with requirements and scripts to the notebook service
    for training data analysis.
    
    Args:
        reqs (str): Requirements string for pip installation (not a JSON string)
        scripts (str): The script to run on the dataframe (not a JSON string)
        dfs (dict): Dictionary with a single key-value pair of table_name:dataframe
    
    Returns:
        dict: The response from the notebook service with training analysis results
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting send_to_training function")
    
    if len(dfs) != 1:
        logger.error(f"Expected 1 dataframe, got {len(dfs)}")
        return {"error": f"Expected 1 dataframe, got {len(dfs)}"}
    
    csvs = []
    file_handles = []
    try:
        # Create csv_adjusted directory if it doesn't exist
        os.makedirs("csv_adjusted", exist_ok=True)
        logger.debug("Created csv_adjusted directory")
        
        # Get the single table name and dataframe
        table_name = list(dfs.keys())[0]
        df = dfs[table_name]
        
        # Add memory optimization for larger dataframes
        if df.shape[0] * df.shape[1] > 100000:  # If dataframe is large
            logger.info(f"Large dataframe detected with shape {df.shape}, applying memory optimization")
            # Downcast numeric columns
            for col in df.columns:
                if df[col].dtype == 'float64':
                    df[col] = pd.to_numeric(df[col], downcast='float')
                elif df[col].dtype == 'int64':
                    df[col] = pd.to_numeric(df[col], downcast='integer')
            # Convert object columns to category if appropriate
            for col in df.select_dtypes(include=['object']):
                if df[col].nunique() < df.shape[0] // 2:
                    df[col] = df[col].astype('category')
            logger.info("Memory optimization applied to dataframe")
        
        logger.info(f"Processing table for training: {table_name}")
        csv_file = f"csv_adjusted/{table_name}.csv"
        logger.debug(f"Saving DataFrame to {csv_file}")
        
        try:
            # Save with less memory usage for large dataframes
            if df.shape[0] > 100000:
                logger.info(f"Large dataframe detected, saving in chunks")
                chunk_size = 50000
                for i in range(0, df.shape[0], chunk_size):
                    chunk = df.iloc[i:i+chunk_size]
                    if i == 0:
                        chunk.to_csv(csv_file, index=False, mode='w')
                    else:
                        chunk.to_csv(csv_file, index=False, mode='a', header=False)
                logger.debug(f"Successfully saved DataFrame in chunks to {csv_file}")
            else:
                df.to_csv(csv_file, index=False)
                logger.debug(f"Successfully saved DataFrame to {csv_file}")
            csvs.append(csv_file)
        except Exception as e:
            logger.error(f"Error saving DataFrame to CSV: {str(e)}")
            raise
        
        try:
            # Open file and create file handle
            file_handle = open(csv_file, 'rb')
            file_handles.append(file_handle)
            # Add to files for the request - keep the file name as is
            files = [('file', (table_name, file_handle, 'text/csv'))]
            logger.debug(f"Created file handle and added to files list for {table_name}")
        except Exception as e:
            logger.error(f"Error creating file handle: {str(e)}")
            raise

        # Add memory safety guards to the scripts
        if "import" in scripts and "gc" not in scripts:
            # Add garbage collection imports and calls
            scripts = "import gc\n" + scripts
            scripts += "\n\n# Final cleanup\ngc.collect()"
        
        # Ensure we're not creating huge arrays
        if "np.array" in scripts or "np.zeros" in scripts or "np.ones" in scripts:
            logger.info("Detected potential large array creation in scripts, adding safety checks")
            memory_guard = """
# Memory safety checks
def check_array_size(shape):
    size_bytes = np.prod(shape) * 8  # Assuming float64 (8 bytes)
    size_gb = size_bytes / (1024**3)
    if size_gb > 1:  # Warn if more than 1GB
        print(f"WARNING: Operation would create array of {size_gb:.2f} GB")
        if size_gb > 10:  # Error if more than 10GB
            raise MemoryError(f"Operation would require {size_gb:.2f} GB of memory")
        return False
    return True
"""
            scripts = memory_guard + "\n" + scripts
        
        # Prepare the data - send as is, no need for json.dumps
        try:
            data = {
                'reqs': reqs + " psutil", # Add psutil for memory monitoring
                'scripts': scripts
            }
            logger.debug("Successfully prepared data")
        except Exception as e:
            logger.error(f"Error preparing data: {str(e)}")
            raise
        
        try:
            # Use notebook:7000 instead of localhost:7000 when running in Docker
            logger.debug(f"Sending POST request to notebook service train-data endpoint")
            response = requests.post(
                f"{NOTEBOOK_URL}/train-data",
                data=data,
                files=files,
                timeout=600  # 10 minute timeout
            )
            logger.debug(f"Received response with status code: {response.status_code}")
            
            if response.status_code == 422:
                logger.error(f"Validation error response: {response.text}")
                return {"error": f"Request validation failed: {response.text}"}
            
            response_json = response.json()
            logger.info("Successfully received and parsed response from notebook service")
            return response_json
        except requests.Timeout:
            logger.error("Timeout error while sending data to notebook service")
            return {"error": "Request timed out while sending data to notebook service"}
        except requests.RequestException as e:
            logger.error(f"Error sending request to notebook service: {str(e)}")
            return {"error": f"Failed to send request to notebook service: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error while communicating with notebook service: {str(e)}", exc_info=True)
            return {"error": f"Unexpected error: {str(e)}"}
    
    finally:
        logger.debug("Starting cleanup process")
        # Close all file handles
        for handle in file_handles:
            try:
                handle.close()
                logger.debug("Closed file handle")
            except Exception as e:
                logger.error(f"Error closing file handle: {str(e)}")
        
        # Clean up temporary CSV files after handles are closed
        for csv_file in csvs:
            try:
                if os.path.exists(csv_file):
                    os.remove(csv_file)
                    logger.debug(f"Removed temporary file: {csv_file}")
            except Exception as e:
                logger.error(f"Error cleaning up {csv_file}: {str(e)}")


def call_notebook_train(state: State) -> State:
    """
    Node to call the notebook FastAPI service and return the executed notebook.
    """
    logger = logging.getLogger(__name__)
    reqs = state.get("FinalReqs", "")  # Get FinalReqs as a string
    scripts = state.get("FinalScripts", "")  # Get FinalScripts as a string
    df_name = state.get("Last_DF", "")  # Get Last_DF as a string

    # Create dictionary with a single dataframe
    if df_name and df_name in state['data_frames']:
        df_dict = {df_name: state['data_frames'][df_name]}
    else:
        logger.error(f"DataFrame {df_name} not found in data_frames")
        df_dict = {}  # Empty dictionary if not found
    
    try:
        # Call send_to_training with the string parameters
        notebook_result = send_to_training(reqs, scripts, df_dict)
        state["executed_training"] = notebook_result
        return state
    except Exception as e:
        logger.error(f"Error in call_notebook_train: {str(e)}")
        raise








graph_builder.add_node("into_data_frames", into_data_frames)
graph_builder.add_node("generate_analysis", generate_analysis)
graph_builder.add_node("call_notebook_service", call_notebook_service)
graph_builder.add_node("analyze_images", analyze_images)
graph_builder.add_node("generate_train", generate_train)
graph_builder.add_node("call_notebook_train", call_notebook_train)

graph_builder.add_edge("into_data_frames", "generate_analysis")
graph_builder.add_edge("generate_analysis", "call_notebook_service")
graph_builder.add_edge("call_notebook_service", "analyze_images")
graph_builder.add_edge("analyze_images", "generate_train")
graph_builder.add_edge("generate_train", "call_notebook_train")
graph_builder.set_entry_point("into_data_frames")
graph_builder.set_finish_point("call_notebook_train")

graph2 = graph_builder.compile()

def test_graph2():
    # Create a sample state
    initial_state = {
        'tables': [{'banking': ['age', 'job', 'marital', 'education', 'default', 'housing', 'loan', 'duration']}, {'data': ['Bankrupt?', ' ROA(C) before interest and depreciation before interest', ' Debt ratio %', ' Net worth/Assets', ' Total debt/Total net worth', ' Cash Flow to Liability', ' Net Income to Total Assets']}],
        'adjusted_columns': {},
        'data_frames': {},
        'csv_files': {'csv_test/banking.csv', 'csv_test/data.csv'},
        'topic': "Machine learning models employed in Credit Risk Assessment",
        'Relationship': "The ML models (SVM, RNN, Bayesian Networks) are well-suited for credit risk assessment using the available data. SVM can classify customers into risk categories based on financial attributes, RNNs can analyze sequential patterns in financial data to predict defaults, and Bayesian Networks can model probabilistic relationships between financial indicators and credit risk outcomes.",
        'ML_Models': ["Support Vector Machines (SVM)", "Recurrent Neural Networks (RNN)", "Bayesian Networks","Logistic Regression", "Random Forest", "Gradient Boosting", "Neural Networks"],
        'scripts': {}, # set of dictionaries of data frames and the scripts to run on them
        'Analysis': {},
        'Pictures': {},
        'Pictures_Analysis': {},
        'Reqs': {},
        'DF_Info': {},
        'executed_notebook': {},
        'chosen_models': {},
        'explained_models': {},
        'FinalReqs': {},
        'FinalScripts': {},
        'Last_Analysis': {},
        'Last_Model': {},
        'Last_DF': {},
        'executed_training': {},
        'images_bytes': {}

    }

    # Run the graph with the sample state
    print("Initial State:")
    final_state2 = graph2.invoke(initial_state)
    print(final_state2)
    
def run_graph2(data: dict) -> State:
    tables_list = [
        {table_name: columns}
        for table_name, columns in data['tables'].items()
    ]

    initial_state = {
        'tables': tables_list,
        'adjusted_columns': {},
        'data_frames': {},
        'csv_files': list(data['csv_files']) if not isinstance(data['csv_files'], list) else data['csv_files'],
        'topic': data['topic'],
        'Relationship': data['Relationship'],
        'ML_Models': data['ML_Models'],
        'DF_Info': {},
        'Analysis': {},
        'Pictures': {},
        'Pictures_Analysis': {},
        'Reqs': {},
        'scripts': {},
        'executed_notebook': {},
        'chosen_models': '',
        'explained_models': '',
        'FinalReqs': '',
        'FinalScripts': '',
        'Last_Analysis': '',
        'Last_Model': '',
        'Last_DF': '',
        'executed_training': {},
        'images_bytes': {}
    }

    logging.info("Starting graph2 execution")
    final_state2 = graph2.invoke(initial_state)
    logging.info("Graph2 execution completed")

    return {
        'tables': final_state2.get('tables', []),
        'adjusted_columns': final_state2.get('adjusted_columns', {}),
        'csv_files': list(final_state2.get('csv_files', [])),
        'topic': final_state2.get('topic', ''),
        'Relationship': final_state2.get('Relationship', ''),
        'ML_Models': final_state2.get('ML_Models', []),
        'Analysis': final_state2.get('Analysis', {}),
        'DF_Info': final_state2.get('DF_Info', {}),
        'Pictures': final_state2.get('Pictures', {}),
        'Pictures_Analysis': final_state2.get('Pictures_Analysis', {}),
        'Reqs': final_state2.get('Reqs', {}),
        'scripts': final_state2.get('scripts', {}),
        'executed_notebook': final_state2.get('executed_notebook', {}),
        'chosen_models': final_state2.get('chosen_models', ''),
        'explained_models': final_state2.get('explained_models', ''),
        'FinalReqs': final_state2.get('FinalReqs', ''),
        'FinalScripts': final_state2.get('FinalScripts', ''),
        'Last_Analysis': final_state2.get('Last_Analysis', ''),
        'Last_DF': final_state2.get('Last_DF', ''),
        'executed_training': final_state2.get('executed_training', {}),
        'images_bytes': final_state2.get('images_bytes', {})
    }


if __name__ == "__main__":
    test_graph2()