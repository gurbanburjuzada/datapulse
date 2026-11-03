#!/usr/bin/env bash
# deploy_aws.sh — Step-by-step AWS EC2 deployment for DataPulse
#
# Run this ON THE EC2 INSTANCE after SSH-ing in.
# The comments explain every command so you understand what you're doing.
#
# Pre-requisites (done in AWS console before running this):
#   1. Launch a t2.micro EC2 instance (Ubuntu 22.04 LTS)
#   2. In Security Groups, allow:
#        - SSH   (port 22)  from YOUR IP only
#        - HTTP  (port 80)  from anywhere (0.0.0.0/0)
#   3. Download the .pem key, chmod 400 it
#   4. SSH in: ssh -i your-key.pem ubuntu@<ec2-public-ip>

set -e  # exit on first error

echo "=== DataPulse EC2 Deployment ==="

# ── 1. System update ──────────────────────────────────────────────────────────
echo ">> Updating system packages..."
sudo apt-get update -q && sudo apt-get upgrade -yq

# ── 2. Install Docker ─────────────────────────────────────────────────────────
echo ">> Installing Docker..."
sudo apt-get install -yq ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update -q
sudo apt-get install -yq docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add ubuntu user to docker group (no sudo needed for docker commands)
sudo usermod -aG docker ubuntu
echo ">> Docker installed. Log out and back in for group change to take effect."

# ── 3. Install Nginx ──────────────────────────────────────────────────────────
echo ">> Installing Nginx..."
sudo apt-get install -yq nginx apache2-utils

# ── 4. Clone / copy your project ──────────────────────────────────────────────
# Option A: if you pushed to GitHub:
#   git clone https://github.com/YOUR_USERNAME/datapulse.git ~/datapulse
# Option B: scp from your local machine (run on YOUR machine, not the EC2):
#   scp -i your-key.pem -r ./datapulse ubuntu@<ec2-ip>:~/datapulse
echo ">> [Manual step] Copy your project to ~/datapulse"

# ── 5. Set environment variables ──────────────────────────────────────────────
echo ">> Creating .env file..."
# Replace YOUR_GEMINI_API_KEY with your actual key
cat > ~/datapulse/.env << 'ENV'
OPENAI_API_KEY=YOUR_OPENAI_API_KEY_HERE
ENV
echo ">> Edit ~/datapulse/.env and add your real OpenAI API key"

# ── 6. Build and start Docker containers ──────────────────────────────────────
echo ">> Building Docker containers (this takes a few minutes first time)..."
cd ~/datapulse
docker compose build
docker compose up -d     # -d = detached (runs in background)

# ── 7. Set up Nginx with Basic Auth ───────────────────────────────────────────
echo ">> Configuring Nginx..."

# Create password file — you'll be prompted to enter the password
echo -n "Enter the access password for DataPulse (share this in your resume): "
read -s HTPASSWD_PASS
echo
echo "datapulse:$(openssl passwd -apr1 $HTPASSWD_PASS)" | sudo tee /etc/nginx/.htpasswd

# Copy our nginx config
sudo cp ~/datapulse/nginx/nginx.conf /etc/nginx/sites-available/datapulse
sudo ln -sf /etc/nginx/sites-available/datapulse /etc/nginx/sites-enabled/datapulse
sudo rm -f /etc/nginx/sites-enabled/default   # remove default page

# Test and reload
sudo nginx -t && sudo systemctl reload nginx

# ── 8. Verify deployment ──────────────────────────────────────────────────────
echo ""
echo "=== Deployment complete! ==="
echo ""
echo "Your EC2 public IP: $(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
echo ""
echo "Access URL: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
echo "Username:   datapulse"
echo "Password:   (the one you just entered)"
echo ""
echo "Useful commands:"
echo "  docker compose logs -f          # stream live logs"
echo "  docker compose ps               # check container status"
echo "  docker compose restart backend  # restart after code changes"