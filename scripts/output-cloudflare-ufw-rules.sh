#!/bin/bash
set -euo pipefail

for ip in $(curl -s https://www.cloudflare.com/ips-v4) $(curl -s https://www.cloudflare.com/ips-v6); do
  echo "sudo ufw allow proto tcp from $ip to any port 443 comment 'Cloudflare IP'"
done
