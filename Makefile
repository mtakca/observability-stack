SHELL := /bin/bash
.DEFAULT_GOAL := help

RELEASE_NAME ?= observability
NAMESPACE    ?= observability
VALUES_FILE  ?= values.example.yaml
DOMAIN       ?= example

.PHONY: help deps lint template install upgrade diff uninstall alerts-generate alerts-deploy alerts-delete agent-deps agent-lint agent-template agent-install agent-upgrade all-lint all-template status verify

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

deps: ## Download and update Helm dependencies
	helm dependency update .

lint: ## Lint the chart with the specified values file
	helm lint . -f $(VALUES_FILE) --namespace $(NAMESPACE)

template: ## Render templates locally (dry-run)
	helm template $(RELEASE_NAME) . -f $(VALUES_FILE) --namespace $(NAMESPACE) --debug

install: deps ## Install the observability stack
	kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	helm install $(RELEASE_NAME) . -f $(VALUES_FILE) --namespace $(NAMESPACE) --create-namespace

upgrade: deps ## Upgrade the observability stack
	helm upgrade $(RELEASE_NAME) . -f $(VALUES_FILE) --namespace $(NAMESPACE)

diff: deps ## Show diff before upgrade (requires helm-diff plugin)
	helm diff upgrade $(RELEASE_NAME) . -f $(VALUES_FILE) --namespace $(NAMESPACE)

uninstall: ## Uninstall the observability stack
	helm uninstall $(RELEASE_NAME) --namespace $(NAMESPACE)

status: ## Show release status and pod health
	@helm status $(RELEASE_NAME) -n $(NAMESPACE) 2>/dev/null || echo "Release not found"
	@echo ""
	@kubectl get pods -n $(NAMESPACE) -o wide
	@echo ""
	@kubectl get pvc -n $(NAMESPACE)

verify: ## Post-install verification
	@echo "Grafana:"
	@kubectl get pods -n $(NAMESPACE) -l app.kubernetes.io/name=grafana
	@echo ""
	@echo "Prometheus:"
	@kubectl get pods -n $(NAMESPACE) -l app=prometheus
	@echo ""
	@echo "Loki:"
	@kubectl get pods -n $(NAMESPACE) -l app.kubernetes.io/name=loki
	@echo ""
	@echo "Tempo:"
	@kubectl get pods -n $(NAMESPACE) -l app.kubernetes.io/name=tempo
	@echo ""
	@echo "Thanos:"
	@kubectl get pods -n $(NAMESPACE) -l app.kubernetes.io/name=thanos

alerts-generate: ## Generate alert ConfigMaps from rule files
	python3 scripts/generate_alert_values.py "alert-rules/$(DOMAIN)/base-alerts.yaml" "alert-rules/$(DOMAIN)/" "generated_alerts_$(DOMAIN).yaml" "generated_configmaps.txt"

alerts-deploy: alerts-generate ## Generate and deploy alerts with pruning
	bash scripts/deploy_alerts.sh $(DOMAIN)

alerts-delete: ## Delete alert rules via Grafana API
	python3 scripts/delete_alert_rules.py "alert-rules/$(DOMAIN)/" $(NAMESPACE)

# --- Remote Agent ---
AGENT_RELEASE  ?= remote-agent
AGENT_VALUES   ?= remote-agent/values.example.yaml

agent-deps: ## Download remote agent dependencies
	helm dependency update remote-agent/

agent-lint: ## Lint the remote agent chart
	helm lint remote-agent/ -f $(AGENT_VALUES) --namespace $(NAMESPACE)

agent-template: ## Render remote agent templates (dry-run)
	helm template $(AGENT_RELEASE) remote-agent/ -f $(AGENT_VALUES) --namespace $(NAMESPACE) --debug

agent-install: agent-deps ## Install the remote agent
	kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	helm install $(AGENT_RELEASE) remote-agent/ -f $(AGENT_VALUES) --namespace $(NAMESPACE) --create-namespace

agent-upgrade: agent-deps ## Upgrade the remote agent
	helm upgrade $(AGENT_RELEASE) remote-agent/ -f $(AGENT_VALUES) --namespace $(NAMESPACE)

all-lint: lint agent-lint ## Lint both hub and agent charts
	@echo "All charts linted successfully"

all-template: template agent-template ## Render both hub and agent templates
	@echo "All charts rendered successfully"

