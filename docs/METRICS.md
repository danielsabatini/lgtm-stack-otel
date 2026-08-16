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

## 📋 Padrão de Descrições de Painéis e Métricas nos Dashboards

Toda métrica e painel criado ou mantido nos dashboards Grafana deste repositório **deve obrigatoriamente** conter uma descrição estruturada no campo `Description` (o tooltip `(i)` do painel).

O objetivo é garantir que **qualquer operador, desenvolvedor ou suporte (mesmo com pouco conhecimento prévio do serviço)** compreenda instantaneamente o que a métrica significa, saiba avaliar se o valor está saudável e tenha comandos concretos para iniciar a resolução em caso de incidente.

### Estrutura Obrigatória em 3 Blocos:

1. **O que é (Definição Simples e Direta):**
   * Explicação objetiva do que o gráfico/card mede, **em linguagem acessível** e contextualizada.
   * Evite jargões herméticos de protocolo; prefira exemplos práticos do dia a dia (ex: *"Consultas de serviços internos da nuvem"* em vez de *"Zona ne1.cloud.internal"*).
2. **• O que observar (Sinais Vitais, Padrões e Thresholds):**
   * O comportamento normal e esperado da métrica.
   * Thresholds e limites numéricos claros (ex: *"< 16 ms (Verde), > 32 ms (Vermelho)"*, *"deve permanecer estritamente em 0"*).
   * O impacto real nas aplicações clientes caso o valor desvie do padrão.
3. **• Ação em caso de problema (Resolução e Mitigação):**
   * Comandos reais e objetivos para verificação e diagnóstico (`journalctl`, `systemctl`, `ping`, `dig`, `etcdctl`).
   * Passos de mitigação imediatos e caminhos de arquivos de configuração relevantes.

### Template Canônico:

```text
<O que a métrica mede de forma simples, clara e contextualizada>.
• O que observar: <Valores e comportamento esperado, limites de alerta/thresholds e impacto no cliente>.
• Ação em caso de problema: <Comandos de verificação imediata, testes de conectividade e passos de mitigação>.
```

### Exemplos Reais de Referência:

**1. Painel de Latência (Pilar Health):**
> *Tempo de resposta percebido por 99% das consultas de serviços internos da nuvem (bancos de dados, VMs e nomes *.cloud.internal).*
> *• O que observar: Deve responder em menos de 16 ms (Verde). Valores entre 16 ms e 32 ms indicam lentidão e acima de 32 ms (Vermelho) indicam lentidão crítica para os sistemas internos.*
> *• Ação em caso de problema: A lentidão geralmente está no banco etcd. Verifique a aba 'etcd > Diagnostics' abaixo para ver a velocidade de gravação em disco do etcd.*

**2. Painel de Capacidade de Memória (Pilar Capacity):**
> *Quantidade real de memória RAM física consumida exclusivamente pelo processo do CoreDNS em cada servidor.*
> *• O que observar: Deve ficar estável entre 50 MB e 150 MB. Se a linha subir continuamente sem nunca parar, indica vazamento de memória (memory leak).*
> *• Ação em caso de problema: Verifique se o cache não está configurado com tamanho excessivo ou se há plugins com falha e reinicie o serviço com 'sudo systemctl restart coredns'.*

**3. Painel de Diagnóstico de Descarte (Pilar Diagnostics):**
> *Quantidade de nomes que foram jogados fora da memória antes do tempo porque a gaveta de cache encheu (limite de 10.000 registros atingido).*
> *• O que observar: Deve ficar próximo de zero. Se a taxa estiver alta e constante, o CoreDNS está descartando dados úteis e tendo que buscar tudo de novo, gerando lentidão desnecessária.*
> *• Ação em caso de problema: Aumente o tamanho do cache no '/etc/coredns/Corefile' (mude 'cache 30' para 'cache 30 { success 50000 denial 25000 }') e recarregue com 'sudo systemctl reload coredns'.*

---
🔙 Voltar: [README Principal](../README.md)
