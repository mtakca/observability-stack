# Observability Stack

Helm umbrella chart — deploys Grafana, Thanos, Loki, Tempo with HA support and S3 long-term storage.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Grafana (HA + HPA)                        │
│              PostgreSQL backend · Unified Alerting            │
├─────────────┬─────────────────┬──────────────────────────────┤
│  METRICS    │     LOGS        │          TRACES              │
│             │                 │                              │
│ Thanos      │ Loki            │ Tempo                        │
│  ├ Query    │  ├ Distributor  │  ├ Distributor               │
│  ├ Store    │  ├ Ingester     │  ├ Ingester                  │
│  ├ Compactor│  ├ Querier      │  ├ Querier                   │
│  └ Sidecar  │  ├ Compactor    │  ├ Compactor                 │
│             │  └ Scheduler    │  └ Query Frontend            │
│ Prometheus  │                 │                              │
│  ├ Instance0│ Promtail        │ OpenTelemetry Collector       │
│  └ Instance1│ (DaemonSet)     │ (multi-protocol ingest)      │
├─────────────┴─────────────────┴──────────────────────────────┤
│                  S3-Compatible Object Storage                │
│                   (MinIO / AWS S3 / etc.)                    │
└──────────────────────────────────────────────────────────────┘
```

**Deployment model:** This chart deploys a centralized observability platform — one per datacenter/environment, not per application cluster. Remote clusters only need Prometheus + Thanos Sidecar; they ship metrics to the central MinIO. Grafana, Thanos Query, Loki, and Tempo run once and aggregate data from all sources.

## Quick Start

```bash
cp values.example.yaml values.prod.yaml
vim values.prod.yaml   # fill in secrets, endpoints, domains
make install VALUES_FILE=values.prod.yaml
make verify
```

See `SECURITY.md` for secrets management options.

## Structure

```
.
├── Chart.yaml                    # umbrella chart, pinned deps
├── Makefile
├── values.example.yaml           # template — replace all <PLACEHOLDER> values
├── values.schema.json            # helm values validation
├── SECURITY.md
├── charts/
│   ├── common/                   # PostgreSQL, TLS, Grafana secrets, PDBs
│   ├── thanos-stack/             # dual Prometheus + Thanos
│   ├── logging-stack/            # Loki microservices
│   └── tracing-stack/            # Tempo + OTel Collector
├── scripts/
│   ├── generate_alert_values.py
│   ├── deploy_alerts.sh
│   ├── add_alert_rule.py
│   └── delete_alert_rules.py
└── alert-rules/
    └── examples/
```

## Make Targets

| Target | Description |
|--------|-------------|
| `make install` | Install the stack |
| `make upgrade` | Upgrade in place |
| `make diff` | Dry-run diff (needs helm-diff) |
| `make lint` | Lint with values |
| `make template` | Render locally |
| `make verify` | Post-install pod check |
| `make status` | Release + pod status |
| `make alerts-deploy` | Build + apply alert ConfigMaps |
| `make alerts-delete` | Remove alerts via Grafana API |
| `make uninstall` | Tear down |

## Alerts

```bash
python3 scripts/add_alert_rule.py my-rules.yaml my-domain
make alerts-deploy DOMAIN=my-domain
```

The deploy script prunes stale ConfigMaps automatically.

## Multi-Cluster Deployment

This chart deploys the **central hub**. Remote clusters run the `remote-agent/` chart to ship metrics, logs, and traces.

```
                Hub Cluster                          Remote Clusters
    ┌──────────────────────────────┐      ┌─────────────────────────┐
    │  Grafana ◀── Thanos Query   │      │  Prometheus             │
    │               ↕             │◀─S3──│    └─ Thanos Sidecar    │
    │          Thanos Store       │      │  Promtail ──────────────┼──HTTP──▶ Hub Loki
    │  Loki ◀── remote Promtail   │      └─────────────────────────┘
    │  Tempo ◀── OTel Collector   │
    └──────────────────────────────┘
```

**Step 1 — Deploy hub** (this chart):
```bash
helm upgrade --install observability . -n observability -f values.prod.yaml
```

**Step 2 — Enable Loki external access** (in hub `values.prod.yaml`):
```yaml
loki-external:
  ingress:
    enabled: true
    hosts: [loki.observability.example.com]
```

**Step 3 — Deploy remote agent** to each spoke cluster:
```bash
cd remote-agent/
helm upgrade --install remote-agent . -n observability -f values.prod-<cluster>.yaml
```

Each remote agent needs: MinIO endpoint, Loki push URL, cluster name, environment label. See `remote-agent/README.md`.


## Scaling Reference

| Component | Dev | Prod |
|-----------|-----|------|
| Grafana | 1 | 2+ (HPA) |
| Prometheus | 1 | 2 instances |
| Loki Ingester | 1 | 3+ |
| Loki Querier | 1 | 4+ |
| Tempo Ingester | 1 | 3+ |
| OTel Collector | 1 | 2+ |
| Alertmanager | off | 2 (clustered) |

## Chart Dependencies

| Chart | Version |
|-------|---------|
| Grafana | 9.3.1 |
| Promtail | 6.16.6 |
| Node Exporter | 4.46.1 |
| Blackbox Exporter | 9.2.0 |
| Kube State Metrics | 5.27.0 |
| Alertmanager | 1.14.0 |
| Thanos | v0.32.5 |
| Loki | 3.0.0 |
| Tempo | 2.3.1 |
| OTel Collector | 0.89.0 |

## License

MIT
