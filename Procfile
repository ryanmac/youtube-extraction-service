web: uvicorn app.main:app --host=0.0.0.0 --port=$PORT
worker: celery -A celery_worker.celery_app worker --loglevel=info