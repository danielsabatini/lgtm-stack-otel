# Métricas (Mimir e Alloy Prometheus)

Este documento cobre somente a política de métricas da stack.

## Endpoints de Ingestão

- **Porta 9999:** Endpoint para recebimento de métricas via Prometheus `remote_write`.
- **Portas 4317/4318:** Recebimento de métricas via OTLP.

## Política de Coleta (Lean Agent Metrics)

O _Node Exporter_ original trazido pelo módulo `prometheus.exporter.unix` injeta mais de 30 módulos inúteis do Kernel. Uma máquina pequena pode gerar **800 a 1400 séries ativas**. Num cluster, isso multiplica velozmente, explodindo a RAM do TSDB.

Por isso, na nossa arquitetura, utilizamos `set_collectors`. O agent entrega somente os sinais necessários:
- `cpu` (Percentual de Uso / Saturation)
- `meminfo` (Disponibilidade RAM)
- `diskstats` (IOPS Rate e Saturation)
- `filesystem` (Espaço em HD)
- `netdev` (Banda in/out em eth0 e interfaces)
- `loadavg` (Média de Carga)
- `uname` (informações do kernel)
- `os` (coletor habilitado no exporter; a seleção final de séries é definida no `prometheus.relabel`)

A cardinalidade extra do Node Exporter nativo (Bateria, BTRFS, Wifi, Infiniband, Selinux state) é limada antes de bater na RAM. O resultado é a premissa de um Mimir _Lean_ operando com **30 a 50% de custo reduzido**.

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

## Dimensionamento

Se precisar calcular o impacto futuro na instância lvm de `/lgtm/mimir`, a equação padrão de compressão é de `2 bytes/amostra`.

*Tendo scrape interno em 60s:*
`Custo (GB) = [séries ativas] × [dias de retenção] × 0.0000045 × 1.5`

Para manter a saúde e não escalar o disco prematuramente, monitore a cardinalidade ativa via a API dedicada do Mimir. Como o Mimir não expõe porta no host, a consulta deve ser feita pela rede Docker `lgtm`:

```bash
docker run --rm --network lgtm curlimages/curl:latest -s \
  "http://mimir:9009/api/v1/cardinality/active_series?selector={}" \
  -H "X-Scope-OrgID: anonymous"
```

Para capacidade de disco e layout físico, consulte [INFRASTRUCTURE.md](INFRASTRUCTURE.md).

---
🔙 Voltar: [README Principal](README.md)
