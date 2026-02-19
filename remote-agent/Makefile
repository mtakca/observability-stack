SHELL := /bin/bash
.DEFAULT_GOAL := help

RELEASE_NAME ?= remote-agent
NAMESPACE    ?= observability
VALUES_FILE  ?= values.example.yaml

.PHONY: help deps lint template install upgrade diff uninstall status verify

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

deps: ## Download and update Helm dependencies
	helm dependency update .

lint: ## Lint the chart with the specified values file
	helm lint . -f $(VALUES_FILE) --namespace $(NAMESPACE)

template: ## Render templates locally (dry-run)
	helm template $(RELEASE_NAME) . -f $(VALUES_FILE) --namespace $(NAMESPACE) --debug

install: deps ## Install the remote agent
	kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	helm install $(RELEASE_NAME) . -f $(VALUES_FILE) --namespace $(NAMESPACE) --create-namespace

upgrade: deps ## Upgrade the remote agent
	helm upgrade $(RELEASE_NAME) . -f $(VALUES_FILE) --namespace $(NAMESPACE)

diff: deps ## Show diff before upgrade (requires helm-diff plugin)
	helm diff upgrade $(RELEASE_NAME) . -f $(VALUES_FILE) --namespace $(NAMESPACE)

uninstall: ## Uninstall the remote agent
	helm uninstall $(RELEASE_NAME) --namespace $(NAMESPACE)

status: ## Show release status and pod health
	@helm status $(RELEASE_NAME) -n $(NAMESPACE) 2>/dev/null || echo "Release not found"
	@echo ""
	@kubectl get pods -n $(NAMESPACE) -o wide
	@echo ""
	@kubectl get pvc -n $(NAMESPACE)

verify: ## Post-install verification
	@echo "Prometheus:"
	@kubectl get pods -n $(NAMESPACE) -l app=prometheus
	@echo ""
	@echo "Thanos Sidecar Logs:"
	@kubectl logs -n $(NAMESPACE) sts/prometheus -c thanos-sidecar --tail=5 2>/dev/null || echo "Not running"
	@echo ""
	@echo "Promtail:"
	@kubectl get pods -n $(NAMESPACE) -l app.kubernetes.io/name=promtail
	@echo ""
	@echo "OTel Collector:"
	@kubectl get pods -n $(NAMESPACE) -l app=otel-collector 2>/dev/null || echo "Not enabled"
