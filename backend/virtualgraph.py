import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from typing import TypedDict, List, Dict
from langgraph.graph import StateGraph
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
import sqlite3
import pandas as pd
import json
import logging
from dotenv import load_dotenv
from utils import parse_llm_json

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY is None:
    raise ValueError("OPENAI_API_KEY environment variable not set.")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Model constants
GPT_MODEL = "gpt-4o"
GPT_MINI_MODEL = "gpt-4o-mini"


class State(TypedDict):
    tables: List[Dict[str, List[str]]]
    analyzed_topics: List[Dict[str, str]]
    csv_files: List[str]
    topic: List[str]
    AnalyzedArticles: Dict[str, Dict[str, str]]
    Relationship: Dict[str, List[str]]
    Needs: Dict[str, List[str]]
    ModelsPerTopic: Dict[str, str]
    ML_Models1: List[str]
    GPT_Columns: Dict[str, List]
    AdjustedColumns: Dict[str, List[str]]


graph_builder = StateGraph(State)


def get_table_columns(state: dict, db_name: str = 'temp.db') -> dict:
    conn = sqlite3.connect(db_name)
    results = []
    adjusted_columns = {}
    try:
        for csv_file in state.get("csv_files", []):
            if not os.path.exists(csv_file):
                continue
            table_name = os.path.splitext(os.path.basename(csv_file))[0]
            df = pd.read_csv(csv_file)
            df.to_sql(table_name, conn, if_exists='replace', index=False)
            columns = pd.read_sql_query(f"PRAGMA table_info({table_name})", conn)['name'].tolist()
            results.append({table_name: columns})
            column_dtypes = []
            for col in columns:
                dtype_str = str(df[col].dtype)
                column_dtypes.append(f"{col}:{dtype_str}")
            adjusted_columns[table_name] = column_dtypes
    except Exception as e:
        logging.error(f"Error processing CSV files: {str(e)}")
        raise
    finally:
        conn.close()

    return {"tables": results, "adjusted_columns": adjusted_columns}


def analyze_tables_node(state: State):
    tables = state["tables"]
    tables_str = "\n".join([f"{table_name}: {columns}" for table in tables for table_name, columns in table.items()])
    model = ChatOpenAI(model_name=GPT_MODEL, temperature=0, openai_api_key=OPENAI_API_KEY)
    input_messages = [
        SystemMessage(content="""Given tables and columns names, extract the topic of the database.
                                 Provide 4 possible topics where machine learning models would be implemented on tabular database similar to the one above to improve the performance of such a company.
                                 The 4 topics should be clear with key words in place.
                                 Return them in a JSON array of objects with topic names and reasoning."""),
        HumanMessage(content="""Return the response *only* in this strict JSON format, with no additional text or explanations:
                                json
                                {
                                    "answer": [
                                        {
                                            "topic": "'Topic 1' and why it is important to the company and how it optimizes the performance of the company",
                                            "ML_Models": "ML Models 1 inferred by Claude from the articles",
                                            "reasoning": "Reasoning 1 or the relationship between the topic and the ML Model and what columns and data types could possibly be used in the ML model"
                                        },
                                        {
                                            "topic": "Machine learning models employed in 'Topic 2'",
                                            "ML_Models": "ML Models 2 inferred by Claude from the articles",
                                            "reasoning": "Reasoning 2 or the relationship between the topic and the ML Model and what columns and data types could possibly be used in the ML model"
                                        }
                                    ]
                                }"""),
        HumanMessage(content=f"Tables and columns names:\n{tables_str}")
    ]

    ai_message = model.invoke(input_messages)
    json_response = parse_llm_json(ai_message.content, "analyze_tables_node")

    ans = json_response['answer']
    topics = [topic["topic"] for topic in ans]
    logging.info(f"Topics: {topics}")

    ML_Models1 = [topic["ML_Models"] for topic in ans]
    logging.info(f"ML Models: {ML_Models1}")

    return {"analyzed_topics": ans, "topic": topics, "ML_Models1": ML_Models1}


def suggest_models_node(state: State):
    """Suggest additional ML models for each topic using LLM directly (replaces web scraping)."""
    model = ChatOpenAI(
        model_name=GPT_MINI_MODEL,
        temperature=0,
        openai_api_key=OPENAI_API_KEY
    )
    ans = {}
    ModelsPerTopic = {}

    tables = state["tables"]
    tables_str = "\n".join([
        f"{table_name}: {columns}"
        for table in tables
        for table_name, columns in table.items()
    ])

    for i, topic in enumerate(state["topic"]):
        previous_models = state["ML_Models1"][i]

        input_messages = [
            SystemMessage(content="""You are an expert data scientist. Given a business topic and database schema,
                suggest specific machine learning models that would be effective for this use case.
                Focus on models NOT already mentioned in the previously extracted models.
                Consider the data types and columns available in the database.
                Limit suggestions to 3 additional models."""),
            HumanMessage(content="""Return the response *only* in this strict JSON format, with no additional text:
                {
                    "answer": [
                        {
                            "Article_Summary": "Analysis of why these ML models are suitable for this topic given the available data",
                            "ML_Models": "Model1, Model2, Model3"
                        }
                    ]
                }"""),
            HumanMessage(content=f"Topic: {topic}"),
            HumanMessage(content=f"Available database tables and columns:\n{tables_str}"),
            HumanMessage(content=f"Previously suggested ML Models: {previous_models}")
        ]

        logging.info(f"Requesting model suggestions for topic: {topic}")
        ai_message = model.invoke(input_messages)
        json_response = parse_llm_json(ai_message.content, f"suggest_models_node (topic: {topic})")

        answer = json_response['answer']
        ans[topic] = answer[0]
        ModelsPerTopic[topic] = ans[topic]["ML_Models"]

    return {"AnalyzedArticles": ans, "ModelsPerTopic": ModelsPerTopic}


def relevance_node(state: State):
    model = ChatOpenAI(
        model_name=GPT_MODEL,
        temperature=0,
        openai_api_key=OPENAI_API_KEY
    )
    tables = state["tables"]
    tables_str = "\n".join([f"{table_name}: {columns}" for table in tables for table_name, columns in table.items()])

    Relationships = {}
    GPT_Columns = {}
    Needs = {}

    for i, topic in enumerate(state["topic"]):
        Input_messages = [
            SystemMessage(content="""You are given the ML models used in the topics and how they would benefit the company,
                                     You are also given the initial tables and column names of my database,
                                     You are given the interpretation of the tables and column names.
                                     Find the relevance of each of the ML models posed with the tables and columns names of the database."""),
            HumanMessage(content="""Return the response *only* in this strict JSON format, with no additional text or explanations:
                                    json
                                    {
                                        "Relationship": "Explains the relationship between the ML model and the tables and columns names of the database",
                                        "Columns": "[{table1:[col1,col2]}, {table2:[col1,col]}](Return a list which contains dictionaries with the table name and the 7 columns maximum which GPT chooses as the key to the table name)",
                                        "Needs": "Tell the user how the columns we need for this certain topic are going to be used in training the ML model and what data types are needed for the end goal of the ML model(classification, regression, etc)"
                                    }"""),
            HumanMessage(content=f"The initial tables and columns: {tables_str}"),
            HumanMessage(content=json.dumps(state["analyzed_topics"][i])),
            HumanMessage(content=f"modelsWeUse: {state['ModelsPerTopic'][topic]}")
        ]

        ai_response = model.invoke(Input_messages)
        logging.info(f"Claude response for topic '{topic}': {ai_response.content[:200]}...")

        parsed_json = parse_llm_json(ai_response.content, f"relevance_node (topic: {topic})")

        Relationships[topic] = [parsed_json.get("Relationship", "No Relationship returned")]
        GPT_Columns[topic] = [parsed_json.get("Columns", "No Columns returned")]
        Needs[topic] = [parsed_json.get("Needs", "No Needs returned")]

    return {"Relationship": Relationships, "GPT_Columns": GPT_Columns, "Needs": Needs}


# Add nodes to the graph
graph_builder.add_node("extract_tables", get_table_columns)
graph_builder.add_node("analyze_tables", analyze_tables_node)
graph_builder.add_node("suggest_models", suggest_models_node)
graph_builder.add_node("relevance", relevance_node)

# Add edges
graph_builder.add_edge("extract_tables", "analyze_tables")
graph_builder.add_edge("analyze_tables", "suggest_models")
graph_builder.add_edge("suggest_models", "relevance")

# Set entry and finish points
graph_builder.set_entry_point("extract_tables")
graph_builder.set_finish_point("relevance")

# Compile the graph
graph = graph_builder.compile()


def run_graph(csv_files: List[str], descriptions: Dict[str, str] = None) -> State:
    csv_files = list(csv_files) if not isinstance(csv_files, list) else csv_files

    initial_state = {
        "tables": [],
        "analyzed_topics": [],
        "csv_files": csv_files,
        "topic": [],
        "AnalyzedArticles": {},
        "ModelsPerTopic": {},
        "Relationship": {},
        "GPT_Columns": {},
        "ML_Models1": [],
        "Needs": {},
        "AdjustedColumns": {}
    }

    final_state = graph.invoke(initial_state)

    logging.info(f"Graph completed. Topics: {final_state.get('topic', [])}")

    return final_state


if __name__ == "__main__":
    run_graph(["csv_files/banking.csv", "csv_files/data.csv"])
