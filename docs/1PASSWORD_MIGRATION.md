# Migration Guide: GitHub Secrets to 1Password

This guide helps you migrate from GitHub Secrets to 1Password for secret management in CI/CD pipelines.

## Overview

The deployment workflows have been updated to use [1Password Service Accounts](https://developer.1password.com/docs/service-accounts/) instead of GitHub Secrets for better security and maintainability.

## Benefits of 1Password

- **Centralized Management**: All secrets in one secure vault
- **Easy Rotation**: Update secrets in 1Password without touching GitHub
- **Audit Trail**: Track when and how secrets are accessed
- **Better Organization**: Logical structure with items and fields
- **Access Control**: Service accounts with minimal required permissions
- **Team Collaboration**: Share access with team members securely

## Migration Steps

### Step 1: Set Up 1Password Vault

1. **Create or use existing vault** named `ci-cd`
2. **Create items** with the following structure:

#### Tailscale
- **Item name**: `tailscale`
  - `oauth-client-id`: Your Tailscale OAuth client ID
  - `oauth-secret`: Your Tailscale OAuth secret

#### Test Server
- **Item name**: `test-server`
  - `ssh-private-key`: SSH private key content
  - `hostname`: Tailscale hostname (e.g., test-server)
  - `username`: SSH username

#### Test Database
- **Item name**: `test-database`
  - `username`: PostgreSQL username
  - `password`: PostgreSQL password
  - `database-name`: Database name

#### Test Secrets
- **Item name**: `test-secrets`
  - `jwt-secret-key`: JWT secret for authentication

#### Production Server
- **Item name**: `prod-server`
  - `ssh-private-key`: SSH private key content
  - `hostname`: Tailscale hostname (e.g., prod-server)
  - `username`: SSH username

#### Production Database
- **Item name**: `prod-database`
  - `username`: PostgreSQL username
  - `password`: PostgreSQL password
  - `database-name`: Database name
  - `port`: PostgreSQL port (e.g., 5432)

#### Production Secrets
- **Item name**: `prod-secrets`
  - `jwt-secret-key`: JWT secret for authentication

#### API Keys
- **Item name**: `api-keys`
  - `google-maps-api-key`: Google Maps API key
  - `google-maps-map-id`: Google Maps Map ID
  - `national-flood-data-api-key`: National Flood Data API key
  - `national-flood-data-client-id`: National Flood Data Client ID
  - `walkscore-api-key`: WalkScore API key
  - `airnow-api-key`: AirNow API key

#### Email Configuration
- **Item name**: `email`
  - `smtp-server`: SMTP server hostname
  - `username`: Email username
  - `password`: Email password
  - `from-address`: From email address

### Step 2: Create Service Account

1. Go to your 1Password account settings
2. Navigate to **Service Accounts**
3. Click **Create Service Account**
4. Configure the service account:
   - **Name**: `github-actions-place-research`
   - **Vaults**: Grant read access to `ci-cd` vault only
5. **Save the token** (you'll only see it once!)

### Step 3: Add Service Account Token to GitHub

1. Go to your GitHub repository
2. Navigate to **Settings > Secrets and variables > Actions**
3. Click **New repository secret**
4. Add:
   - **Name**: `OP_SERVICE_ACCOUNT_TOKEN`
   - **Value**: Paste your 1Password service account token

### Step 4: Verify Migration

Once the service account token is added to GitHub:

1. The next deployment will automatically use 1Password
2. Monitor the workflow run to ensure secrets are loaded correctly
3. Check the "Load secrets from 1Password" step in GitHub Actions

### Step 5: Clean Up Old GitHub Secrets (Optional)

After verifying everything works, you can optionally remove the old GitHub Secrets:

**Test Environment:**
- `TEST_SERVER_SSH_KEY`
- `TEST_SERVER_HOST` (also in Variables)
- `TEST_SERVER_USER` (also in Variables)
- `TEST_POSTGRES_USER` (also in Variables)
- `TEST_POSTGRES_PASSWORD`
- `TEST_POSTGRES_DB` (also in Variables)
- `TEST_JWT_SECRET_KEY`

**Production Environment:**
- `PROD_SERVER_SSH_KEY`
- `PROD_SERVER_HOST` (also in Variables)
- `PROD_SERVER_USER` (also in Variables)
- `PROD_POSTGRES_USER` (also in Variables)
- `PROD_POSTGRES_PASSWORD`
- `PROD_POSTGRES_DB` (also in Variables)
- `PROD_POSTGRES_PORT` (also in Variables)
- `PROD_JWT_SECRET_KEY`

**Tailscale:**
- `TS_OAUTH_CLIENT_ID`
- `TS_OAUTH_SECRET`

**API Keys:**
- `GOOGLE_MAPS_API_KEY`
- `GOOGLE_MAPS_MAP_ID`
- `NATIONAL_FLOOD_DATA_API_KEY`
- `NATIONAL_FLOOD_DATA_CLIENT_ID`
- `WALKSCORE_API_KEY`
- `AIRNOW_API_KEY`

**Email:**
- `EMAIL_SMTP_SERVER` (also in Variables)
- `EMAIL_USERNAME` (also in Variables)
- `EMAIL_PASSWORD`
- `EMAIL_FROM_ADDRESS` (also in Variables)

**Keep only:**
- `OP_SERVICE_ACCOUNT_TOKEN` (required for 1Password)
- `GITHUB_TOKEN` (automatically provided by GitHub Actions)

## Secret Reference Format

Secrets in 1Password are referenced using the format:

```
op://vault-name/item-name/field-name
```

**Examples:**
- `op://ci-cd/test-database/password` - Test database password
- `op://ci-cd/api-keys/google-maps-api-key` - Google Maps API key
- `op://ci-cd/prod-server/ssh-private-key` - Production SSH key

## Troubleshooting

### "Failed to load secrets from 1Password"

**Possible causes:**
1. Service account token not set in GitHub Secrets
2. Service account doesn't have access to the vault
3. Item or field name doesn't match the reference

**Solution:**
- Verify `OP_SERVICE_ACCOUNT_TOKEN` exists in GitHub Secrets
- Check service account has read access to `ci-cd` vault
- Verify item and field names match exactly (case-sensitive)

### "Secret reference not found"

**Possible causes:**
1. Typo in the secret reference path
2. Item or field doesn't exist in 1Password

**Solution:**
- Double-check the reference format: `op://vault/item/field`
- Verify the item and field exist in 1Password
- Ensure field names are lowercase with hyphens (not spaces)

### Workflow fails with authentication errors

**Possible causes:**
1. Secrets not loaded correctly from 1Password
2. Environment variables not exported properly

**Solution:**
- Check the "Load secrets from 1Password" step output
- Verify `export-env: true` is set in the workflow
- Ensure subsequent steps reference `${{ env.VARIABLE_NAME }}`

## Security Best Practices

1. **Use dedicated service accounts** for each project or environment
2. **Grant minimal permissions** - read-only access to required vaults only
3. **Rotate service account tokens** periodically
4. **Monitor access logs** in 1Password for suspicious activity
5. **Use separate vaults** for different sensitivity levels
6. **Never log or expose** the service account token in workflows

## Additional Resources

- [1Password Service Accounts Documentation](https://developer.1password.com/docs/service-accounts/)
- [1Password GitHub Actions](https://github.com/1password/load-secrets-action)
- [1Password Secret References](https://developer.1password.com/docs/cli/secret-references/)

## Support

If you encounter issues during migration:

1. Check the [1Password documentation](https://developer.1password.com)
2. Review GitHub Actions logs for error details
3. Verify vault structure matches the expected format
4. Open an issue in the repository for project-specific help
