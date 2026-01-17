# Single Server Deployment Migration Guide

## Overview

This guide helps you migrate from a two-server deployment (separate test and production servers) to a **single server deployment** where both test and production environments coexist on the same server.

## What Changed?

### Before (Two Servers)
- **Test Environment**: Deployed to `test-server` (8000, 3000)
- **Production Environment**: Deployed to `prod-server` (8000, 3000)
- Separate 1Password items: `test-server` and `prod-server`

### After (Single Server)
- **Test Environment**: Deployed to single server in `/opt/place-research-test` (8000, 3000)
- **Production Environment**: Deployed to same server in `/opt/place-research-prod` (8001, 3001)
- Shared 1Password item: `server` (in both Test and Prod vaults)

## Benefits

✅ **Simplified Infrastructure**: Only one server to manage and maintain  
✅ **Cost Savings**: Reduced hosting costs  
✅ **Easier Setup**: Single Tailscale connection, one server to configure  
✅ **Complete Isolation**: Separate directories, networks, and ports ensure no conflicts  

## Migration Steps

### Step 1: Update 1Password Configuration

You need to update the 1Password items in **both** vaults:

#### In "Place Research - Test" Vault:

1. **Rename or create the `server` item** (previously `test-server`):
   - Field: `ssh-private-key` - SSH private key for your server
   - Field: `hostname` - Tailscale hostname (e.g., `place-research-server`)
   - Field: `username` - SSH username (e.g., `ubuntu` or `placeapp`)

2. If you renamed `test-server` to `server`, you're done. Otherwise:
   - Create new item named `server` with the fields above
   - Copy values from old `test-server` item
   - You can delete `test-server` after verifying the deployment works

#### In "Place Research - Prod" Vault:

1. **Rename or create the `server` item** (previously `prod-server`):
   - Field: `ssh-private-key` - **Same SSH key** as in Test vault
   - Field: `hostname` - **Same hostname** as in Test vault (e.g., `place-research-server`)
   - Field: `username` - **Same username** as in Test vault

2. If you renamed `prod-server` to `server`, you're done. Otherwise:
   - Create new item named `server` with the fields above
   - Copy values from old `prod-server` item
   - You can delete `prod-server` after verifying the deployment works

> **Important**: Both vaults should have identical `server` items with the same hostname, username, and SSH key since they deploy to the same physical server.

### Step 2: Setup Single Server

If you're migrating from two servers to one, you need to set up the new server:

1. **Install Tailscale on the server**:
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   sudo tailscale set --hostname place-research-server
   ```

2. **Setup both environments on the same server**:
   ```bash
   # Setup test environment
   sudo bash scripts/setup-server.sh test
   
   # Setup production environment  
   sudo bash scripts/setup-server.sh production
   ```

3. **Verify directory structure**:
   ```bash
   ls -la /opt/
   # Should see:
   # drwxr-xr-x  place-research-test
   # drwxr-xr-x  place-research-prod
   ```

### Step 3: Update Production Environment Port Configuration

Production now uses different ports to avoid conflicts with test:

- **Backend**: Port 8001 (was 8000)
- **Frontend**: Port 3001 (was 3000)

If you have any external configurations (reverse proxies, firewalls, etc.) that reference the production ports, update them to use the new ports.

### Step 4: Copy SSH Key to Server

Ensure your deployment SSH key is authorized on the server:

```bash
# On your local machine
ssh-copy-id -i ~/.ssh/place-research.pub user@place-research-server

# Or manually on the server
cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys
```

### Step 5: Test the Deployment

1. **Test environment deployment**:
   - Push to `develop` or `frontend` branch
   - Monitor the GitHub Actions workflow
   - Check that deployment succeeds
   - Verify services are running: `http://your-server:8000` (backend), `http://your-server:3000` (frontend)

2. **Production environment deployment**:
   - Push to `main` branch
   - Monitor the GitHub Actions workflow
   - Check that deployment succeeds
   - Verify services are running: `http://your-server:8001` (backend), `http://your-server:3001` (frontend)

3. **Verify both environments are isolated**:
   ```bash
   # SSH into server
   ssh user@place-research-server
   
   # Check test environment
   docker ps | grep test
   # Should see: place-research-test-backend, place-research-test-frontend, place-research-test-db
   
   # Check production environment
   docker ps | grep prod
   # Should see: place-research-prod-backend, place-research-prod-frontend, place-research-prod-db
   ```

### Step 6: Cleanup (Optional)

After verifying everything works:

1. **In 1Password**: Delete old `test-server` and `prod-server` items (if you created new `server` items instead of renaming)

2. **Old servers**: If migrating from two servers, you can decommission them:
   - Back up any data you need
   - Remove from Tailscale network
   - Shut down and delete the VMs/instances

## Architecture Details

### Directory Layout on Server
```
/opt/
├── place-research-test/
│   ├── docker/
│   ├── scripts/
│   ├── env/
│   ├── .env.test
│   ├── logs/
│   └── data/
└── place-research-prod/
    ├── docker/
    ├── scripts/
    ├── env/
    ├── .env.prod
    ├── logs/
    └── data/
```

### Port Allocation
| Environment | Backend | Frontend | Database (internal) |
|-------------|---------|----------|---------------------|
| Test        | 8000    | 3000     | 5432                |
| Production  | 8001    | 3001     | 5432                |

### Docker Networks
- **Test**: `test-network` (isolated)
- **Production**: `prod-network` (isolated)

### Container Names
**Test Environment:**
- `place-research-test-backend`
- `place-research-test-frontend`
- `place-research-test-db`

**Production Environment:**
- `place-research-prod-backend`
- `place-research-prod-frontend`
- `place-research-prod-db`

## Troubleshooting

### Deployment fails with "Failed to load secrets from 1Password"

**Cause**: The `server` item doesn't exist in the 1Password vault.

**Solution**:
1. Verify the `server` item exists in the appropriate vault (Test or Prod)
2. Check that field names match exactly: `ssh-private-key`, `hostname`, `username`
3. Ensure your 1Password service account has read access to both vaults

### SSH connection fails

**Cause**: SSH key not authorized or incorrect hostname.

**Solution**:
1. Verify the server is online: `tailscale ping place-research-server`
2. Check SSH key is in authorized_keys: `ssh-add -l`
3. Try manual SSH: `ssh user@place-research-server`
4. Verify hostname in 1Password matches actual Tailscale hostname

### Port conflict errors

**Cause**: Both environments trying to use the same ports.

**Solution**:
1. Verify production docker-compose uses ports 8001 and 3001
2. Check nothing else is using these ports: `sudo lsof -i :8000 -i :8001 -i :3000 -i :3001`
3. Stop conflicting services or change ports

### Environments interfere with each other

**Cause**: Docker networks or volume names conflict.

**Solution**:
1. Verify containers use different networks:
   ```bash
   docker network ls
   # Should see: test-network and prod-network
   ```
2. Check volume names are unique:
   ```bash
   docker volume ls
   # Should see: postgres_test_data and postgres_prod_data
   ```

## Rollback Plan

If you need to rollback to two-server deployment:

1. **In 1Password**:
   - Restore `test-server` and `prod-server` items (or rename `server` back)
   
2. **In Git**:
   - Revert the workflow changes:
     ```bash
     git revert <commit-hash>
     git push origin main
     ```

3. **Redeploy** to your original two servers

## Support

If you encounter issues:

1. Check [GitHub Actions logs](../../actions) for detailed error messages
2. Review [CICD_README.md](CICD_README.md) for general setup
3. See [1PASSWORD_MIGRATION.md](docs/1PASSWORD_MIGRATION.md) for 1Password troubleshooting
4. Open an issue with error details

## Summary

✅ Update 1Password: Rename `test-server`/`prod-server` to `server` in both vaults  
✅ Setup server: Install Tailscale and run setup scripts for both environments  
✅ Update ports: Production uses 8001 (backend) and 3001 (frontend)  
✅ Test deployment: Push to trigger workflows and verify both environments work  
✅ Cleanup: Remove old servers and 1Password items after verification  
