"""
SuperDeploy CLI Constants

Centralized constants for magic values, defaults, and configuration.
"""

# Default SSH Configuration
DEFAULT_SSH_KEY_PATH = "~/.ssh/superdeploy_deploy"
DEFAULT_SSH_PUBLIC_KEY_PATH = "~/.ssh/superdeploy_deploy.pub"
DEFAULT_SSH_USER = "superdeploy"

# Default GCP Configuration
DEFAULT_GCP_REGION = "us-central1"
DEFAULT_GCP_ZONE = "us-central1-a"

# Default VM Configuration
DEFAULT_VM_MACHINE_TYPE = "e2-medium"
DEFAULT_VM_DISK_SIZE = 20
DEFAULT_CORE_VM_COUNT = 1

# Default Port Configuration
DEFAULT_APP_PORT = 8000
DEFAULT_POSTGRES_PORT = 5432
DEFAULT_RABBITMQ_PORT = 5672
DEFAULT_RABBITMQ_MANAGEMENT_PORT = 15672
DEFAULT_REDIS_PORT = 6379
DEFAULT_GRAFANA_PORT = 3000
DEFAULT_PROMETHEUS_PORT = 9090

# Default Network Configuration
ORCHESTRATOR_DOCKER_SUBNET = "172.29.0.0/24"
VPC_SUBNET_BASE = "10.0.0.0/8"
DOCKER_SUBNET_BASE = "172.30.0.0/16"

# Default Addon Versions
DEFAULT_POSTGRES_VERSION = "15-alpine"
DEFAULT_RABBITMQ_VERSION = "3.12-management-alpine"
DEFAULT_REDIS_VERSION = "7-alpine"
DEFAULT_CADDY_VERSION = "2-alpine"
DEFAULT_MONGODB_VERSION = "7-alpine"

# Docker Configuration
DEFAULT_DOCKER_REGISTRY = "docker.io"

# SSH Timeout Configuration
SSH_CONNECTION_TIMEOUT = 5
SSH_WAIT_MAX_ATTEMPTS = 18
SSH_WAIT_DELAY = 10

# Terraform Configuration
TERRAFORM_STATE_DIR = ".terraform"
TERRAFORM_WORKSPACE_DIR = "terraform.tfstate.d"

# Ansible Configuration
ANSIBLE_PYTHON_INTERPRETER = "/usr/bin/python3"
ANSIBLE_BECOME_METHOD = "sudo"

# Log Configuration
LOG_DATE_FORMAT = "%Y-%m-%d"
LOG_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Error Messages
ERROR_PROJECT_NOT_FOUND = (
    "Project '{project}' not found\nRun: superdeploy {project}:init"
)
ERROR_NO_DEPLOYMENT = "Project '{project}' not deployed\nRun: superdeploy {project}:up"
ERROR_APP_NOT_FOUND = "App '{app}' not found in project '{project}'"
ERROR_VM_NOT_FOUND = "VM '{vm}' not found in state"
ERROR_CONFIG_INVALID = "Invalid project configuration: {error}"

# Success Messages
SUCCESS_PROJECT_DEPLOYED = "Project deployed successfully"
SUCCESS_APP_RESTARTED = "Application restarted"
SUCCESS_ORCHESTRATOR_DEPLOYED = "Orchestrator deployed successfully"

# Tool Names (for doctor check)
REQUIRED_TOOLS = [
    "python3",
    "terraform",
    "ansible",
    "gcloud",
    "jq",
    "gh",
    "age",
    "ssh",
]

# Sensitive Keywords (for secret masking)
SENSITIVE_KEYWORDS = [
    "PASSWORD",
    "TOKEN",
    "SECRET",
    "KEY",
    "PAT",
]

# Container Name Format
CONTAINER_NAME_FORMAT = "{project}_{app}"  # Docker Compose uses underscore

# File Permissions
SECRET_FILE_PERMISSIONS = 0o600
SSH_KEY_PERMISSIONS = 0o600

# Orchestrator Services
ORCHESTRATOR_SERVICES = ["grafana", "prometheus"]

# Database Addons
DATABASE_ADDONS = ["postgres", "mongodb", "elasticsearch"]

# Cache Addons
CACHE_ADDONS = ["redis"]

# Queue Addons
QUEUE_ADDONS = ["rabbitmq"]

# Service Port Mappings
SERVICE_PORTS = {
    "postgres": DEFAULT_POSTGRES_PORT,
    "rabbitmq": DEFAULT_RABBITMQ_PORT,
    "rabbitmq-management": DEFAULT_RABBITMQ_MANAGEMENT_PORT,
    "redis": DEFAULT_REDIS_PORT,
    "grafana": DEFAULT_GRAFANA_PORT,
    "prometheus": DEFAULT_PROMETHEUS_PORT,
}

# Tunnel Port Mappings (local -> remote)
TUNNEL_PORT_MAPPINGS = {
    "postgres": (5433, DEFAULT_POSTGRES_PORT),
    "rabbitmq": (25672, DEFAULT_RABBITMQ_MANAGEMENT_PORT),
    "redis": (6380, DEFAULT_REDIS_PORT),
    "grafana": (3001, DEFAULT_GRAFANA_PORT),
    "prometheus": (9091, DEFAULT_PROMETHEUS_PORT),
}
