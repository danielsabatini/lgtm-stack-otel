# Métricas (Mimir e Alloy Prometheus)

Este documento cobre somente a política de métricas da stack.

## Endpoints de Ingestão

A LGTM Stack possui endpoints específicos nativos (recebimento via Prometheus `remote_write`) e endpoints unificados (OTLP) expostos pelo Alloy Gateway. 

Para consultar as portas exatas e o roteamento de rede, consulte a matriz oficial em:
👉 **[ARCHITECTURE.md (Fronteiras de Rede)](ARCHITECTURE.md)**

## Política de Coleta (Lean Agent Metrics)

Diferente do padrão de mercado que coleta centenas de métricas irrelevantes, nossa arquitetura utiliza uma política de **Explicit Whitelisting (Allowlist)** via `metric_relabel` com a ação `keep`.

O _Node Exporter_ original pode gerar até **1400 séries ativas**. Em nossa stack, filtramos agressivamente na origem para persistir apenas o que é visualizado nos Dashboards.

### Estratégia de Filtragem:
- **Agente (Push):** O filtro ocorre no Alloy Agent antes de enviar o dado pela rede.
- **Gateway (Pull Legado):** O filtro ocorre no Alloy Gateway assim que o dado é coletado do exporter remoto.

O resultado é um Mimir _Lean_ operando com **80% a 90% de economia de disco** em comparação com coletas não filtradas.

## Labels

Todos os hosts são identificados exclusivamente pelo label **`instance`**. O label `nodename` **não é utilizado** para evitar duplicidade de cardinalidade — `instance` e `nodename` carregariam o mesmo valor, dobrando o custo de séries sem benefício analítico.

| Label | Valor | Origem |
|---|---|---|
| `job` | `node-exporter` | Injetado pelo `prometheus.relabel` no Alloy Agent |
| `instance` | `$HOSTNAME` (ex: `code`) | Injetado pelo `prometheus.relabel` via `sys.env("HOSTNAME")` |
| `service_name` | `node-exporter` | Injetado pelo `prometheus.relabel` |

O mesmo padrão se aplica ao cAdvisor. Para política de logs e labels do Loki, consulte [LOGS.md](LOGS.md).

## Retenção

A retenção é definida dinamicamente. Os blocos persistidos obedecem à variável `MIMIR_RETENTION` do arquivo `.env` da stack.

*   Valor Padrão Original: **`30d`**
*   Cortes de blocos velhos ocorrem autonomamente em partições TSDB limitadas.

> **Requisito técnico:** o Mimir inicializa o componente `ruler` mesmo sem regras configuradas. Por isso `mimir.yaml` precisa declarar `ruler_storage` e `ruler.rule_path` com caminhos graváveis.
> ```
> ruler: failed to access directory ./data-ruler/: open .check: permission denied
> ```
> O `mimir.yaml` desta stack já declara os paths absolutos obrigatórios:
> ```yaml
> ruler_storage:
>   backend: filesystem
>   filesystem:
>     dir: /data/ruler
>
> ruler:
>   rule_path: /data/ruler-temp
> ```

## Dimensionamento (Sizing)

Para cálculos de projeção de disco, cardinalidade real por host e cenários de exemplo, consulte o documento central de capacidade:

👉 **[SIZING.md](SIZING.md)**

---
🔙 Voltar: [README Principal](README.md)
