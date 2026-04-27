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
