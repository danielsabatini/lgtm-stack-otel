# LGTM Stack

Stack de observabilidade com Grafana, Alloy, Loki, Mimir e Tempo.

## O que este repositório entrega

- `compose.yaml`: stack principal.
- `alloy-agent/`: coleta local de métricas e logs.
- `alloy-gateway/`: entrada OTLP e fanout para Loki, Mimir e Tempo.
- `grafana/provisioning/`: datasources e dashboards provisionados.
- `examples/`: templates de agentes e cenários legados.

## Documentação oficial do repositório (Governança)

> [!IMPORTANT]
> **Regra de Governança (Single Source of Truth):** Cada arquivo `.md` neste repositório é a **única referência da verdade** sobre o seu respectivo tema. É terminantemente proibido duplicar informações técnicas (como sizing, comandos de backup ou configurações de rede) entre arquivos. Sempre referencie o documento original através de links.

- [ARCHITECTURE.md](ARCHITECTURE.md): topologia, papéis de cada componente e fronteiras de rede.
- [INFRASTRUCTURE.md](INFRASTRUCTURE.md): setup físico, disco e volumes.
- [SIZING.md](SIZING.md): dimensionamento, projeção de custos e limites de hardware.
- [BACKUP.md](BACKUP.md): backup, snapshot e disaster recovery.
- [UPGRADE.md](UPGRADE.md): processo de upgrade e validações.
- [METRICS.md](METRICS.md): política de métricas, labels e retenção no Mimir.
- [LOGS.md](LOGS.md): política de logs, labels e retenção no Loki.
- [TRACES.md](TRACES.md): ingestão OTLP e política de traces no Tempo.
- [DASHBOARDS.md](DASHBOARDS.md): templates de dashboard para diferentes tipos de host.
- [CHANGELOG.md](CHANGELOG.md): histórico de versões e mudanças.
- [CONTRIBUTING.md](CONTRIBUTING.md): guia de contribuição e governança técnica.
- [ROADMAP.md](ROADMAP.md): visão de futuro e próximas funcionalidades.

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

## Endpoints e Topologia de Rede

Para verificar quais portas a stack expõe nativamente, a responsabilidade de cada componente e como o isolamento de rede foi desenhado (ex: o motivo do Loki, Mimir e Tempo não exporem portas no host), consulte o documento oficial de topologia:

👉 **[ARCHITECTURE.md (Fronteiras de Rede)](ARCHITECTURE.md)**


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
| Windows + SQL Server | [examples/windows-mssql/INSTALL.md](examples/windows-mssql/INSTALL.md) |
| Coleta via Pull: Linux + MySQL | [examples/remote-scrape/INSTALL.md#linux--dbaas-mysql) |
| Coleta via Pull: Linux + PostgreSQL | [examples/remote-scrape/INSTALL.md#linux--dbaas-postgresql) |
| Coleta via Pull: Outras plataformas | [examples/remote-scrape/INSTALL.md](examples/remote-scrape/INSTALL.md) |

> Para atualizar as configurações em servidores já instalados: `git pull` no
> diretório clonado e reinicie o serviço Alloy.

---

## Termo de Responsabilidade e Suporte MGC

**Não Homologação:** Esta solução (*LGTM Stack*) é uma arquitetura de referência baseada em projetos *Open Source* de terceiros (Grafana, Alloy, Loki, Mimir, Tempo) rodando no espaço do usuário (via Docker). Ela **não é** um produto gerenciado (PaaS) ou homologado nativamente pela Magalu Cloud para ambientes de produção de alta criticidade.

**Limites do Suporte MGC:** O suporte oficial da Magalu Cloud se limita exclusivamente à infraestrutura subjacente: disponibilidade das instâncias (MGC Compute), conectividade de rede (VPC/Internet) e o funcionamento das APIs de infraestrutura (como Block Storage ou Object Storage). O suporte da MGC **não cobre** a depuração de problemas relacionados ao processo dos containers da stack (ex: travamentos por OOM Kill, lentidão em queries, alto consumo de CPU pelo Grafana Alloy, ou erros de permissão interna). Esses são considerados problemas de nível de aplicação, de responsabilidade do cliente.

**Responsabilidade do Cliente:** Ao optar por esta arquitetura, o cliente assume o papel de administrador e mantenedor da solução. O cliente tem total responsabilidade pelo monitoramento da saúde dos containers, pelo dimensionamento correto da infraestrutura (sizing), pelas rotinas de backup, gerenciamento de credenciais (arquivo `.env`) e pelos impactos de performance e estabilidade gerados pelo volume de telemetria ingerido.
