# Grafana Email Alerts Setup

Grafana runs on the orchestrator VM and provides monitoring for all projects. You can configure email alerts directly in Grafana's UI.

## Quick Setup

### 1. Set SSL Email (Required for HTTPS)

Edit `shared/orchestrator/config.yml`:

```yaml
project:
  name: orchestrator
  ssl_email: "admin@yourdomain.com"  # For Let's Encrypt certificates
```

### 2. Enable SMTP in Orchestrator Config

Edit `shared/orchestrator/config.yml`:

```yaml
grafana:
  domain: "grafana.yourdomain.com"
  port: 3000
  smtp_enabled: true
  smtp_host: "smtp.gmail.com:587"
  smtp_user: "alerts@yourdomain.com"
```

### 3. Add SMTP Password

Edit `shared/orchestrator/.env` and add:

```bash
GRAFANA_SMTP_PASSWORD=your-app-password-here
```

**For Gmail:**
- Use an [App Password](https://support.google.com/accounts/answer/185833)
- Don't use your regular Gmail password

### 4. Redeploy Orchestrator

```bash
superdeploy orchestrator up --skip-terraform --tags addons
```

This will restart Grafana with SMTP enabled.

## Configure Alerts in Grafana

1. **Access Grafana**: `http://orchestrator-ip:3000`
   - Username: `admin`
   - Password: Check `shared/orchestrator/.env` → `GRAFANA_ADMIN_PASSWORD`

2. **Add Contact Point**:
   - Go to: Alerting → Contact points → New contact point
   - Name: `Email Alerts`
   - Type: `Email`
   - Addresses: `your-email@example.com`
   - Test and Save

3. **Create Alert Rule**:
   - Go to: Alerting → Alert rules → New alert rule
   - Example: CPU usage > 80%
   - Set evaluation interval
   - Link to contact point
   - Save

## Common SMTP Providers

### Gmail
```yaml
smtp_host: "smtp.gmail.com:587"
smtp_user: "your-email@gmail.com"
# Use App Password in .env
```

### SendGrid
```yaml
smtp_host: "smtp.sendgrid.net:587"
smtp_user: "apikey"
# Use API key as password in .env
```

### AWS SES
```yaml
smtp_host: "email-smtp.us-east-1.amazonaws.com:587"
smtp_user: "your-smtp-username"
# Use SMTP password in .env
```

## Troubleshooting

### Test SMTP Connection

SSH into orchestrator and check Grafana logs:

```bash
ssh superdeploy@orchestrator-ip
docker logs superdeploy-grafana | grep -i smtp
```

### Common Issues

1. **"SMTP not enabled"**: Make sure `smtp_enabled: true` in config.yml
2. **"Authentication failed"**: Check SMTP password in .env
3. **"Connection timeout"**: Verify SMTP host and port
4. **Gmail blocks login**: Use App Password, not regular password

## Notes

- Grafana runs on orchestrator, not on project VMs
- All projects share the same Grafana instance
- Configure alerts per project using Grafana's UI
- SMTP settings are optional - Grafana works without them
