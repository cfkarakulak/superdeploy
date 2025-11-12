# GitHub Actions Integration

The SuperDeploy Dashboard now includes GitHub Actions integration, allowing you to view workflow runs directly from the dashboard.

## Setup

### 1. GitHub Token

The dashboard requires a GitHub token to fetch workflow runs. Add one of the following to your project's `secrets.yml`:

```yaml
secrets:
  shared:
    GITHUB_TOKEN: ghp_your_token_here
    # OR
    GH_TOKEN: ghp_your_token_here
```

You can also set the token as an environment variable:

```bash
export GITHUB_TOKEN=ghp_your_token_here
```

### 2. Token Permissions

The GitHub token needs the following permissions:
- `repo` - Full control of private repositories (or `public_repo` for public repos only)
- `actions:read` - Read access to Actions

To create a token:
1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select the appropriate scopes
4. Copy the token and add it to your `secrets.yml`

### 3. GitHub Configuration

Your project's `config.yml` should include GitHub information:

```yaml
github:
  organization: your-org-name  # or owner: your-username
  # Optional: specify repo name (defaults to project name)
  # repo: custom-repo-name
```

## Features

### Viewing Workflow Runs

1. Navigate to your project in the dashboard
2. Click on the "GitHub Actions" tab
3. View all recent workflow runs with:
   - Status icons (success, failure, in progress, cancelled)
   - Workflow name and run number
   - Branch name
   - Status and conclusion
   - Relative timestamps
   - Direct links to GitHub

### Status Icons

- 🟢 **Green checkmark** - Successful run
- 🔴 **Red X** - Failed run
- 🟡 **Yellow clock** - In progress or queued
- ⚪ **Gray alert** - Cancelled

### Automatic Refresh

Workflow runs are fetched automatically when you switch to the Actions tab. Refresh the page to see the latest runs.

## API Endpoints

The dashboard backend provides these endpoints:

- `GET /api/github/actions/{project_name}` - Get all workflow runs for a project
- `GET /api/github/actions/{project_name}/{run_id}` - Get details of a specific run

## Troubleshooting

### No workflow runs displayed

1. Check that your GitHub token is valid and has the correct permissions
2. Verify that your `config.yml` has the correct GitHub organization/owner
3. Ensure your repository has GitHub Actions workflows configured
4. Check the backend logs for any API errors

### API rate limits

GitHub API has rate limits:
- Authenticated requests: 5,000 requests per hour
- Unauthenticated requests: 60 requests per hour

Always use a token to avoid hitting rate limits.

### 404 errors

If you see 404 errors, check:
1. The repository name matches the project name (or is specified in `config.yml`)
2. The token has access to the repository
3. The repository exists and is accessible

