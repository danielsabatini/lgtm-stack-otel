# LGTM Stack

Stack de observabilidade com Grafana, Alloy, Loki, Mimir e Tempo.

## O que este repositório entrega

- `compose.yaml`: stack principal.
- `alloy-agent/`: coleta local de métricas e logs.
- `alloy-gateway/`: entrada OTLP e fanout para Loki, Mimir e Tempo.
- `grafana/provisioning/`: datasources e dashboards provisionados.
- `examples/`: templates de agentes e cenários legados.

## Documentação oficial do repositório

Cada arquivo abaixo é a fonte da verdade do seu próprio tema:

- [ARCHITECTURE.md](ARCHITECTURE.md): topologia, papéis de cada componente e fronteiras de rede.
- [INFRASTRUCTURE.md](INFRASTRUCTURE.md): setup físico, LVM, permissões e diretórios.
- [BACKUP.md](BACKUP.md): backup, snapshot e disaster recovery.
- [UPGRADE.md](UPGRADE.md): processo de upgrade e validações.
- [METRICS.md](METRICS.md): política de métricas, labels e retenção no Mimir.
- [LOGS.md](LOGS.md): política de logs, labels e retenção no Loki.
- [TRACES.md](TRACES.md): ingestão OTLP e política de traces no Tempo.

## Início rápido

Para laboratório ou desenvolvimento local:

```bash
git clone <seu-repo> lgtm-stack
cd lgtm-stack
cp .env.example .env
sudo bash scripts/volumes-init.sh
docker compose up -d
```

Para ambiente produtivo com discos dedicados, siga [INFRASTRUCTURE.md](INFRASTRUCTURE.md).

## Endpoints expostos

- Grafana: `http://localhost:3000`
- Alloy Gateway UI: `http://localhost:12345`
- OTLP gRPC: `localhost:4317`
- OTLP HTTP: `localhost:4318`

Loki, Mimir e Tempo não expõem portas no host. A justificativa está em [ARCHITECTURE.md](ARCHITECTURE.md).

## Templates

Os templates em [examples/](examples) são exemplos de agentes enxutos por plataforma.

- [examples/linux/config.alloy](examples/linux/config.alloy)
- [examples/windows/config.alloy](examples/windows/config.alloy)
- [examples/mysql/config.alloy](examples/mysql/config.alloy)
- [examples/postgresql/config.alloy](examples/postgresql/config.alloy)
- [examples/sqlserver/config.alloy](examples/sqlserver/config.alloy)
- [examples/remote-scrape/README.md](examples/remote-scrape/README.md)
