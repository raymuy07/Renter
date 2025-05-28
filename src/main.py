from fastapi import FastAPI
from src.config import settings

app = FastAPI(
    title="Blog Scraper API",
    version="0.1.0",
    description="Scalable blog post scraper and analyzer"
)

@app.get("/")
async def root():
    return {"message": "Blog Scraper API", "version": "0.1.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
