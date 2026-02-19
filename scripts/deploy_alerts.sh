#!/bin/bash
set -euo pipefail

# Configuration
DOMAIN="${1:-wallet}"
NAMESPACE="observability"
LABEL_SELECTOR="grafana_alert=1"
BASE_VALUES="values.${DOMAIN}.alerts.yaml"
RULES_DIR="alert-rules/${DOMAIN}/"
OUTPUT_YAML="generated_alerts_${DOMAIN}.yaml"
GENERATED_NAMES_FILE="generated_configmaps.txt"

echo "Starting Alert Deployment with Pruning Strategy..."

# 1. Generate Alert Values and ConfigMap Names
echo "Generating alert values..."
python3 scripts/generate_alert_values.py "$BASE_VALUES" "$RULES_DIR" "$OUTPUT_YAML" "$GENERATED_NAMES_FILE"

# 2. Get Existing ConfigMaps
echo "Fetching existing ConfigMaps..."
EXISTING_CMS=$(kubectl get cm -n "$NAMESPACE" -l "$LABEL_SELECTOR" -o jsonpath='{.items[*].metadata.name}')

# 3. Identify Stale ConfigMaps
echo "Identifying stale ConfigMaps..."
# Read generated names into an array
GENERATED_CMS=()
if [ -f "$GENERATED_NAMES_FILE" ]; then
    IFS=$'\n' read -d '' -r -a GENERATED_CMS < "$GENERATED_NAMES_FILE" || true
fi

STALE_CMS=()
for existing in $EXISTING_CMS; do
    found=false
    for generated in "${GENERATED_CMS[@]:-}"; do
        if [[ "$existing" == "$generated" ]]; then
            found=true
            break
        fi
    done
    if [ "$found" = false ]; then
        STALE_CMS+=("$existing")
    fi
done

# 4. Delete Stale ConfigMaps
if [ ${#STALE_CMS[@]} -gt 0 ]; then
    echo "Found ${#STALE_CMS[@]} stale ConfigMaps. Deleting..."
    for cm in "${STALE_CMS[@]}"; do
        echo "Deleting $cm..."
        kubectl delete cm "$cm" -n "$NAMESPACE"
    done
else
    echo "No stale ConfigMaps found."
fi

# 5. Apply New ConfigMaps
echo "Applying new ConfigMaps..."
kubectl apply -f "$OUTPUT_YAML" -n "$NAMESPACE"

# 6. Restart Grafana to pick up changes immediately
echo "Restarting Grafana..."
kubectl delete pod -n "$NAMESPACE" -l app.kubernetes.io/name=grafana

echo "Deployment completed successfully."
rm "$GENERATED_NAMES_FILE"
