#!/usr/bin/env bash
# Restore workouts.sqlite from the most recent Azure Blob backup.
#
# Required env vars:
#   AZURE_STORAGE_ACCOUNT   — storage account name
#   AZURE_BACKUP_CONTAINER  — container name (e.g. workout-backups)
#
# Usage: bash restore_db.sh

set -euo pipefail

ACCOUNT="${AZURE_STORAGE_ACCOUNT:?AZURE_STORAGE_ACCOUNT is required}"
CONTAINER="${AZURE_BACKUP_CONTAINER:?AZURE_BACKUP_CONTAINER is required}"
DEST="data/workouts.sqlite"

echo "Listing backups in $ACCOUNT/$CONTAINER..."
LATEST=$(az storage blob list \
  --account-name "$ACCOUNT" \
  --container-name "$CONTAINER" \
  --query "sort_by([].name, &@)[-1]" \
  --output tsv \
  --auth-mode login)

if [ -z "$LATEST" ]; then
  echo "No backups found in $CONTAINER."
  exit 1
fi

echo "Latest backup: $LATEST"
mkdir -p data

if [ -f "$DEST" ]; then
  echo "Existing database found — moving to ${DEST}.bak"
  mv "$DEST" "${DEST}.bak"
fi

echo "Downloading $LATEST -> $DEST..."
az storage blob download \
  --account-name "$ACCOUNT" \
  --container-name "$CONTAINER" \
  --name "$LATEST" \
  --file "$DEST" \
  --auth-mode login

echo "Restored. Verifying..."
python summary.py

echo ""
echo "If this is a fresh Hermes install, seed memory with:"
echo "  cp memory_template.md ~/.hermes/memories/MEMORY.md"
