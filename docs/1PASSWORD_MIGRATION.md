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

### Step 1: Understand the Architecture

The new setup uses:
- **Environment file templates** (`env/test.env` and `env/prod.env`) stored in the repository with 1Password secret references
- **1Password CLI** (`op inject`) to replace secret references with actual values during deployment
- **Service account token** as the only GitHub Secret needed

These template files contain references like `op://ci-cd/database/password` instead of actual secrets, making them safe to commit to version control.

### Step 2: Set Up 1Password Vault

1. **Create or use existing vault** named `ci-cd`
2. **Create items** with the following structure:

**Note:** The repository includes template env files (`env/test.env` and `env/prod.env`) that reference these 1Password items. The CI/CD workflow uses `op inject` to replace the references with actual secret values during deployment.

#### Tailscale
- **Item name**: `tailscale`
  - `oauth-client-id`: Your Tailscale OAuth client ID
  - `oauth-secret`: Your Tailscale OAuth secret

#### Test Server
- **Item name**: `server`
  - `ssh-private-key`: SSH private key content (same key for both test and prod)
  - `hostname`: Tailscale hostname (e.g., place-research-server)
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
- **Item name**: `server`
  - `ssh-private-key`: SSH private key content (same key for both test and prod)
  - `hostname`: Tailscale hostname (e.g., place-research-server)
  - `username`: SSH username

**Note**: Both test and production environments use the same server configuration in 1Password, as they deploy to the same physical server but in different directories with different ports.

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

### Step 3: Create Service Account

1. Go to your 1Password account settings
2. Navigate to **Service Accounts**
3. Click **Create Service Account**
4. Configure the service account:
   - **Name**: `github-actions-place-research`
   - **Vaults**: Grant read access to `ci-cd` vault only
5. **Save the token** (you'll only see it once!)

### Step 4: Add Service Account Token to GitHub

1. Go to your GitHub repository
2. Navigate to **Settings > Secrets and variables > Actions**
3. Click **New repository secret**
4. Add:
   - **Name**: `OP_SERVICE_ACCOUNT_TOKEN`
   - **Value**: Paste your 1Password service account token

### Step 5: Verify Migration

Once the service account token is added to GitHub:

1. The next deployment will automatically use 1Password
2. Monitor the workflow run to ensure secrets are loaded correctly
3. Check the "Load secrets from 1Password" step in GitHub Actions

### Step 6: Clean Up Old GitHub Secrets (Optional)

After verifying everything works, you can optionally remove the old GitHub Secrets:

**Test Environment:**
- `TEST_SERVER_SSH_KEY` (now uses `SERVER_SSH_KEY` from 1Password)
- `TEST_SERVER_HOST` (now uses `SERVER_HOST` from 1Password)
- `TEST_SERVER_USER` (now uses `SERVER_USER` from 1Password)
- `TEST_POSTGRES_USER`
- `TEST_POSTGRES_PASSWORD`
- `TEST_POSTGRES_DB`
- `TEST_JWT_SECRET_KEY`

**Production Environment:**
- `PROD_SERVER_SSH_KEY` (now uses `SERVER_SSH_KEY` from 1Password)
- `PROD_SERVER_HOST` (now uses `SERVER_HOST` from 1Password)
- `PROD_SERVER_USER` (now uses `SERVER_USER` from 1Password)
- `PROD_POSTGRES_USER`
- `PROD_POSTGRES_PASSWORD`
- `PROD_POSTGRES_DB`
- `PROD_POSTGRES_PORT`
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
- `op://Place Research - Test/postgres/password` - Test database password
- `op://Place Research - Test/google-maps/credential` - Google Maps API key
- `op://Place Research - Prod/server/private key?ssh-format=openssh` - Server SSH key (used by both environments)

## Environment File Templates

The repository includes environment file templates with 1Password secret references:
- `env/test.env` - Test environment configuration
- `env/prod.env` - Production environment configuration

These files contain references like `POSTGRES_PASSWORD="op://ci-cd/test-database/password"` instead of actual secrets. During deployment, the workflow runs `op inject -i env/test.env -o .env.test` to replace all references with actual values from 1Password.

**Benefits:**
- Version controlled configuration templates
- No secrets in repository
- Easy to see what secrets are needed
- Can be updated without touching workflows

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
