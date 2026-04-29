# Roadmap do Projeto

Este documento esboça a visão de futuro para a LGTM Stack e as funcionalidades planejadas para as próximas versões.

## Curto Prazo (Q2 2026)
- [ ] **Implantação de Tracing Distribuído:** Guia e exemplos para instrumentação de microsserviços (OTel) conectados ao Tempo.
- [ ] **Continuous Profiling (Pyroscope):** Integração do Grafana Pyroscope na stack para análise de performance de CPU/Memória a nível de linha de código.
- [x] **Integração PostgreSQL:** Criação de template Alloy (`pull-linux-dbaas-pgsql-hosts.alloy`) para configuração de scrape remoto DBaaS e filtros granulares de métricas.
- [ ] **Integração MySQL:** Criação de templates Alloy e dashboards provisionados para banco de dados Open Source.
- [ ] **Monitoramento Avançado de SQL Server:** Expansão das métricas de Wait Stats e Deadlocks no Windows Exporter.
- [ ] **Relatórios de Saúde:** Dashboard de auto-monitoramento da stack (saúde do Mimir/Loki/Tempo).

## Médio Prazo (Q3 2026)
- [ ] **Adaptive Sampling for Traces:** Implementação de amostragem dinâmica baseada em erros para otimizar o custo do Tempo.
- [ ] **Alerting Base:** Conjunto de regras de alerta padrão (Prometheus Rules) para incidentes críticos de infraestrutura.
- [ ] **Auto-Sizing Tool:** Script ou dashboard que calcula a projeção de disco baseada no consumo real das últimas 24h.

## Longo Prazo (Visão)
- [ ] **Multi-tenancy:** Suporte a múltiplos ambientes/clientes isolados no mesmo Mimir/Loki.
- [ ] **Kubernetes Sidecar Mode:** Versão do Alloy Agent otimizada para rodar como DaemonSet em clusters K8s.

---
**Nota:** Este roadmap é dinâmico e evolui conforme as necessidades da comunidade e do projeto.
