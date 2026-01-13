# CI/CD with Tailscale - Summary

## What Changed

Your CI/CD pipeline now uses **Tailscale for ephemeral, private network connections** instead of requiring publicly accessible servers.

## Key Benefits

✅ **No Public Exposure** - Servers stay private on your Tailscale network
✅ **Ephemeral Connections** - GitHub Actions connects temporarily during deployment
✅ **Zero Trust Security** - Strong OAuth authentication
✅ **No VPN Complexity** - Simple, automatic network mesh
✅ **Better Security** - No open ports to the internet

## Updated Workflows

Both deployment workflows now include:

```yaml
- name: Connect to Tailscale
  uses: tailscale/github-action@v2
  with:
    oauth-client-id: ${{ secrets.TS_OAUTH_CLIENT_ID }}
    oauth-secret: ${{ secrets.TS_OAUTH_SECRET }}
    tags: tag:ci
```

This step runs before SSH connection, allowing the GitHub Actions runner to join your private Tailscale network.

## Required Setup

### 1. Tailscale OAuth Client

Create at: https://login.tailscale.com/admin/settings/oauth

- **Name**: GitHub Actions CI/CD
- **Tags**: `tag:ci`
- **Scopes**: Devices: Write

Add credentials to GitHub secrets:

- `TS_OAUTH_CLIENT_ID`
- `TS_OAUTH_SECRET`

### 2. Server Hostnames

Update GitHub secrets to use Tailscale hostnames:

```
TEST_SERVER_HOST=test-server  # or test-server.tail1234.ts.net
PROD_SERVER_HOST=prod-server  # or prod-server.tail1234.ts.net
```

### 3. Tailscale ACL (Optional but Recommended)

Tag your servers and configure ACL:

```json
{
  "tagOwners": {
    "tag:ci": ["autogroup:admin"],
    "tag:server": ["autogroup:admin"]
  },
  "acls": [
    {
      "action": "accept",
      "src": ["tag:ci"],
      "dst": ["tag:server:22"]
    }
  ]
}
```

On each server:

```bash
sudo tailscale up --advertise-tags=tag:server
```

## Deployment Flow

```
1. Push to GitHub
2. Workflow starts
3. Runner connects to Tailscale network (ephemeral)
4. Runner SSHs to server via Tailscale hostname
5. Deployment completes
6. Runner disconnects from Tailscale (automatic)
7. No trace left in your network
```

## Documentation

- 📘 [TAILSCALE_SETUP.md](./TAILSCALE_SETUP.md) - Complete Tailscale configuration guide
- 🚀 [CICD_QUICKSTART.md](./CICD_QUICKSTART.md) - Updated quick start with Tailscale
- 📖 [CICD.md](./CICD.md) - Full CI/CD documentation

## Monitoring

During deployment, check [Tailscale Admin > Machines](https://login.tailscale.com/admin/machines):

- You'll see a temporary machine with tag `tag:ci`
- It appears during deployment
- It automatically disappears after workflow completes

## Troubleshooting

### Can't connect to server

1. Verify server is on Tailscale:

   ```bash
   ssh user@server
   tailscale status
   ```

2. Check ACL allows `tag:ci` → `tag:server:22`

3. Verify OAuth credentials in GitHub secrets

4. Use full hostname: `test-server.tail1234.ts.net`

### Still need help?

See [TAILSCALE_SETUP.md](./TAILSCALE_SETUP.md) troubleshooting section.

## Security Notes

- ✅ Servers never exposed to public internet
- ✅ All traffic encrypted end-to-end by Tailscale
- ✅ GitHub Actions runner exists only during deployment
- ✅ OAuth provides strong authentication
- ✅ ACLs provide granular access control
- ✅ Audit trail in Tailscale logs

## What Stays the Same

- ✅ Same deployment scripts
- ✅ Same Docker configuration
- ✅ Same monitoring and logging
- ✅ Same backup and rollback procedures
- ✅ Same application architecture

Only the **network connection method** changed!
