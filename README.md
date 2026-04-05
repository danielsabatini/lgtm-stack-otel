# LGTM Stack

Stack de observabilidade completa baseada em componentes open-source da Grafana Labs. Coleta **métricas**, **logs** e **traces** de forma integrada, com correlação nativa entre os três sinais operando de maneira completamente blindada (Zero-Trust).

## 📚 Documentação (Single Source of Truth)

Para manter a organização e escalabilidade deste repositório, separamos as definições matemáticas, arquiteturais e de Setup Físico em documentos especialistas focados. Consulte-os abaixo antes de operar ou enviar dados para o seu Host:

- 🏗️ **[ARCHITECTURE.md](ARCHITECTURE.md)** — Topologia do Docker, Alloy Gateway vs Alloy Agent, e filosofia Zero-Trust.
- ⚙️ **[INFRASTRUCTURE.md](INFRASTRUCTURE.md)** — Roteiro oficial de setup (Scripts LVM), limites restritos de CPU/RAM, e provisionamento de HDs físicos.
- 📈 **[METRICS.md](METRICS.md)** — Planejamento do Mimir, dimensionamento, whitelist de componentes do Node Exporter e gestão de TSDB retenções.
- 📋 **[LOGS.md](LOGS.md)** — Armazenamento do Loki, cálculos de GB/dia e uso de filtros estritos omitindo os ruídos do Kernel/Systemd.
- 🔗 **[TRACES.md](TRACES.md)** — Recebimentos do Banco Tempo, integração OTLP e o uso cirúrgico de "Tail Sampling" para cortar descartes.

---

## 🧱 Biblioteca de Templates (Lean Agents)

Disponibilizamos na pasta `examples/` uma curadoria de configurações oficiais (Alloy Agents) moldadas com a nossa filosofia _Lean_ (Coleta Mínima Necessária). Elas devem ser usadas como base pelas equipes que implantarão a coleta nas pontas (Hosts e Bancos) para enviar dados ao nosso Gateway central, poupando recursos na origem.

- 🐧 **[Linux](examples/linux/config.alloy)** — Node Exporter restrito aos "Golden Signals" e filtro cirúrgico no syslog do Docker.
- 🪟 **[Windows](examples/windows/config.alloy)** — Filtros de altíssima performance no banco EventViewer, puxando severidades via `XPath` nativo.
- 🐬 **[MySQL](examples/mysql/config.alloy)** — Mitigação de cardinalidade inútil de _schemas_ e leitura exclusiva de _error.log_.
- 🐘 **[PostgreSQL](examples/postgresql/config.alloy)** — Remoção de lock-metrics invasivos e _Regex_ matando logs triviais de nível INFO.
- 📊 **[SQL Server](examples/sqlserver/config.alloy)** — Coleta global via Exporter MSSQL aliada a um XPath de Provider cruzado.
- 📡 **[Legado / Remote Scrape](examples/remote-scrape)** — Arquitetura de `Pull Scrape` via módulos, protegendo contra *node_exporters* clássicos invasivos em clusters não gerenciados.

---

## 🚀 Componentes Base

| Imagem Original | Versão Bloqueada |
|---|---|
| `grafana/grafana` | `12.4.2` |
| `grafana/alloy` | `1.15.0` |
| `grafana/loki` | `3.7.1` |
| `grafana/mimir` | `3.0.5` |
| `grafana/tempo` | `2.10.3` |

---

## ⚡ Guia de Início Rápido (Local / Desenvolvimento)

Para testes rápidos em laboratório (laptop ou VM), você pode subir todo o ecossistema utilizando seu disco principal, sem as amarras físicas e scripts paralelos do _Linux LVM_.
**Espaço em Disco Mínimo Exigido:** Recomendado ao menos `10 GB` livres para não atritar os _buffers_.

1. **Clone e Copie o Arquivo Base:**
```bash
git clone <seu-repo> lgtm-stack
cd lgtm-stack
cp .env.example .env
```

2. **Crie Volumes Docker Virtuais Genéricos:**
```bash
docker volume create grafana-data
docker volume create alloy-gateway-data
docker volume create alloy-agent-data
docker volume create loki-data
docker volume create mimir-data
docker volume create tempo-data
```

3. **Inicie Mágica:**
```bash
docker compose up -d
```

---

## 🏢 Guia de Produção (Enterprise High-Load)

Em cenários produtivos que exigirão alta ingestão de traces ou logs de dezenas de microsserviços, **NÃO crie volumes fantasmas normais como acima**. O ambiente exaure rapidamente a velocidade de I/O de um único disco e as bases _Corrompem_.

Neste caso, orquestramos _Mount Pointers_ usando partições LVM exclusivas (`/dev/vdb`, `vdc`, etc) com `UIDs` precisos de sistema.
Para subir o ambiente produtivo com segurança blindada, siga nosso roteiro tático exclusivo: 
**👉 [Leia o roteiro de subida em INFRASTRUCTURE.md](INFRASTRUCTURE.md)**

---

## 🖥️ Acessar os Serviços

Após iniciar e provisionar o stack (Veja \`INFRASTRUCTURE.md\`), aguarde todos os containers ficarem integrados e saudáveis:

```bash
docker compose ps
```

| Serviço | URL Exposta | Credenciais Fixadas |
|---|---|---|
| Grafana | http://localhost:3000 | \`admin\` / valor customizado em \`GF_ADMIN_PASSWORD\` |
| Alloy Gateway UI | http://localhost:12345 | Navegação Read-Only Direta |
| Mimir/Loki/Tempo | \`Acesso Bloqueado\` | Por estarem em portas isoladas nativamente (Docker Network), qualquer diagnóstico deles é feito exclusivamente no Grafana via Datasources nativos. |

---

## 📊 Dashboards Provisionados

Os Datasources do Grafana estão roteados para buscar o histórico de Log → Trace → Metrics sem configuração manual necessária.
Nós embarcamos nativamente as visualizações abaixo:

| Pasta Lógica | Dashboard Ativo | Repositório |
|---|---|---|
| **Host** | Node Exporter Full | [ID 1860](https://grafana.com/grafana/dashboards/1860) |
| **Stack** | Logging Dashboard via Loki | [ID 12611](https://grafana.com/grafana/dashboards/12611) |
| **Stack** | Alloy Monitoring | [ID 20475](https://grafana.com/grafana/dashboards/20475) |

> 🧩 **Extensibilidade**: Para plugar mais painéis, efetue o download do layout JSON em Grafana.com, converta as variáveis declarativas e posicione em \`grafana/provisioning/dashboards/\`.

---

## 🛠️ Manutenção Comum

**Diagnóstico rápido em Real-time:**
```bash
docker compose logs -f alloy-gateway
```

**Tombamento a Quente (Hot-Reload):**
```bash
docker compose restart mimir
```

**Destruição Segura (Seus HD/Volumes estão salvos):**
```bash
docker compose down
```
