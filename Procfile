web: uvicorn src.web.app:app --host 0.0.0.0 --port $PORT
worker: alembic upgrade head && python -m src.main
