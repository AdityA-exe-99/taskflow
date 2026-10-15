# Production + Monitoring (Unna)

Production VM: `aerodeploy-prod`, Azure Australia East, Standard_B2s_v2 (2 vCPU, 8 GB), Ubuntu 24.04.
Public IP: `20.70.170.224`

## Network security group (inbound)

| Rule | Port | Source | Why |
|---|---|---|---|
| Allow-HTTP | 80 | Any | Public website (Nginx) |
| Allow-SSH | 22 | Team IPs | Admin login |
| Allow-SSH-CI | 22 | 4.197.146.206 (CI VM) | Pipeline deploys |
| Allow-Grafana | 3000 | Team IPs | Dashboard |

Prometheus (9090) and Node Exporter (9100) are not exposed; they are only reachable inside the VM.

## Users

- `azureuser`: admin login
- `deploy`: used by the pipeline over SSH; in the `docker` group; owns `/opt/aerodeploy`

## Nginx

Nginx runs on the host and forwards port 80 to the app on `127.0.0.1:8000`.
Config: [`nginx/taskflow.conf`](nginx/taskflow.conf) (install steps are at the top of the file).

## Monitoring

[`monitoring/`](monitoring/) runs Prometheus, Node Exporter and Grafana with Docker Compose.

```bash
cd deploy/monitoring
cp .env.example .env        # then set GRAFANA_PASSWORD
docker compose up -d
```

- Grafana: `http://20.70.170.224:3000` (login required)
- Dashboard: Node Exporter Full (Grafana ID 1860) for CPU, RAM, disk, network
- Prometheus scrapes the VM (Node Exporter) and the app (`web:8000/metrics`)
- Prometheus joins the app's Docker network (`APP_NETWORK`, default `aerodeploy-taskflow_default`), so the app must be running first

### Alerts ([`monitoring/alerts.yml`](monitoring/alerts.yml))

| Alert | Condition |
|---|---|
| HighCPU | CPU > 80% for 5 min |
| HighMemory | RAM > 80% for 5 min |
| DiskAlmostFull | Disk > 85% for 1 min |
| TaskFlowDown | App `/metrics` not responding for 1 min |

## Database

The app's compose file runs PostgreSQL with a named volume, so data survives container restarts and redeploys.
