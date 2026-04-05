# Métricas (Mimir e Alloy Prometheus)

O Mimir é o nosso TSDB (Time-Series Database) hiper escalável, herdando o DNA do Prometheus. Aqui definimos as tratativas base para as métricas da máquina host e aplicações subjacentes.

## Política de Coleta (Lean Agent Metrics)

O _Node Exporter_ original trazido pelo módulo `prometheus.exporter.unix` injeta mais de 30 módulos inúteis do Kernel. Uma máquina pequena pode gerar **800 a 1400 séries ativas**. Num cluster, isso multiplica velozmente, explodindo a RAM do TSDB.

Por isso, na nossa arquitetura, utilizamos `set_collectors`. O Agent foi amordaçado para entregar estritamente "Sinais de Ouro":
- `cpu` (Percentual de Uso / Saturation)
- `meminfo` (Disponibilidade RAM)
- `diskstats` (IOPS Rate e Saturation)
- `filesystem` (Espaço em HD)
- `netdev` (Banda in/out em eth0 e interfaces)
- `loadavg` (Média de Carga)

A cardinalidade extra do Node Exporter nativo (Bateria, BTRFS, Wifi, Infiniband, Selinux state) é limada antes de bater na RAM. O resultado é a premissa de um Mimir _Lean_ operando com **30 a 50% de custo reduzido**.

## Política de Retenção

A retenção é definida dinamicamente. Os blocos persistidos obedecem à variável `MIMIR_RETENTION` do arquivo `.env` da stack.

*   Valor Padrão Original: **`30d`**
*   Cortes de blocos velhos ocorrem autonomamente em partições TSDB limitadas.

> **Requisito Técnico — `ruler_storage` e `ruler.rule_path`:** O Mimir, mesmo em modo single-binary sem regras configuradas, inicializa o componente `ruler` na startup. Sem os paths explícitos no `mimir.yaml`, o binário tenta usar o diretório de trabalho relativo (`./data-ruler/`) onde o UID 10001 não tem permissão de escrita, causando boot failure:
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

## Fórmula de Dimensionamento Estrito

Se precisar calcular o impacto futuro na instância lvm de `/lgtm/mimir`, a equação padrão de compressão é de `2 bytes/amostra`.

*Tendo scrape interno em 60s:*
`Custo (GB) = [séries ativas] × [dias de retenção] × 0.0000045 × 1.5`

Para manter a saúde e não escalar o disco prematuramente, monitore a cardinalidade ativa via a API dedicada do Mimir (evite `count({__name__=~".+"})` pois causa full-scan e degrada o TSDB):

```bash
# Retorna contagem e lista das séries ativas (requer acesso à porta interna 9009)
curl -s "http://localhost:9009/api/v1/cardinality/active_series?selector={}" \
  -H "X-Scope-OrgID: anonymous" | jq '.data.activeSeriesCount'
```

No Grafana, use a métrica interna `cortex_ingester_active_series` para um painel de tendência não-invasivo.

---
🔙 Voltar: [README Principal](README.md)
