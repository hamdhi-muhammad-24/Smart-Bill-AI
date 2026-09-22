#!/bin/bash
# ==============================================================================
# SLM-EKB VM Automated Maintenance & Disk Cleanup Script
# Safely reclaims disk space from Docker cache, logs, Ollama failed downloads,
# and temporary directories WITHOUT touching running containers or active data.
# ==============================================================================

set -euo pipefail

echo "========================================================"
echo " Starting SLM-EKB VM Disk Cleanup..."
echo " Date: $(date)"
echo "========================================================"

echo ""
echo "[1/6] Disk usage BEFORE cleanup:"
df -h /

# 1. Clean Ollama incomplete / failed download blobs (major cause of 40GB+ bloat)
echo ""
echo "[2/6] Cleaning incomplete/partial Ollama model downloads..."
if [ -d "/usr/share/ollama/.ollama/models/blobs" ]; then
    rm -f /usr/share/ollama/.ollama/models/blobs/*-partial 2>/dev/null || true
    echo "  -> Cleaned partial Ollama blobs."
else
    echo "  -> Ollama blobs directory not found, skipping."
fi

# 2. Truncate Docker JSON container logs (frees gigabytes without stopping containers)
echo ""
echo "[3/6] Truncating oversized Docker container JSON logs..."
if compgen -G "/var/lib/docker/containers/*/*-json.log" > /dev/null; then
    truncate -s 0 /var/lib/docker/containers/*/*-json.log 2>/dev/null || true
    echo "  -> Docker container logs truncated to 0."
else
    echo "  -> No Docker container logs found."
fi

# 3. Clean Docker build cache and unused dangling images (safe: active containers are preserved)
echo ""
echo "[4/6] Pruning Docker build cache and unused images..."
docker builder prune -a -f || true
docker image prune -f || true
docker volume prune -f || true

# 4. Clean system logs, journals, and crash reports
echo ""
echo "[5/6] Cleaning system journals, crash dumps, and apt cache..."
journalctl --vacuum-size=100M 2>/dev/null || true
find /var/log -type f \( -name "*.gz" -o -name "*.1" -o -name "*.old" \) -delete 2>/dev/null || true
rm -rf /var/crash/* 2>/dev/null || true
rm -rf /root/.cache /root/.npm 2>/dev/null || true
apt-get clean || true
apt-get autoremove -y -qq || true

# 5. Clean stale temporary GMF upload staging files older than 1 day in /tmp
echo ""
echo "[6/6] Cleaning stale temporary staging files in /tmp..."
find /tmp -maxdepth 1 \( -name "slt_gmf_upload_*" -o -name "slt_zip_ext_*" \) -mtime +1 -exec rm -rf {} + 2>/dev/null || true

echo ""
echo "========================================================"
echo " Disk usage AFTER cleanup:"
df -h /
echo "========================================================"
echo " Cleanup completed successfully!"
