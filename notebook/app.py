from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
from routes import router

logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://backend:5000,http://localhost:5000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

if __name__ == "__main__":
    # Listen on all interfaces (0.0.0.0) inside the container
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7000)