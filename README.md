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
- [INFRASTRUCTURE.md](INFRASTRUCTURE.md): setup físico, disco e volumes.
- [BACKUP.md](BACKUP.md): backup, snapshot e disaster recovery.
- [UPGRADE.md](UPGRADE.md): processo de upgrade e validações.
- [METRICS.md](METRICS.md): política de métricas, labels e retenção no Mimir.
- [LOGS.md](LOGS.md): política de logs, labels e retenção no Loki.
- [TRACES.md](TRACES.md): ingestão OTLP e política de traces no Tempo.

## Início rápido

> [!IMPORTANT]
> Certifique-se de ter o **Docker** e o **Docker Compose (V2)** instalados antes de prosseguir. Para guias de instalação e requisitos, consulte [INFRASTRUCTURE.md](INFRASTRUCTURE.md).

Para laboratório ou desenvolvimento local:

```bash
git clone <seu-repo> lgtm-stack
cd lgtm-stack
cp .env.example .env
docker compose up -d
```

Para ambiente produtivo com disco dedicado, siga [INFRASTRUCTURE.md](INFRASTRUCTURE.md).

## Lifecycle

```bash
# Subir
docker compose up -d

# Parar (mantém dados)
docker compose down

# Reset completo (apaga todos os dados)
docker compose down -v
```

## Endpoints expostos

| Porta | Serviço | Descrição |
|---|---|---|
| `3000` | **Grafana** | Visualização de dashboards e dados. |
| `12345` | **Alloy Gateway UI** | Status do pipeline de ingestão. |
| `9999` | **Métricas (Gateway)** | Ingestão via Prometheus `remote_write`. |
| `9998` | **Logs (Gateway)** | Ingestão via Loki `push` API. |
| `4317` | **OTLP gRPC** | Ingestão de traces, métricas e logs via gRPC. |
| `4318` | **OTLP HTTP** | Ingestão de traces, métricas e logs via HTTP. |

Loki, Mimir e Tempo não expõem portas no host por design. A justificativa detalhada está em [ARCHITECTURE.md](ARCHITECTURE.md).


## Instalação em servidores remotos

Para monitorar um servidor remoto, clone este repositório no servidor alvo
e siga o guia de instalação da plataforma correspondente:

```bash
git clone <url-do-repositorio> lgtm-stack
cd lgtm-stack/examples/<plataforma>
# siga o INSTALL.md
```

| Plataforma | Guia |
|------------|------|
| Linux (Debian/Ubuntu) | [examples/linux/INSTALL.md](examples/linux/INSTALL.md) |
| Windows | [examples/windows/INSTALL.md](examples/windows/INSTALL.md) |
| MySQL | em breve |
| PostgreSQL | em breve |
| Windows + SQL Server | [examples/windows-mssql/INSTALL.md](examples/windows-mssql/INSTALL.md) |

> Para atualizar as configurações em servidores já instalados: `git pull` no
> diretório clonado e reinicie o serviço Alloy.
