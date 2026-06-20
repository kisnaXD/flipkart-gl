#!/usr/bin/env bash
# Run on Ubuntu EC2 as ubuntu user after cloning the repo.
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/flipkart-gridlock}"
DOMAIN="${DOMAIN:-65.2.35.241.nip.io}"

echo "==> System packages"
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git

echo "==> Python venv + dependencies"
cd "$APP_DIR"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Train models (one-time)"
python -m src.pipeline

echo "==> Pre-cache OSM graphs for demo scenarios"
PYTHONPATH="$APP_DIR" python scripts/precache_graphs.py || echo "Graph pre-cache skipped (network optional)"

echo "==> systemd service"
sudo cp deploy/gridlock.service /etc/systemd/system/gridlock.service
sudo systemctl daemon-reload
sudo systemctl enable gridlock
sudo systemctl restart gridlock

echo "==> nginx"
sudo cp deploy/nginx-gridlock.conf /etc/nginx/sites-available/gridlock
sudo ln -sf /etc/nginx/sites-available/gridlock /etc/nginx/sites-enabled/gridlock
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

echo "==> SSL via Let's Encrypt (nip.io)"
sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m admin@"$DOMAIN" --redirect || {
  echo "Certbot failed — ensure EC2 security group allows inbound TCP 80 and 443."
  echo "App still available at http://$DOMAIN"
}

echo ""
echo "Done. Open https://$DOMAIN (or http if SSL pending)"
curl -sf "http://127.0.0.1:8000/api/health" && echo ""
