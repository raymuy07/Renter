# Blog Scraper

A scalable blog post scraper and analyzer using Python, FastAPI, and LLMs.

## Features
- Automated blog post scraping
- LLM-powered content analysis
- RESTful API
- Real-time processing for premium users
- Batch processing for free tier

## Setup
1. Clone the repository
2. Create virtual environment: `uv venv && source .venv/bin/activate`
3. Install dependencies: `uv pip install -e .`
4. Copy `.env.example` to `.env` and fill in your values
5. Run migrations: `alembic upgrade head`
6. Start the server: `uvicorn src.main:app --reload`

## Architecture
- FastAPI for API
- PostgreSQL for data storage
- Redis for queues and caching
- Celery for background tasks
- Playwright for web scraping
