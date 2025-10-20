# Forgejo Required Secrets and Variables

**IMPORTANT**: All workflows require explicit configuration. No fallbacks or defaults exist.

## How to Configure

1. Go to Forgejo Repository → Settings → Secrets and Variables
2. Add all required **Secrets** (sensitive data)
3. Add all required **Variables** (non-sensitive configuration)

## Required Secrets (Sensitive)

### Database & Queue
- `POSTGRES_PASSWORD` - PostgreSQL database password
- `RABBITMQ_PASSWORD` - RabbitMQ message queue password

### Application
- `API_SECRET_KEY` - API secret key for JWT/encryption
- `PROXY_REGISTRY_API_KEY` - Proxy registry API authentication key
- `PROXY_PASSWORD` - Proxy server authentication password

### Monitoring (Optional)
- `SENTRY_DSN` - Sentry error tracking DSN (can be empty string if not used)

## Required Variables (Non-Sensitive)

### Network Configuration
- `CORE_EXTERNAL_IP` - Core VM public IP (e.g., `34.56.43.99`)
- `CORE_INTERNAL_IP` - Core VM internal IP (e.g., `10.0.0.5`)
- `SCRAPE_EXTERNAL_IP` - Scrape VM public IP (e.g., `34.67.236.167`)
- `SCRAPE_INTERNAL_IP` - Scrape VM internal IP (e.g., `10.0.0.7`)
- `PROXY_EXTERNAL_IP` - Proxy VM public IP (e.g., `34.173.11.246`)
- `PROXY_INTERNAL_IP` - Proxy VM internal IP (e.g., `10.0.0.6`)

### Core Services Configuration
- `CORE_API_PORT` - API port (e.g., `8000`)
- `CORE_DB_PORT` - Database port (e.g., `5432`)
- `CORE_DB_NAME` - Database name (e.g., `superdeploy`)
- `CORE_DB_USER` - Database user (e.g., `superdeploy`)

### RabbitMQ Configuration
- `RABBITMQ_PORT` - RabbitMQ port (e.g., `5672`)
- `RABBITMQ_USER` - RabbitMQ user (e.g., `superdeploy`)
- `RABBITMQ_VHOST` - RabbitMQ virtual host (e.g., `/`)
- `RABBITMQ_QUEUE_NAME` - Queue name (e.g., `scraping_jobs`)

### Proxy Registry Configuration
- `PROXY_REGISTRY_PORT` - Proxy registry port (e.g., `8080`)

### Proxy Server Configuration
- `PROXY_USER` - Proxy authentication user (e.g., `proxyuser`)
- `SOCKS5_PORT` - SOCKS5 proxy port (e.g., `1080`)
- `HTTP_PROXY_PORT` - HTTP proxy port (e.g., `3128`)
- `IP_CHECK_INTERVAL` - IP check interval in seconds (e.g., `300`)
- `IP_CHECK_URL` - IP check service URL (e.g., `https://api.ipify.org`)
- `IP_UPDATE_ENDPOINT` - Endpoint to update IP (e.g., `http://10.0.0.5:8080/api/proxies/update`)
- `PROXY_ALLOWED_IPS` - Comma-separated allowed IPs (can be empty)

### Worker Configuration
- `PROXY_TIMEOUT` - Proxy timeout in seconds (e.g., `30`)
- `PROXY_RETRY_COUNT` - Proxy retry count (e.g., `3`)
- `PROXY_ROTATION_INTERVAL` - Proxy rotation interval in seconds (e.g., `300`)
- `WORKER_CONCURRENCY` - Worker concurrency (e.g., `2`)
- `WORKER_LOG_LEVEL` - Log level (e.g., `info`)
- `WORKER_NAME` - Worker name (e.g., `scrape-worker`)
- `PLAYWRIGHT_TIMEOUT` - Playwright timeout in ms (e.g., `30000`)
- `PLAYWRIGHT_HEADLESS` - Run headless (e.g., `true`)

### Scraping Configuration
- `USER_AGENT` - User agent string (e.g., `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36`)
- `MAX_RETRIES` - Max retries for failed requests (e.g., `3`)
- `DOWNLOAD_DELAY` - Delay between requests in seconds (e.g., `1`)
- `CONCURRENT_REQUESTS` - Concurrent requests (e.g., `5`)

### Monitoring Configuration
- `LOG_LEVEL` - Application log level (e.g., `info`)
- `ENABLE_METRICS` - Enable metrics collection (e.g., `true`)

### Caddy Configuration
- `CADDY_DOMAIN` - Domain for Caddy (e.g., `superdeploy.io` or IP)
- `CADDY_EMAIL` - Email for Let's Encrypt (e.g., `admin@superdeploy.io`)

## Configuration Checklist

Before running any workflow:

- [ ] All secrets added to Forgejo
- [ ] All variables added to Forgejo
- [ ] External IPs match actual VM public IPs
- [ ] Internal IPs match actual VM private IPs
- [ ] Ports are consistent across all configurations
- [ ] SSH keys are properly configured on VMs

## Failure Modes

If any required variable/secret is missing:

1. **Ansible workflows**: Will fail with "undefined variable" error
2. **Docker Compose**: Containers will fail to start with empty env vars
3. **Actions**: Workflow will fail at env generation step

This is **by design** - fail-fast ensures you catch configuration issues immediately rather than at runtime.

## Example: Adding Variables in Forgejo

1. Navigate to: `Repository → Settings → Actions → Variables`
2. Click "Add Variable"
3. Name: `CORE_EXTERNAL_IP`
4. Value: `34.56.43.99`
5. Click "Add"
6. Repeat for all required variables

## Example: Adding Secrets in Forgejo

1. Navigate to: `Repository → Settings → Actions → Secrets`
2. Click "Add Secret"
3. Name: `POSTGRES_PASSWORD`
4. Value: `your_secure_random_password_here`
5. Click "Add"
6. Repeat for all required secrets

## Security Best Practices

1. **Never** commit secrets to Git
2. Use **strong random passwords** for all credentials
3. Rotate secrets regularly
4. Use different passwords for each service
5. Keep external IPs up to date if VMs are recreated
6. Use firewall rules to restrict access between VMs

s