# Email Notification Setup

SuperDeploy can send email notifications after each deployment.

## Gmail Setup

1. **Enable 2-Factor Authentication** on your Gmail account
   - Go to https://myaccount.google.com/security
   - Enable 2-Step Verification

2. **Generate App Password**
   - Go to https://myaccount.google.com/apppasswords
   - Select "Mail" and "Other (Custom name)"
   - Name it "SuperDeploy"
   - Copy the 16-character password

3. **Add to .env file**
   ```bash
   ALERT_EMAIL=your-email@gmail.com
   SMTP_USER=your-email@gmail.com
   SMTP_PASSWORD=xxxx xxxx xxxx xxxx  # 16-character app password
   ```

4. **Sync secrets to Forgejo**
   ```bash
   superdeploy sync -p cheapa
   ```

## Testing

Deploy any service and check your email:
```bash
# Trigger a deployment from app repo
git push
```

You should receive an email with:
- ✅ Deployment status
- 📦 Service name and image
- 🔗 Git commit SHA
- ⏰ Timestamp

## Troubleshooting

If emails are not arriving:
1. Check spam folder
2. Verify SMTP_PASSWORD is correct (no spaces)
3. Check runner logs: `docker logs <runner-container>`
4. Ensure mailutils is installed on runner VM
