#!/bin/bash
set -euo pipefail

# Diagnostic script to test Atlas API connection and debug 401 errors.
#
# Prerequisites:
#   - .env file with ATLAS_PUBLIC_KEY and ATLAS_PRIVATE_KEY
#   - curl installed
#   - jq recommended for JSON formatting (brew install jq)

# Check and load .env
if [[ ! -f .env ]]; then
    echo "Error: .env file not found." >&2
    exit 1
fi

# Source .env safely (handles spaces, quotes, etc.)
set -a
source .env
set +a

if [[ -z "${ATLAS_PUBLIC_KEY:-}" ]] || [[ -z "${ATLAS_PRIVATE_KEY:-}" ]]; then
    echo "Error: ATLAS_PUBLIC_KEY or ATLAS_PRIVATE_KEY not set in .env" >&2
    exit 1
fi

echo "✅ Credentials loaded from .env"
echo

# Step 1: Check public IP
echo "🔎 Checking public IP address..."
if PUBLIC_IP=$(curl --silent --max-time 5 ifconfig.me 2>/dev/null); then
    echo "   Your IP: $PUBLIC_IP"
    echo "   → Ensure this IP is on your Atlas API Key Access List"
else
    echo "   ⚠️  Could not determine public IP (network issue?)"
fi
echo

# Step 2: Test API connection
echo "🚀 Testing Atlas API connection..."
HTTP_STATUS=$(curl --user "$ATLAS_PUBLIC_KEY:$ATLAS_PRIVATE_KEY" --digest \
    --header "Accept: application/json" \
    --silent --max-time 10 \
    --output /dev/null --write-out "%{http_code}" \
    "https://cloud.mongodb.com/api/atlas/v1.0/orgs")

echo "   HTTP Status: $HTTP_STATUS"
echo

case "$HTTP_STATUS" in
    200)
        echo "✅ SUCCESS - API connection working"
        ;;
    401)
        echo "❌ FAILED (401 Unauthorized)"
        echo "   Check:"
        echo "   1. Your IP is on the API Access List"
        echo "   2. API keys in .env are correct"
        exit 1
        ;;
    *)
        echo "❌ FAILED (HTTP $HTTP_STATUS)"
        exit 1
        ;;
esac
