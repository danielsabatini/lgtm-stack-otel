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
1.  Identifique a métrica no exporter (Node Exporter, cAdvisor, etc).
2.  Adicione o nome da métrica na regra `keep` do arquivo `.alloy` correspondente em `alloy-agent/conf.d/`.
3.  Atualize o `SIZING.md` se a cardinalidade aumentar significativamente.

### 1.1 Editando templates em `examples/`
Os templates de `examples/` são arquivos únicos e autocontidos por design — feitos para copiar direto num host remoto sem depender de outros arquivos do repositório. Isso significa que a allowlist de métricas e os labels de identidade global aparecem duplicados entre arquivos que deveriam espelhar um ao outro (ex.: `linux/config.alloy` ↔ `remote-scrape/pull-linux-hosts.alloy`). Ao criar ou editar qualquer `.alloy` em `examples/`, rode:
```bash
python3 scripts/check-examples-consistency.py
```
Ele valida a sintaxe (via `alloy validate`) e verifica se as edições foram replicadas nos arquivos-espelho, evitando o tipo de drift silencioso que esse script foi criado para pegar.

### 2. Documentação
A regra de ouro é: **Single Source of Truth**.
- Se alterar a rede, atualize o `ARCHITECTURE.md`.
- Se alterar métricas, atualize o `METRICS.md` e o `SIZING.md`.
- Sempre registre as mudanças no `CHANGELOG.md`.

## Padrões de Código

- **Alloy:** Use a sintaxe do Alloy v1.x. Organize arquivos por função (ex: `00x-metric-...`, `20x-log-...`).
- **Docker:** Utilize imagens oficiais e, preferencialmente, versões estáveis. Evite a tag `latest` em produção.

---
**Política de Governança:** Toda mudança executada deve ser seguida da atualização imediata das documentações pertinentes.
