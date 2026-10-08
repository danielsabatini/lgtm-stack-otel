# Guia de Contribuição (CONTRIBUTING)

Obrigado pelo interesse em contribuir com a LGTM Stack! Este projeto foca em **Lean Observability** — coletar apenas o necessário para garantir performance e economia de recursos.

## Princípios de Design

1.  **Whitelist First:** Nunca adicione métricas "por segurança". Adicione apenas o que é estritamente necessário para os Dashboards.
2.  **Desacoplamento:** O agente OpenTelemetry coleta (privilegiado, no host), o OTel Gateway ingere (sem privilégios, somente OTLP).
3.  **Portabilidade:** Use variáveis do Grafana sobre os atributos de identidade OpenTelemetry (`$host` → `host.name`, `$container` → `container.name`) em vez de nomes de hosts fixos.
4.  **Sincronização de Alertas:** Thresholds visuais nos painéis devem existir apenas para métricas com alertas e seus valores devem ser idênticos aos da regra de alerta.

## Fluxo de Trabalho

### 1. Adicionando novas métricas
Se você adicionar um novo painel ao Grafana que exige uma métrica ainda não coletada:
1.  Identifique a métrica no receiver do OpenTelemetry Collector (`host_metrics`, `docker_stats`, etc.).
2.  Habilite-a explicitamente (`metrics: <nome>: { enabled: true }`) em `otel-agent/config.yaml` e no template correspondente de `examples/push/`.
3.  Atualize o `docs/SIZING.md` se a cardinalidade aumentar significativamente.

### 1.1 Editando templates em `examples/`
Os templates de `examples/` são arquivos únicos e autocontidos por design — feitos para copiar direto num host remoto sem depender de outros arquivos do repositório. Isso significa que a allowlist de métricas e os labels de identidade global aparecem duplicados entre arquivos que deveriam espelhar um ao outro (ex.: as flags `system.*` de `examples/push/linux/config.yaml` ↔ `examples/push/windows/config.yaml` ↔ `otel-agent/config.yaml`, ou a lista `node_*` de `examples/pull/linux/linux-hosts.yaml` ↔ `examples/pull/dns/dns-hosts.yaml`). Ao criar ou editar qualquer `.yaml` em `examples/` ou em `otel-agent/`, rode:
```bash
python3 artifacts/scripts/check-examples-consistency.py
```
Ele valida as configs (via `otelcol-contrib validate`) e verifica se as edições foram replicadas nos arquivos-espelho, evitando o tipo de drift silencioso que esse script foi criado para pegar.

### 2. Documentação
A regra de ouro é: **Single Source of Truth** com **Linguagem Simples, Direta e Numerada**.
- Toda documentação em `docs/` deve ser **estruturada e numerada** (`1. Introdução`, `2. Objetivo`, etc.) e escrita em **linguagem simples, direta e de fácil entendimento**, evitando termos obscuros sem explicação prática.
- Se alterar a rede, atualize o `docs/ARCHITECTURE.md`.
- Se alterar métricas ou padrões de painéis, atualize o `docs/METRICS.md` e o `docs/SIZING.md`.
- Se alterar a taxonomia de dashboards ou metodologia de sinais, atualize o `docs/OBSERVABILITY-METHODOLOGY.md`.
- Sempre registre as mudanças no `CHANGELOG.md`.

## Padrões de Código

- **OpenTelemetry Collector:** configs em YAML do `otelcol-contrib` (versão em `OTELCOL_CONTRIB_VERSION`). Cada métrica e cada fonte de log é explícita (Política Lean); identidade via `OTEL_RESOURCE_ATTRIBUTES` + detector `system`; nomes da OTel Semantic Conventions.
- **Docker:** Utilize imagens oficiais e, preferencialmente, versões estáveis. Evite a tag `latest` em produção.

---
**Política de Governança:** Toda mudança executada deve ser seguida da atualização imediata das documentações pertinentes.
