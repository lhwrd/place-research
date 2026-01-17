#!/bin/bash
set -e

# =============================================================================
# Server Setup Script for Ubuntu
# =============================================================================
# Prepares an Ubuntu server for hosting the Place Research application
# Run as root or with sudo
# =============================================================================

echo "=========================================="
echo "Place Research - Server Setup"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root or with sudo"
    exit 1
fi

ENVIRONMENT=${1:-test}

if [ "$ENVIRONMENT" = "prod" ]; then
    APP_DIR="/opt/place-research-prod"
    APP_USER="placeapp-prod"
elif [ "$ENVIRONMENT" = "test" ]; then
    APP_DIR="/opt/place-research-test"
    APP_USER="placeapp-test"
else
    echo "Error: Invalid environment. Use 'test' or 'prod'"
    exit 1
fi

echo "Setting up $ENVIRONMENT environment..."
echo "Application directory: $APP_DIR"
echo ""

# Update system
echo "Step 1: Updating system packages..."
apt-get update
apt-get upgrade -y


# Install required packages
echo "Step 2: Installing required packages..."
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    ufw \
    fail2ban \
    unattended-upgrades

# Install 1Password CLI
if ! command -v op &> /dev/null; then
    echo "Step 2b: Installing 1Password CLI..."
    curl -sS https://downloads.1password.com/linux/keys/1password.asc | gpg --dearmor > /usr/share/keyrings/1password-archive-keyring.gpg
    echo 'deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/1password-archive-keyring.gpg] https://downloads.1password.com/linux/debian/amd64 stable main' > /etc/apt/sources.list.d/1password.list
    mkdir -p /etc/debsig/policies/AC2D62742012EA22/
    curl -sS https://downloads.1password.com/linux/debian/debsig/1password.pol | tee /etc/debsig/policies/AC2D62742012EA22/1password.pol
    mkdir -p /usr/share/debsig/keyrings/AC2D62742012EA22
    curl -sS https://downloads.1password.com/linux/keys/1password.asc | gpg --dearmor > /usr/share/debsig/keyrings/AC2D62742012EA22/debsig.gpg
    apt-get update && apt-get install -y 1password-cli
else
    echo "1Password CLI already installed."
fi

# Install Docker if not already installed
if ! command -v docker &> /dev/null; then
    echo "Step 3: Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
else
    echo "Step 3: Docker already installed"
fi

# Install Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "Step 4: Installing Docker Compose..."
    DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
    curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
else
    echo "Step 4: Docker Compose already installed"
fi

# Create application user
echo "Step 5: Creating application user..."
if ! id "$APP_USER" &>/dev/null; then
    useradd -r -m -s /bin/bash $APP_USER
    usermod -aG docker $APP_USER
    echo "Created user: $APP_USER"
else
    echo "User $APP_USER already exists"
fi

# Create application directory
echo "Step 6: Creating application directory..."
mkdir -p $APP_DIR
mkdir -p $APP_DIR/docker
mkdir -p $APP_DIR/scripts
mkdir -p $APP_DIR/backups
mkdir -p $APP_DIR/logs
mkdir -p $APP_DIR/data

chown -R $APP_USER:$APP_USER $APP_DIR

# Setup firewall
echo "Step 7: Configuring firewall..."
ufw --force enable
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp   # HTTP
ufw allow 443/tcp  # HTTPS

if [ "$ENVIRONMENT" = "test" ]; then
    # Allow direct access to services in test environment
    ufw allow 8000/tcp  # Backend
    ufw allow 3000/tcp  # Frontend
fi

echo "Firewall rules:"
ufw status

# Setup fail2ban
echo "Step 8: Configuring fail2ban..."
systemctl enable fail2ban
systemctl start fail2ban

# Setup automatic security updates
echo "Step 9: Enabling automatic security updates..."
cat > /etc/apt/apt.conf.d/50unattended-upgrades << 'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
};
Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
EOF

# Create backup cron job for production
if [ "$ENVIRONMENT" = "production" ]; then
    echo "Step 10: Setting up automated backups..."
    (crontab -u $APP_USER -l 2>/dev/null; echo "0 2 * * * cd $APP_DIR && bash scripts/backup.sh >> logs/backup.log 2>&1") | crontab -u $APP_USER -
    echo "Daily backups scheduled at 2 AM"
fi

# Setup log rotation
echo "Step 11: Configuring log rotation..."
cat > /etc/logrotate.d/place-research << EOF
$APP_DIR/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0644 $APP_USER $APP_USER
    sharedscripts
    postrotate
        docker-compose -f $APP_DIR/docker/docker-compose.${ENVIRONMENT}.yml restart backend frontend 2>/dev/null || true
    endscript
}
EOF

# Create systemd service for auto-start
echo "Step 12: Creating systemd service..."
cat > /etc/systemd/system/place-research-${ENVIRONMENT}.service << EOF
[Unit]
Description=Place Research Application (${ENVIRONMENT})
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$APP_DIR
User=$APP_USER
Group=$APP_USER
ExecStart=/usr/local/bin/docker-compose -f docker/docker-compose.${ENVIRONMENT}.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker/docker-compose.${ENVIRONMENT}.yml down
TimeoutStartSec=0
Environment=OP_SERVICE_ACCOUNT_TOKEN_FILE=/etc/place-research/op-token

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable place-research-${ENVIRONMENT}.service

# Setup SSH key authentication (if not already done)
echo "Step 13: SSH configuration recommendations..."
echo "For security, ensure you:"
echo "  1. Use SSH key authentication"
echo "  2. Disable password authentication"
echo "  3. Disable root login"
echo ""
echo "Edit /etc/ssh/sshd_config and set:"
echo "  PasswordAuthentication no"
echo "  PermitRootLogin no"
echo ""
echo "Then restart SSH: systemctl restart sshd"

# Create helper scripts
echo "Step 14: Creating helper scripts..."

# Helper script: start.sh (inject secrets with op if available)
cat > $APP_DIR/start.sh << 'EOF'
#!/bin/bash
set -e

export OP_SERVICE_ACCOUNT_TOKEN_FILE=/etc/place-research/op-token
ENV_FILE="$APP_DIR/.env.${ENVIRONMENT}"
TEMPLATE_FILE="$APP_DIR/env/${ENVIRONMENT}.env"
if command -v op &> /dev/null && [ -f "$TEMPLATE_FILE" ]; then
    echo "Injecting secrets from 1Password..."
    op inject -i "$TEMPLATE_FILE" -o "$ENV_FILE"
fi
docker compose -f $APP_DIR/docker/docker-compose.${ENVIRONMENT}.yml --env-file "$ENV_FILE" up -d
EOF


# Helper script: stop.sh
cat > $APP_DIR/stop.sh << 'EOF'
#!/bin/bash
docker compose -f $APP_DIR/docker/docker-compose.${ENVIRONMENT}.yml down
EOF


# Helper script: logs.sh
cat > $APP_DIR/logs.sh << 'EOF'
#!/bin/bash
docker compose -f $APP_DIR/docker/docker-compose.${ENVIRONMENT}.yml logs -f "$@"
EOF


# Helper script: status.sh
cat > $APP_DIR/status.sh << 'EOF'
#!/bin/bash
docker compose -f $APP_DIR/docker/docker-compose.${ENVIRONMENT}.yml ps
EOF

chmod +x $APP_DIR/*.sh
chown $APP_USER:$APP_USER $APP_DIR/*.sh

echo ""
echo "=========================================="
echo "✅ Server setup completed!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Setup SSH keys for deployment user"
echo "  2. Add GitHub Container Registry credentials"
echo "  3. Create .env file at: $APP_DIR/.env.${ENVIRONMENT}"
echo "  4. Deploy the application using CI/CD or manually"
echo ""
echo "Application directory: $APP_DIR"
echo "Application user: $APP_USER"
echo ""
echo "Helper commands:"
echo "  Start:  $APP_DIR/start.sh"
echo "  Stop:   $APP_DIR/stop.sh"
echo "  Logs:   $APP_DIR/logs.sh"
echo "  Status: $APP_DIR/status.sh"
echo ""
echo "System service:"
echo "  sudo systemctl start place-research-${ENVIRONMENT}"
echo "  sudo systemctl stop place-research-${ENVIRONMENT}"
echo "  sudo systemctl status place-research-${ENVIRONMENT}"
