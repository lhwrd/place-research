# Tailscale Setup for CI/CD

This guide explains how to configure Tailscale for secure, ephemeral connections from GitHub Actions to your private servers.

> 📚 **Official Documentation**: [Tailscale GitHub Action Guide](https://tailscale.com/kb/1276/tailscale-github-action)

## Overview

Your servers are on a private Tailscale network and NOT publicly accessible. GitHub Actions workflows connect to them using ephemeral Tailscale clients that:

- Authenticate using OAuth credentials
- Connect only during deployment
- Automatically disconnect after workflow completes
- Use zero-trust security model
- Run as ephemeral nodes (automatically removed after use)

## Benefits

✅ **No Public Exposure** - Servers don't need public IPs or open ports
✅ **Ephemeral Connections** - CI runners connect temporarily and disconnect
✅ **Zero Trust** - Strong authentication and encryption
✅ **Simple Networking** - No VPN configuration or port forwarding
✅ **Audit Trail** - See all CI connections in Tailscale admin
✅ **Auto Cleanup** - Ephemeral nodes automatically removed when workflow ends

## Step 1: Create OAuth Client

1. Go to [Tailscale Admin Console > Settings > OAuth clients](https://login.tailscale.com/admin/settings/oauth)
2. Click **"Generate OAuth client"**
3. Configure the client:
   - **Description**: `GitHub Actions CI/CD for place-research`
   - Under **Scopes**, check both:
     - ✅ `devices:write` (required - allows creating ephemeral devices)
     - ✅ `auth_keys` (required - allows device authentication)
   - Under **Tags**, add: `tag:ci`
4. Click **"Generate client"**
5. Save the credentials:
   - **Client ID** → GitHub secret `TS_OAUTH_CLIENT_ID`
   - **OAuth secret** → GitHub secret `TS_OAUTH_SECRET`

> ⚠️ **Important**: The OAuth secret is only shown once. Save it immediately!

> 💡 **Tip**: The `tag:ci` tag will be automatically applied to all devices created with this OAuth client, making ACL management easier.

## Step 2: Configure Tailscale ACL

Add ACL rules to allow CI runners to access your servers.

### Recommended: Tag-Based Access

1. Go to [Tailscale Admin Console > Access Controls](https://login.tailscale.com/admin/acls)
2. Update your ACL policy file:

```jsonc
{
  // Define who can manage tags
  "tagOwners": {
    "tag:ci": ["autogroup:admin"], // OAuth client creates these
    "tag:server": ["autogroup:admin"] // You manually tag servers
  },

  // Define access rules
  "acls": [
    {
      "action": "accept",
      "src": ["tag:ci"], // CI runners
      "dst": ["tag:server:22"] // SSH to servers only
    },
    {
      "action": "accept",
      "src": ["tag:ci"],
      "dst": ["tag:server:*"] // Or allow all ports if needed
    }
  ],

  // Enable SSH (optional but recommended)
  "ssh": [
    {
      "action": "accept",
      "src": ["tag:ci"],
      "dst": ["tag:server"],
      "users": ["autogroup:nonroot"] // Restrict to non-root users
    }
  ]
}
```

3. Tag your servers:
   ```bash
   # On each server (test and production)
   sudo tailscale up --advertise-tags=tag:server --accept-routes
   ```

### Alternative: Allow Access to All Devices

If you want CI to access all devices on your network:

```jsonc
{
  "tagOwners": {
    "tag:ci": ["autogroup:admin"]
  },
  "acls": [
    {
      "action": "accept",
      "src": ["tag:ci"],
      "dst": ["*:22"] // SSH to any device
    }
  ]
}
```

## Step 3: Setup Servers on Tailscale

On each server (test and production):

### Install Tailscale

```bash
# Ubuntu/Debian (recommended method)
curl -fsSL https://tailscale.com/install.sh | sh
```

For other operating systems, see: https://tailscale.com/download

### Authenticate and Configure

```bash
# Authenticate with server tag (recommended)
sudo tailscale up --advertise-tags=tag:server --accept-routes

# Verify connection
tailscale status
tailscale ip -4

# Check your server appears in the admin console
# https://login.tailscale.com/admin/machines
```

### Set Hostname (Recommended)

Use descriptive hostnames for easier management:

```bash
# On test server
sudo tailscale set --hostname test-server

# On production server
sudo tailscale set --hostname prod-server

# Verify
tailscale status | grep hostname
```

## Step 4: Configure GitHub Secrets

Add these secrets to your repository (Settings > Secrets and variables > Actions):

```
TS_OAUTH_CLIENT_ID=<your-oauth-client-id>
TS_OAUTH_SECRET=<your-oauth-secret>
TEST_SERVER_HOST=test-server  # or full hostname: test-server.tail1234.ts.net
PROD_SERVER_HOST=prod-server  # or full hostname: prod-server.tail1234.ts.net
```

> 💡 **Tip**: Use MagicDNS names (e.g., `test-server`) for simplicity. They work automatically within your Tailscale network.

## Step 5: Verify GitHub Action Configuration

Your workflows already include the Tailscale connection step:

```yaml
- name: Connect to Tailscale
  uses: tailscale/github-action@v2
  with:
    oauth-client-id: ${{ secrets.TS_OAUTH_CLIENT_ID }}
    oauth-secret: ${{ secrets.TS_OAUTH_SECRET }}
    tags: tag:ci
```

Key points about this action:

- **Ephemeral nodes**: The `tag:ci` automatically makes the connection ephemeral (removed after workflow ends)
- **No version pinning needed**: Using `@v2` is recommended to get automatic updates
- **Automatic cleanup**: Node is removed when the job completes or fails

For advanced configuration options, see: https://tailscale.com/kb/1276/tailscale-github-action

## Step 6: Test Connection

### Manual Test

From your local machine (if you're on the same Tailscale network):

```bash
# Test connectivity
ping test-server
ssh user@test-server

# Verify hostname resolution and tags
tailscale status | grep test-server
```

### GitHub Actions Test

1. Push to your `frontend` branch
2. Go to Actions tab and watch the deployment workflow
3. Open [Tailscale Admin Console > Machines](https://login.tailscale.com/admin/machines)
4. During deployment, you should see an ephemeral machine:
   - Name like `github-runner-xxxxx`
   - Tag: `tag:ci`
   - Status: ⚡ Ephemeral
5. After workflow completes, the machine should disappear automatically

## How It Works

1. **Workflow Starts**

   - GitHub Actions runner starts
   - `tailscale/github-action` authenticates using OAuth credentials

2. **Network Connection**

   - Ephemeral node joins your Tailscale network
   - Automatically tagged with `tag:ci` (from OAuth client)
   - Receives private Tailscale IP address
   - MagicDNS enables hostname resolution

3. **Deployment**

   - Runner can SSH to servers using Tailscale hostnames
   - All traffic encrypted with WireGuard
   - No public internet exposure

4. **Automatic Cleanup**
   - Workflow completes (success or failure)
   - Ephemeral node automatically deregistered
   - No manual cleanup required

## Troubleshooting

### Can't connect to server from workflow

1. **Check workflow logs**:

   - Look for the "Connect to Tailscale" step
   - Verify it completes successfully
   - Check for authentication errors

2. **Verify server is online and reachable**:

   ```bash
   ssh user@server
   tailscale status
   tailscale ping test-server
   ```

3. **Verify ACL configuration**:

   - Go to [Tailscale Admin > Access Controls](https://login.tailscale.com/admin/acls)
   - Ensure `tag:ci` can access `tag:server:22`
   - Test ACL rules using the built-in ACL tester

4. **Check server tags**:

   ```bash
   tailscale status --json | jq '.Self.Tags'
   # Should show: ["tag:server"]
   ```

5. **Check ephemeral node appears**:
   - During workflow execution, check [Machines](https://login.tailscale.com/admin/machines)
   - Look for ephemeral node with `tag:ci`
   - If it doesn't appear, OAuth credentials may be incorrect

### OAuth authentication fails

1. **Verify secrets are correct**:

   - Check `TS_OAUTH_CLIENT_ID` and `TS_OAUTH_SECRET` in GitHub
   - Ensure no extra whitespace or newlines
   - Re-create secrets if unsure

2. **Verify OAuth client configuration**:

   - Go to [OAuth Clients](https://login.tailscale.com/admin/settings/oauth)
   - Ensure client has BOTH required scopes:
     - ✅ `devices:write`
     - ✅ `auth_keys`
   - Ensure client is tagged with `tag:ci`
   - Check client hasn't been revoked or expired

3. **Check workflow logs for specific errors**:

   ```
   Error: failed to authenticate: invalid client credentials
   → OAuth secret is wrong

   Error: The OAuth client requires the auth_keys scope
   → Missing auth_keys scope - recreate OAuth client with both scopes
   ```

### Server hostname not resolving

1. **Verify MagicDNS is enabled**:

   - Check [DNS settings](https://login.tailscale.com/admin/dns)
   - MagicDNS should be enabled for hostname resolution

2. **Use full MagicDNS hostname**:

   ```
   TEST_SERVER_HOST=test-server.tail1234.ts.net
   ```

   Replace `tail1234` with your tailnet name (see Admin Console)

3. **Or use IP address directly**:

   ```bash
   # On server, get Tailscale IP
   tailscale ip -4
   # Example: 100.101.102.103

   # Use in GitHub secret
   TEST_SERVER_HOST=100.101.102.103
   ```

### Connection works locally but not in CI

1. **Ensure server is tagged**:

   ```bash
   # On server
   sudo tailscale up --advertise-tags=tag:server --accept-routes
   ```

2. **Check ACL allows `tag:ci` → `tag:server:22`**:

   ```jsonc
   "acls": [
     {
       "action": "accept",
       "src": ["tag:ci"],
       "dst": ["tag:server:22"]
     }
   ]
   ```

3. **Verify OAuth client permissions**:
   - OAuth client must have both scopes: `devices:write` AND `auth_keys`
   - OAuth client must be tagged with `tag:ci`

### Ephemeral node not cleaning up

This should happen automatically. If nodes persist:

1. **Check workflow completion**:

   - Workflow must complete (success or failure)
   - If workflow is cancelled, node may persist

2. **Manually clean up**:

   - Go to [Machines](https://login.tailscale.com/admin/machines)
   - Find machines with `tag:ci`
   - Click "..." menu → "Delete"

3. **Verify OAuth client tag**:
   - OAuth client MUST have `tag:ci` for ephemeral behavior
   - Without tag, nodes are permanent

## Monitoring

### View Active Connections

```bash
# On server, see all connected devices
tailscale status

# See only active peers
tailscale status --peers

# Watch for CI connections in real-time
watch -n 2 'tailscale status | grep tag:ci'
```

### Monitor in Admin Console

1. **During Deployment**:

   - Go to [Machines](https://login.tailscale.com/admin/machines)
   - Filter by "Ephemeral" or search for `tag:ci`
   - You'll see the GitHub Actions runner

2. **After Deployment**:

   - Ephemeral node automatically disappears
   - No cleanup needed

3. **Network Flow Logs** (if enabled):
   - Go to [Logs](https://login.tailscale.com/admin/logs)
   - Filter by `tag:ci` to see all CI connections
   - Review access patterns and timing

### Audit Trail

- Go to [Settings > Logs](https://login.tailscale.com/admin/logs)
- View configuration changes
- See device additions/removals
- Filter by `tag:ci` for CI-specific events

## Security Best Practices

1. **Use Tagged Devices**:

   - Always tag servers with `tag:server`
   - Restrict CI access with ACLs
   - Never allow `tag:ci` to access untagged devices

2. **Minimal OAuth Scope**:

   - OAuth client needs both `devices:write` AND `auth_keys` scopes
   - Do not grant additional permissions
   - One OAuth client per use case

3. **Rotate Credentials**:

   - Regenerate OAuth credentials periodically
   - Update GitHub secrets after rotation
   - Revoke old credentials in Tailscale admin

4. **Monitor Access**:

   - Review audit logs regularly
   - Set up alerts for unusual activity
   - Monitor ephemeral node creation/deletion

5. **Server Security**:

   - Use SSH keys only (disable password auth)
   - Keep servers updated
   - Use UFW/firewall even on Tailscale
   - Limit sudo access

6. **Network Segmentation**:
   - Use ACLs to limit what CI can access
   - Don't give CI broad network access
   - Test ACL rules before deploying

## Advanced Configuration

### Custom Workflow Configuration

The GitHub Action supports additional parameters:

```yaml
- name: Connect to Tailscale
  uses: tailscale/github-action@v2
  with:
    oauth-client-id: ${{ secrets.TS_OAUTH_CLIENT_ID }}
    oauth-secret: ${{ secrets.TS_OAUTH_SECRET }}
    tags: tag:ci
    # Optional: custom arguments
    args: --accept-routes --ssh
    # Optional: custom hostname
    hostname: github-ci-${{ github.run_id }}
```

See full options: https://tailscale.com/kb/1276/tailscale-github-action#action-parameters

### Multiple CI Environments

Use different tags for different environments:

```jsonc
{
  "tagOwners": {
    "tag:ci": ["autogroup:admin"],
    "tag:ci-test": ["autogroup:admin"],
    "tag:ci-prod": ["autogroup:admin"],
    "tag:test-server": ["autogroup:admin"],
    "tag:prod-server": ["autogroup:admin"]
  },
  "acls": [
    {
      "action": "accept",
      "src": ["tag:ci", "tag:ci-test"],
      "dst": ["tag:test-server:22"]
    },
    {
      "action": "accept",
      "src": ["tag:ci", "tag:ci-prod"],
      "dst": ["tag:prod-server:22"]
    }
  ]
}
```

Then use different OAuth clients for test vs production deployments.

### Subnet Routing

If your servers are behind a subnet router:

1. **Configure subnet router** to advertise routes:

   ```bash
   sudo tailscale up --advertise-routes=192.168.1.0/24 --accept-routes
   ```

2. **Approve routes** in [Tailscale Admin](https://login.tailscale.com/admin/machines)

3. **Update ACLs** to allow CI access to subnet:

   ```jsonc
   "acls": [
     {
       "action": "accept",
       "src": ["tag:ci"],
       "dst": ["192.168.1.0/24:22"]
     }
   ]
   ```

4. **Use subnet IPs** in GitHub secrets:
   ```
   TEST_SERVER_HOST=192.168.1.10
   ```

No changes needed to workflows - they'll automatically route through the subnet router.

## Resources

- **Official Documentation**:

  - [Tailscale GitHub Action](https://tailscale.com/kb/1276/tailscale-github-action)
  - [OAuth Clients](https://tailscale.com/kb/1215/oauth-clients)
  - [ACLs](https://tailscale.com/kb/1018/acls)
  - [Ephemeral Nodes](https://tailscale.com/kb/1111/ephemeral-nodes)
  - [MagicDNS](https://tailscale.com/kb/1081/magicdns)

- **GitHub Action**:

  - [Source Code](https://github.com/tailscale/github-action)
  - [Example Workflows](https://github.com/tailscale/github-action/tree/main/examples)

- **Community**:
  - [Tailscale Community](https://github.com/tailscale/tailscale/discussions)
  - [r/Tailscale](https://www.reddit.com/r/Tailscale/)

## Support

For issues with this setup:

1. **Check this documentation** - Most common issues covered above
2. **Review workflow logs** - GitHub Actions provides detailed output
3. **Check Tailscale Admin Console** - Verify nodes, tags, and ACLs
4. **Test ACLs** - Use the ACL tester in the admin console
5. **Review official docs** - https://tailscale.com/kb/1276/tailscale-github-action

For Tailscale-specific issues:

- [Tailscale Support](https://tailscale.com/contact/support)
- [Community Forum](https://github.com/tailscale/tailscale/discussions)
