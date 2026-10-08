# Roadmap do Projeto (Visão de Futuro)

> **Referência Técnica:** Este documento estabelece o planejamento evolutivo, os horizontes de entrega e as novas funcionalidades previstas para a LGTM Stack.

---

## 1. Introdução

A LGTM Stack é um projeto dinâmico que evolui continuamente para incorporar as melhores práticas de engenharia de confiabilidade (*SRE*), novos coletores de telemetria e otimizações de performance em ambientes corporativos.

Este roadmap organiza as entregas planejadas em três horizontes temporais bem definidos.

---

## 2. Objetivo

1. **Dar Visibilidade:** Compartilhar com mantenedores e usuários as próximas capacidades da plataforma.
2. **Priorizar Demandas Técnicas:** Garantir que novas integrações respeitem a filosofia Lean Observability e a metodologia de pilares.
3. **Orientar Contribuições:** Servir como guia para desenvolvedores que desejem contribuir com novos templates, pipelines ou regras de alerta.

---

## 3. Planejamento por Horizonte Temporal

### 3.1 Curto Prazo (Q2 2026)
* [x] **Integração PostgreSQL:** Template de coleta remota de DBaaS com filtros granulares (hoje `examples/pull/linux-dbaas-pgsql`).
* [x] **Integração MySQL:** Templates e dashboards provisionados para MySQL / MariaDB.
* [x] **Lean Observability DBaaS:** Otimização rigorosa de allowlists nos exporters de banco de dados, reduzindo o volume de séries ativas em > 90%.
* [x] **Monitoramento de DNS Interno:** Coleta pull para CoreDNS e etcd com dashboard completo organizado na metodologia de 5 pilares.
* [ ] **Stack 100% OpenTelemetry (OTLP + Semantic Conventions):**
  * [x] Backends: Mimir e Loki recebendo OTLP nativo com semântica preservada (`NoTranslation`/UTF-8 no Mimir, `otlp_config` no Loki); Tempo armazenando apenas traces (`metrics_generator` desabilitado); single-tenant monolítico.
  * [x] Gateway: OpenTelemetry Collector Contrib (`otel-gateway`), somente OTLP (4317/4318), sem conversões; portas 9998/9999 removidas.
  * [x] Agent Linux (`examples/push/linux`): OpenTelemetry Collector Contrib (`host_metrics`, `journald`) + OBI (traces e métricas HTTP), validado em VM Debian 13.
  * [x] Agent da própria stack: `otel-agent` (Collector em container, host + `docker_stats` + logs de containers + journald), validado em VM Debian 13 com Docker.
  * [x] `examples/push/linux-mysql`: host + receiver nativo `mysql` + error log, validado com MySQL Community 8.4.11 LTS na VM Debian 13.
  * [x] `examples/push/linux-pgsql`: host + receiver nativo `postgresql` (gate `useOTelSemconv`, `db.namespace`) + log com agrupamento de continuações, validado com PostgreSQL 18.6 na VM Debian 13.
  * [x] `examples/pull/linux` (node_exporter legado): coleta pelo `otel-agent` via `otel-agent/pull.d/`, sem conversão no Gateway, validado contra node_exporter 1.9.0 na VM Debian 13.
  * [x] `examples/pull/linux-dbaas-mysql`: node_exporter + mysqld_exporter do DBaaS pelo `otel-agent`, validado contra instância MySQL 8.4.6 (Magalu Cloud).
  * [x] `examples/pull/linux-dbaas-pgsql`: node_exporter + postgres_exporter do DBaaS pelo `otel-agent` (`datname` → `db.namespace`), validado contra instância PostgreSQL 16.11 (Magalu Cloud).
  * [x] `examples/pull/dns`: cluster DNS (node_exporter + CoreDNS + etcd) num único template pelo `otel-agent`, validado contra os 3 nós `dns-se1-*` (histogramas nativos).
  * [x] `examples/push/windows`: Collector (MSI oficial) com `host_metrics` (mesmos nomes do Linux) e 4 fontes do Event Log, validado em Windows Server 2022.
  * [x] `examples/push/windows-mssql`: receiver nativo `sqlserver` (contadores de desempenho, sem credencial) com identidade por instância e `db.namespace`, validado com duas instâncias em Windows Server 2022.
  * [x] `examples/pull/windows` e `windows-mssql` (windows_exporter) pelo `otel-agent`, com `mssql_instance`/`database` → `sqlserver.instance.name`/`db.namespace`; nenhum template Alloy restante.
  * [x] Auditoria pós-migração de toda a documentação e dos diagramas (docs alinhadas às configs, diagramas regenerados).
  * [ ] Service Graph a partir do OBI (feature `application_service_graph`), validar com o Service Map do Grafana.
  * [x] Coletas pull convertidas para o formato do agente (`otel-agent/pull-semconv.yaml`): push e pull gravam o mesmo formato OTel.
  * [x] Dashboards e datasources refeitos sobre os nomes OpenTelemetry, um por tipo de servidor (push e pull), mais o self-monitoring do pipeline.
* [ ] **Implantação de Tracing Distribuído:** Guia e exemplos práticos para instrumentação de microsserviços via SDK OTel conectados ao Tempo.
* [ ] **Continuous Profiling (Pyroscope):** Integração do Grafana Pyroscope na stack para análise de performance de CPU e memória a nível de linha de código.
* [ ] **Monitoramento Avançado de SQL Server:** Wait Stats e consultas mais custosas pelo receiver `sqlserver` (métricas por consulta ao banco, exigem credencial de leitura).

### 3.2 Médio Prazo (Q3 2026)
* [ ] **Alertas Inteligentes por Burn Rate:** Conjunto unificado de regras de alerta no Grafana Provisioning baseado em SLOs e queima de Error Budget.
* [ ] **Adaptive Sampling para Traces:** Implementação de amostragem dinâmica baseada em taxa de erros para otimizar custos no Tempo.
* [ ] **Auto-Sizing Tool:** Script automatizado que calcula a projeção de disco recomendada baseada no consumo real das últimas 24 horas.

### 3.3 Longo Prazo (Visão de Futuro)
* [ ] **Kubernetes Sidecar Mode:** Versão otimizada do agente OpenTelemetry empacotada para execução como DaemonSet em clusters Kubernetes.

---

## 4. Governança e Referências

* Para a metodologia conceitual de observabilidade, consulte [docs/OBSERVABILITY-METHODOLOGY.md](docs/OBSERVABILITY-METHODOLOGY.md).
* Para o histórico de versões e releases já entregues, consulte [CHANGELOG.md](CHANGELOG.md).
* Para diretrizes de contribuição, consulte [CONTRIBUTING.md](CONTRIBUTING.md).

---
🔙 Voltar: [README Principal](README.md)
