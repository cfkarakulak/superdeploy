from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import psycopg2
import pika
from datetime import datetime

app = FastAPI(title="SuperDeploy API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables
DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "superdeploy")
DB_USER = os.getenv("POSTGRES_USER", "superdeploy")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "superdeploy_secure_password_2025")

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = os.getenv("RABBITMQ_PORT", "5672")
RABBITMQ_USER = os.getenv("RABBITMQ_DEFAULT_USER", "superdeploy")
RABBITMQ_PASS = os.getenv("RABBITMQ_DEFAULT_PASS", "superdeploy_secure_password_2025")


@app.get("/")
def read_root():
    return {
        "service": "SuperDeploy API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    checks = {"api": "healthy", "database": "unknown", "queue": "unknown"}

    # Check database
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            connect_timeout=3,
        )
        conn.close()
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)}"

    # Check RabbitMQ
    try:
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        parameters = pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=int(RABBITMQ_PORT),
            credentials=credentials,
            connection_attempts=1,
            socket_timeout=3,
        )
        connection = pika.BlockingConnection(parameters)
        connection.close()
        checks["queue"] = "healthy"
    except Exception as e:
        checks["queue"] = f"unhealthy: {str(e)}"

    all_healthy = all(v == "healthy" for v in checks.values())

    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/tasks")
def list_tasks():
    """List tasks - placeholder"""
    return {"tasks": [], "total": 0, "message": "No tasks yet"}


@app.post("/api/tasks")
def create_task(task: dict):
    """Create task - placeholder"""
    return {"id": "task-001", "status": "created", "task": task}


@app.get("/api/proxies")
def list_proxies():
    """List proxies - placeholder"""
    return {"proxies": [], "total": 0, "message": "No proxies yet"}
