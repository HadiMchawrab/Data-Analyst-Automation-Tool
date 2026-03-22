# AI Consult
EECE 490 Project on agentic workflow

AI Consult is a fully automated agentic workflow designed to bridge the gap between non-technical users (including companies) and AI solutions: 0 code experience required!
Our agents take the user from raw data to a trained Machine Learning model seamlessly.

Just upload your CSV files, and let AI Consult analyze, recommend, and implement the best-fit ML model to solve your real-world problem.

## Prerequisites
- Docker & Docker Compose
- OpenAI API key

## Installation

Clone the repository:
```bash
git clone https://github.com/HadiMchawrab/Agents.git
cd Agents
```

Create a `.env` file inside the `backend/` directory:
```
OPENAI_API_KEY=your-openai-api-key-here
```

Build and start all services:
```bash
docker-compose up --build
```

The application will be available at:
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:5000
- **Notebook Service:** http://localhost:7000

## Architecture

The project runs as 3 Docker containers:

| Service | Tech | Purpose |
|---------|------|---------|
| Frontend | React 19 | Upload UI, topic selection, results display |
| Backend | FastAPI + LangGraph | LLM orchestration via GPT-4o, API endpoints |
| Notebook | FastAPI + Jupyter | Script execution, visualization, model training |

All LLM calls use **OpenAI GPT-4o** (and GPT-4o-mini for lighter tasks). The backend orchestrates two LangGraph state machines:

- **Graph 1** (virtualgraph.py): CSV upload → table analysis → ML topic inference → model suggestion → relevance matching
- **Graph 2** (implementer.py): Data preparation → visualization scripts → notebook execution → image analysis → training script generation → model training → evaluation → optimization loop

## Workflow

_The pipeline communicates with GPT-4o by sending well-designed prompts and receiving formatted responses that are forwarded from stage to stage._

1. **Upload CSV Files**
   Start by uploading your data file(s) with optional descriptions.

2. **Topic Inference (~30 seconds)**
   The system analyzes table metadata to suggest 4 ML topics with recommended models. GPT-4o-mini suggests additional models for each topic based on the data schema.

3. **Human in the Loop**
   Topics are displayed to the user, each with reasoning, data relationships, data needs, and suggested ML models. The user selects one topic and can add extra tables/columns for analysis.

4. **Automated Data Analysis**
   GPT-4o generates Python visualization scripts (distributions, correlations, heatmaps) tailored to the data types and shape. Scripts execute in an isolated Jupyter notebook. Generated images are encoded and passed to the next stage.

5. **ML Model Recommendation**
   GPT-4o analyzes the visualizations and selects the best-fit ML model based on data characteristics.

6. **Model Training & Optimization Loop**
   The selected model is trained on the data with an 80/20 train/test split. The system:
   - Generates a training script with metrics output
   - Executes it in the notebook service
   - Extracts evaluation metrics (accuracy, F1, R², etc.)
   - **If metrics are below threshold**, the system automatically retries with adjusted hyperparameters and feedback (up to 3 attempts)
   - Returns the trained model (`.pkl` download) and performance metrics

7. **Results Display**
   The frontend shows:
   - Visualization graphs (base64 images)
   - Chosen model with reasoning
   - Training metrics table (accuracy, precision, recall, F1, etc.)
   - Number of optimization retries performed
   - Download button for the trained model file

## Tech Stack

- **LLM:** OpenAI GPT-4o, GPT-4o-mini
- **Orchestration:** LangChain + LangGraph (with conditional edges for optimization loop)
- **Backend:** FastAPI, Python 3.11
- **Frontend:** React 19, React Router
- **ML/Data:** scikit-learn, pandas, NumPy, matplotlib, seaborn
- **Notebook:** Jupyter (nbformat/nbconvert for programmatic execution)
- **Infrastructure:** Docker Compose, shared volumes for artifacts
