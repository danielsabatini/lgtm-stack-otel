# Guia de Contribuição (CONTRIBUTING)

Obrigado pelo interesse em contribuir com a LGTM Stack! Este projeto foca em **Lean Observability** — coletar apenas o necessário para garantir performance e economia de recursos.

## Princípios de Design

1.  **Whitelist First:** Nunca adicione métricas "por segurança". Adicione apenas o que é estritamente necessário para os Dashboards.
2.  **Desacoplamento:** O Alloy Agent coleta (privilegiado), o Alloy Gateway ingere (seguro).
3.  **Portabilidade:** Use variáveis do Grafana (`$instance`, `$container`) em vez de nomes de hosts fixos.
4.  **Sincronização de Alertas:** Thresholds visuais nos painéis devem existir apenas para métricas com alertas e seus valores devem ser idênticos aos da regra de alerta.

## Fluxo de Trabalho

### 1. Adicionando novas métricas
Se você adicionar um novo painel ao Grafana que exige uma métrica ainda não coletada:
1.  Identifique a métrica no receiver do OpenTelemetry Collector (`host_metrics`, `docker_stats`, etc.).
2.  Habilite-a explicitamente (`metrics: <nome>: { enabled: true }`) em `otel-agent/config.yaml` e no template correspondente de `examples/push/` (ou na regra `keep` do `.alloy`, nos templates legados ainda não migrados).
3.  Atualize o `docs/SIZING.md` se a cardinalidade aumentar significativamente.

### 1.1 Editando templates em `examples/`
Os templates de `examples/` são arquivos únicos e autocontidos por design — feitos para copiar direto num host remoto sem depender de outros arquivos do repositório. Isso significa que a allowlist de métricas e os labels de identidade global aparecem duplicados entre arquivos que deveriam espelhar um ao outro (ex.: `linux/config.alloy` ↔ `remote-scrape/pull-linux-hosts.alloy`). Ao criar ou editar qualquer `.alloy` em `examples/`, rode:
```bash
python3 artifacts/scripts/check-examples-consistency.py
```
Ele valida a sintaxe (via `alloy validate`) e verifica se as edições foram replicadas nos arquivos-espelho, evitando o tipo de drift silencioso que esse script foi criado para pegar.

### 2. Documentação
A regra de ouro é: **Single Source of Truth** com **Linguagem Simples, Direta e Numerada**.
- Toda documentação em `docs/` deve ser **estruturada e numerada** (`1. Introdução`, `2. Objetivo`, etc.) e escrita em **linguagem simples, direta e de fácil entendimento**, evitando termos obscuros sem explicação prática.
- Se alterar a rede, atualize o `docs/ARCHITECTURE.md`.
- Se alterar métricas ou padrões de painéis, atualize o `docs/METRICS.md` e o `docs/SIZING.md`.
- Se alterar a taxonomia de dashboards ou metodologia de sinais, atualize o `docs/OBSERVABILITY-METHODOLOGY.md`.
- Sempre registre as mudanças no `CHANGELOG.md`.

## Padrões de Código

- **Alloy:** Use a sintaxe do Alloy v1.x. Organize arquivos por função (ex: `00x-metric-...`, `20x-log-...`).
- **Docker:** Utilize imagens oficiais e, preferencialmente, versões estáveis. Evite a tag `latest` em produção.

---
**Política de Governança:** Toda mudança executada deve ser seguida da atualização imediata das documentações pertinentes.
