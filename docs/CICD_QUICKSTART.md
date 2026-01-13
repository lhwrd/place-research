# CI/CD Quick Start Guide

This guide will help you set up the complete CI/CD pipeline for Place Research.

> 🔒 **Note**: This setup uses Tailscale for secure, private network connections. Your servers will NOT be publicly accessible. See [TAILSCALE_SETUP.md](./TAILSCALE_SETUP.md) for detailed Tailscale configuration.

## 📋 Prerequisites

- [ ] GitHub repository with admin access
- [ ] Two Ubuntu 20.04+ servers (test and production) on your Tailscale network
- [ ] Tailscale account with OAuth client credentials
- [ ] SSH access to both servers via Tailscale
- [ ] Domain names configured (optional but recommended)

## 🚀 Step 1: Configure GitHub Secrets

1. Go to your repository Settings > Secrets and variables > Actions
2. Add the following secrets:

### Tailscale Network Access

```
TS_OAUTH_CLIENT_ID        - Tailscale OAuth client ID
TS_OAUTH_SECRET           - Tailscale OAuth secret
```

> **📖 Detailed Setup**: See [TAILSCALE_SETUP.md](./TAILSCALE_SETUP.md) for complete instructions on:
>
> - Creating OAuth client
> - Configuring ACLs
> - Tagging servers
> - Troubleshooting connections

### Test Environment

```
TEST_SERVER_SSH_KEY       - SSH private key
TEST_SERVER_HOST          - test-server (Tailscale hostname or IP)
TEST_SERVER_USER          - ubuntu (or your username)
TEST_POSTGRES_USER        - place_research_test
TEST_POSTGRES_PASSWORD    - <generate strong password>
TEST_POSTGRES_DB          - place_research_test
TEST_JWT_SECRET_KEY       - <run: openssl rand -hex 32>
```

### Production Environment

```
PROD_SERVER_SSH_KEY       - SSH private key
PROD_SERVER_HOST          - prod-server (Tailscale hostname or IP)
PROD_SERVER_USER          - ubuntu (or your username)
PROD_POSTGRES_USER        - place_research_prod
PROD_POSTGRES_PASSWORD    - <generate strong password>
PROD_POSTGRES_DB          - place_research_prod
PROD_JWT_SECRET_KEY       - <run: openssl rand -hex 32>
```

### API Keys (Shared)

```
GOOGLE_MAPS_API_KEY
GOOGLE_MAPS_MAP_ID
NATIONAL_FLOOD_DATA_API_KEY
NATIONAL_FLOOD_DATA_CLIENT_ID
WALKSCORE_API_KEY
AIRNOW_API_KEY
FBI_API_KEY
```

### Optional

```
SLACK_WEBHOOK             - For deployment notifications
```

## 🔑 Step 2: Setup Tailscale OAuth

1. Go to [Tailscale Admin Console](https://login.tailscale.com/admin/settings/oauth)
2. Click "Generate OAuth client"
3. Configure the client:
   - **Name**: GitHub Actions CI/CD
   - **Tags**: `tag:ci`
   - **Scopes**: Select "Devices: Write"
4. Save the **Client ID** and **Client secret**
5. Add to GitHub secrets:
   - `TS_OAUTH_CLIENT_ID` = Client ID
   - `TS_OAUTH_SECRET` = Client secret

## 🔑 Step 3: Generate and Setup SSH Keys

**Important:** Run the setup script on your server _before_ copying SSH keys. The setup script creates the deployment user (`placeapp-test` or `placeapp-prod`), which must exist before you add their SSH keys.

### On your local machine:

```bash
# Generate deployment keys
ssh-keygen -t ed25519 -C "deploy-test" -f ~/.ssh/place-research-test
ssh-keygen -t ed25519 -C "deploy-prod" -f ~/.ssh/place-research-prod
```

### On the server (after running the setup script):

You cannot log in directly as the app user until their SSH key is set up. Instead, log in as your existing user (e.g., `ubuntu`), then use `sudo` to copy the public key into the app user's authorized_keys:

```bash
# Copy your public key file to the server (e.g., scp or paste it)
# Then, as your existing user (e.g., ubuntu):
sudo mkdir -p /home/placeapp-test/.ssh
sudo cat place-research-test.pub >> /home/placeapp-test/.ssh/authorized_keys
sudo chown -R placeapp-test:placeapp-test /home/placeapp-test/.ssh
sudo chmod 700 /home/placeapp-test/.ssh
sudo chmod 600 /home/placeapp-test/.ssh/authorized_keys

# Repeat for production:
sudo mkdir -p /home/placeapp-prod/.ssh
sudo cat place-research-prod.pub >> /home/placeapp-prod/.ssh/authorized_keys
sudo chown -R placeapp-prod:placeapp-prod /home/placeapp-prod/.ssh
sudo chmod 700 /home/placeapp-prod/.ssh
sudo chmod 600 /home/placeapp-prod/.ssh/authorized_keys
```

After this, you can log in as the app user using SSH:

```bash
ssh -i ~/.ssh/place-research-test placeapp-test@test-server
ssh -i ~/.ssh/place-research-prod placeapp-prod@prod-server
```

# Get private key contents for GitHub secrets

cat ~/.ssh/place-research-test # Copy entire output to TEST_SERVER_SSH_KEY
cat ~/.ssh/place-research-prod # Copy entire output to PROD_SERVER_SSH_KEY

> **Tip**: Use Tailscale MagicDNS names like `test-server` or the full hostname like `test-server.tail1234.ts.net`

## 🖥️ Step 4: Setup Test Server

SSH into your test server via Tailscale:

```bash
ssh user@test-server
```

Run the setup script:

```bash
# Download and run setup script
curl -O https://raw.githubusercontent.com/lhwrd/place-research/main/scripts/setup-server.sh
sudo bash setup-server.sh test
```

This will:

- Install Docker and Docker Compose
- Create application user and directories
- Configure firewall and security
- Setup automated tasks

## 🖥️ Step 5: Setup Production Server

SSH into your production server via Tailscale:

```bash
ssh user@prod-server
```

Run the setup script:

```bash
# Download and run setup script
curl -O https://raw.githubusercontent.com/lhwrd/place-research/main/scripts/setup-server.sh
sudo bash setup-server.sh production
```

## 📝 Step 6: Environment Files — CI/CD Managed

**You do NOT need to manually create or edit `.env.test` or `.env.prod` files on your servers.**

The CI/CD pipeline automatically generates the correct environment files from your GitHub Secrets and securely copies them to the server on every deployment. This ensures your secrets are always up to date and never need to be stored in the repository or manually managed on the server.

**For local development only:**

- You should create a `.env` file in your local project root (not committed to git) using `.env.example` as a template.

**For server deployments:**

- The pipeline will overwrite `/opt/place-research-test/.env.test` and `/opt/place-research-prod/.env.prod` automatically.
- Do not manually edit or create these files on the server—they will be replaced on each deployment.

If you need to update secrets, do so in GitHub repository Settings > Secrets and variables > Actions, then redeploy.

## 🔄 Step 7: Enable GitHub Container Registry

The workflows use GitHub Container Registry (ghcr.io) to store Docker images.

1. Go to repository Settings > Actions > General
2. Scroll to "Workflow permissions"
3. Select "Read and write permissions"
4. Check "Allow GitHub Actions to create and approve pull requests"
5. Save

## ✅ Step 8: Test the Pipeline

### Verify Tailscale Connection

First, ensure GitHub Actions can connect to your Tailscale network:

1. Go to [Tailscale Admin Console](https://login.tailscale.com/admin/machines)
2. After a deployment runs, you should see a temporary machine with tag `tag:ci`
3. This machine will automatically disconnect after the workflow completes

### Test CI/CD

1. Create a new branch from `frontend`:

   ```bash
   git checkout frontend
   git checkout -b test-cicd
   ```

2. Make a small change and push:

   ```bash
   git commit --allow-empty -m "Test CI/CD pipeline"
   git push origin test-cicd
   ```

3. Go to GitHub Actions tab and watch:
   - CI Tests should run
   - Images should build
   - Test deployment should trigger

### Test Production Deployment

1. Merge to main:

   ```bash
   git checkout main
   git merge test-cicd
   git push origin main
   ```

2. Watch GitHub Actions:
   - CI Tests run
   - Images build
   - Production deployment triggers

## 🔍 Step 9: Verify Deployment

### Check Test Environment

```bash
ssh user@test-server
/opt/place-research-test/status.sh
/opt/place-research-test/scripts/health-check.sh
```

Visit: `http://test-server-ip:3000`

### Check Production Environment

```bash
ssh user@prod-server
/opt/place-research-prod/status.sh
/opt/place-research-prod/scripts/health-check.sh
```

Visit: `http://prod-server-ip:3000`

## 🌐 Step 10: Setup Domain and SSL (Optional)

### Install Certbot

On each server:

```bash
sudo apt-get install certbot python3-certbot-nginx
```

### Setup Nginx Reverse Proxy

Create `/etc/nginx/sites-available/place-research`:

```nginx
server {
    listen 80;
    server_name yourapp.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Enable site:

```bash
sudo ln -s /etc/nginx/sites-available/place-research /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Get SSL Certificate

```bash
sudo certbot --nginx -d yourapp.com -d www.yourapp.com
```

## 📊 Step 11: Setup Monitoring (Optional)

### Add Slack Notifications

1. Create a Slack webhook URL
2. Add to GitHub secrets as `SLACK_WEBHOOK`
3. Workflows will send deployment notifications

### Add Uptime Monitoring

Consider using:

- UptimeRobot (free)
- Pingdom
- StatusCake

Monitor:

- `https://yourapp.com`
- `https://api.yourapp.com/health`

## 🎯 Next Steps

Now that CI/CD is set up:

1. **Push to `frontend` branch** → Deploys to test environment
2. **Merge to `main` branch** → Deploys to production
3. **Create version tags** → Tagged releases to production
4. **Monitor deployments** in GitHub Actions
5. **Check logs** on servers when needed

## 📚 Common Commands

### Manual Deployment

```bash
# On server
cd /opt/place-research-{env}
./scripts/deploy.sh {environment} {image-tag}
```

### View Logs

```bash
# All services
/opt/place-research-{env}/logs.sh

# Specific service
/opt/place-research-{env}/logs.sh backend
```

### Create Backup

```bash
cd /opt/place-research-{env}
./scripts/backup.sh
```

### Rollback

```bash
cd /opt/place-research-{env}
./scripts/rollback.sh {environment}
```

### Health Check

```bash
cd /opt/place-research-{env}
./scripts/health-check.sh
```

## ❓ Troubleshooting

### Deployment fails

1. Check GitHub Actions logs
2. SSH to server and check `docker-compose logs`
3. Run health check script
4. Review environment variables

### Can't connect to server

1. Verify SSH key is added to server
2. Check firewall allows SSH (port 22)
3. Verify server IP/hostname is correct

### Images not pulling

1. Check GitHub token permissions
2. Login to registry: `echo $TOKEN | docker login ghcr.io -u USERNAME --password-stdin`
3. Verify image exists in GitHub Packages

## 📖 Full Documentation

For complete details, see [docs/CICD.md](../docs/CICD.md)

## 🎉 You're Done!

Your CI/CD pipeline is now fully operational. Every push will automatically:

- Run tests
- Build Docker images
- Deploy to appropriate environment
- Verify deployment health
- Notify team (if configured)

Happy deploying! 🚀
