# Observability Remote Agent

Helm chart for remote K8s clusters. Collects metrics, logs, and traces and pushes them to the central observability stack.

## Components

| Component | What it does | Replicas |
|-----------|-------------|----------|
| Prometheus + Thanos Sidecar | Scrapes local metrics, ships 2h blocks to MinIO | 1 (StatefulSet) |
| Promtail | Tails pod logs, pushes to Loki | 1 per node (DaemonSet) |
| OTel Collector | Receives traces (OTLP/Zipkin/Jaeger), forwards to central OTel | 1 (Deployment) |

## Data Flow

```
Remote Cluster                           Central Hub
┌──────────────────────────┐            ┌──────────────────┐
│ Prometheus               │            │                  │
│   └─ Thanos Sidecar ─────┼── S3 ────▶│ Thanos Query     │
│                          │            │ Thanos Store     │
│ Promtail (DaemonSet) ────┼── HTTP ──▶│ Loki             │
│                          │            │                  │
│ OTel Collector ───────────┼── gRPC ──▶│ Tempo            │
│                          │            │                  │
│                          │            │ Grafana           │
└──────────────────────────┘            └──────────────────┘
```

## Usage

```bash
cp values.example.yaml values.prod-wallet.yaml
# Edit: cluster.name, cluster.environment, centralStack.* endpoints

helm dependency update .
helm upgrade --install remote-agent . \
  -n observability --create-namespace \
  -f values.prod-wallet.yaml
```

Or from the root repo:
```bash
make agent-install AGENT_VALUES=remote-agent/values.prod-wallet.yaml
```

## Required Configuration

| Key | Example |
|-----|---------|
| `cluster.name` | `wallet-prod` |
| `cluster.environment` | `production` |
| `centralStack.minioEndpoint` | `minio.observability.svc:9000` |
| `centralStack.lokiEndpoint` | `https://loki.obs.example.com/loki/api/v1/push` |
| `centralStack.otelEndpoint` | `otel-collector.obs.example.com:4317` |

## Verify

```bash
# Prometheus targets
kubectl port-forward -n observability svc/prometheus 9090
curl localhost:9090/api/v1/targets | jq '.data.activeTargets | length'

# Sidecar block upload
kubectl logs -n observability sts/prometheus -c thanos-sidecar --tail=20

# Promtail push
kubectl logs -n observability ds/remote-agent-promtail --tail=20 | grep "sent"

# OTel health
kubectl logs -n observability deploy/otel-collector --tail=10
```
