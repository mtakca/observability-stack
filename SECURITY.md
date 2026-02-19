# Security

## Secrets

Never commit real values. Replace all `<PLACEHOLDER>` entries in your environment values file.

| Secret | Values Path |
|--------|------------|
| TLS cert/key | `global.ingressCerts.internal.crt` / `.key` |
| S3 access/secret | `global.objectStorage.accessKey` / `.secretKey` |
| Grafana admin | `common.grafana.admin_password` |
| PostgreSQL | `common.postgres.password` |
| Webhook | `grafana.alerting.contactpoints` |

### Option 1: separate values file

```bash
cp values.example.yaml values.prod.yaml
vim values.prod.yaml
helm upgrade observability . -f values.prod.yaml -n observability
```

### Option 2: SOPS

```bash
sops --encrypt --age $(cat ~/.sops/age-key.txt | grep public | cut -d: -f2 | tr -d ' ') \
  values.prod.yaml > values.prod.enc.yaml

sops --decrypt values.prod.enc.yaml | helm upgrade observability . -f - -n observability
```

### Option 3: External Secrets Operator

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: observability-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: grafana-secrets
  data:
    - secretKey: GF_SECURITY_ADMIN_PASSWORD
      remoteRef:
        key: observability/grafana
        property: admin_password
```

### TLS

You can also create the secret directly instead of managing it through Helm:

```bash
kubectl create secret tls ingress-internal-tls \
  --cert=path/to/tls.crt \
  --key=path/to/tls.key \
  -n observability
```

## Vulnerability Reporting

Open a private issue or contact the maintainers directly.
