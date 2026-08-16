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
* [x] **Integração PostgreSQL:** Criação de template Alloy (`pull-linux-dbaas-pgsql-hosts.alloy`) para scrape remoto de DBaaS com filtros granulares.
* [x] **Integração MySQL:** Criação de templates Alloy e dashboards provisionados para MySQL / MariaDB.
* [x] **Lean Observability DBaaS:** Otimização rigorosa de allowlists nos exporters de banco de dados, reduzindo o volume de séries ativas em > 90%.
* [x] **Monitoramento de DNS Interno:** Coleta pull para CoreDNS e etcd com dashboard completo organizado na metodologia de 5 pilares.
* [ ] **Implantação de Tracing Distribuído:** Guia e exemplos práticos para instrumentação de microsserviços via SDK OTel conectados ao Tempo.
* [ ] **Continuous Profiling (Pyroscope):** Integração do Grafana Pyroscope na stack para análise de performance de CPU e memória a nível de linha de código.
* [ ] **Monitoramento Avançado de SQL Server:** Expansão das métricas de Wait Stats e Deadlocks no Windows Exporter.

### 3.2 Médio Prazo (Q3 2026)
* [ ] **Alertas Inteligentes por Burn Rate:** Conjunto unificado de regras de alerta no Grafana Provisioning baseado em SLOs e queima de Error Budget.
* [ ] **Adaptive Sampling para Traces:** Implementação de amostragem dinâmica baseada em taxa de erros para otimizar custos no Tempo.
* [ ] **Auto-Sizing Tool:** Script automatizado que calcula a projeção de disco recomendada baseada no consumo real das últimas 24 horas.

### 3.3 Longo Prazo (Visão de Futuro)
* [ ] **Multi-tenancy:** Suporte a múltiplos ambientes e clientes isolados com segurança no mesmo cluster de Mimir e Loki.
* [ ] **Kubernetes Sidecar Mode:** Versão otimizada do Alloy Agent empacotada para execução como DaemonSet em clusters Kubernetes.

---

## 4. Governança e Referências

* Para a metodologia conceitual de observabilidade, consulte [docs/OBSERVABILITY-METHODOLOGY.md](docs/OBSERVABILITY-METHODOLOGY.md).
* Para o histórico de versões e releases já entregues, consulte [CHANGELOG.md](CHANGELOG.md).
* Para diretrizes de contribuição, consulte [CONTRIBUTING.md](CONTRIBUTING.md).

---
🔙 Voltar: [README Principal](README.md)
