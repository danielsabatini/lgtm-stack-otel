# Traces (Tempo e OTLP)

Este documento cobre somente a política de traces da stack.

## Endpoints

Você programará suas aplicações para enviar spans via OpenTelemetry apontando o exporter para as portas OTLP gRPC ou HTTP do Alloy Gateway do seu servidor (consulte as portas exatas na [Topologia de Rede em ARCHITECTURE.md](ARCHITECTURE.md)).

### Modelo de Código Recomendado:
*(Exemplo genérico para linguagens com SDKs Oficiais do OTel)*
```go
exporter, _ := otlptracegrpc.New(ctx,
    otlptracegrpc.WithEndpoint("SEU_HOST:<PORTA_GRPC>"),
    otlptracegrpc.WithInsecure(), // Ou gere um certificado SSL via reverse proxy
)
```

## Coleta remota via Beyla eBPF (hosts Linux)

Além da instrumentação manual via SDK OTel (seção anterior), hosts Linux remotos
monitorados pela stack podem gerar traces automaticamente via **Beyla eBPF**
(`beyla.ebpf`, componente nativo do Alloy v1.x) — auto-instrumentação de serviços
HTTP/S e gRPC sem alterar código de aplicação. O template está em
[examples/linux/config.alloy](examples/linux/config.alloy), com guia completo de
pré-requisitos e instalação em
[examples/linux/INSTALL.md, seção "Traces (Beyla eBPF) — Opcional"](examples/linux/INSTALL.md#51-traces-beyla-ebpf--opcional).

**Escopo:**
- Somente hosts **Linux** — eBPF é uma tecnologia de kernel Linux, não roda em Windows.
- **Não aplicável** aos templates de DBaaS (`examples/linux-mysql`, `examples/linux-pgsql`):
  não há processo de aplicação colocalizado para instrumentar, apenas exporters PromQL
  de bancos gerenciados.
- **Não aplicável** ao modelo pull (`examples/remote-scrape`): o eBPF precisa rodar no
  mesmo kernel do processo-alvo, o que é incompatível com scrape remoto via HTTP.

**Sampling:** o produtor (Beyla) deve sempre enviar 100% dos spans
(`sampler { name = "always_on" }`) — o corte de volume já é feito pelo tail sampling
do Alloy Gateway (ver seção acima). Nenhuma configuração adicional é necessária no
lado do Gateway ao habilitar Beyla em um host.

**Correlação automática:** assim que os primeiros traces chegarem, o `metrics_generator`
do Tempo (já ativo, `service-graphs` + `span-metrics`) passa a gerar métricas RED
(`traces_spanmetrics_*`) e o Service Graph no Grafana automaticamente, sem configuração
adicional — ver [SIZING.md](SIZING.md) para o impacto de cardinalidade.

---

## Tail sampling

Um fato matemático na captura de Traces em produção: Seu banco Tempo afogará em disco se receber milhões de repetições de _HTTP 200 OK_. A esmagadora maioria são chamadas perfeitas e imutáveis das funções, sem variação analítica pertinente, ocupando RAM e disco.

Nós ativamos o padrão arquitetural Enterprise batizado de `Tail Sampling` direto no processador OTLP do nosso Alloy Gateway (Porta invisível). Ele guarda os traces "na memória" e julga antes de encaminhá-los pro Tempo:

1. **Keep-Errors:** Retém **100%** dos traces onde qualquer span possui status OpenTelemetry `ERROR`. **Importante:** isso depende do SDK da aplicação mapear o erro para o status OTel `ERROR` — a maioria dos SDKs modernos faz isso automaticamente para exceções não tratadas e respostas HTTP 5xx, mas verifique o comportamento do seu SDK.
2. **Keep-Slow:** Mede a duração total do trace. Acima de **1000 ms**? Arquiva **100%** da jornada para diagnóstico de gargalo.
3. **Drop Sample-OK:** Para as chamadas rápidas e bem-sucedidas restantes, preserva apenas **5%** como amostra estatística — descartando os 95% duplicados sem valor analítico.

Os thresholds ficam em `alloy-gateway/conf.d/00-core.alloy`.

## Retenção e Sizing

A retenção é controlada pela variável `TEMPO_RETENTION` no `.env`. Para cálculos de impacto em disco e estratégia de economia via *Tail Sampling*, consulte o documento central:

👉 **[SIZING.md](SIZING.md)**

> **Requisito técnico:** no `tempo.yaml`, `block_retention` e `compaction_window` devem ficar dentro de `compactor.compaction`.
> ```
> field block_retention not found in type compactor.Config
> ```
> Estrutura correta (já aplicada no `tempo.yaml` desta stack):
> ```yaml
> compactor:
>   compaction:
>     block_retention: ${TEMPO_RETENTION}
>     compaction_window: 1h
> ```

---
🔙 Voltar: [README Principal](README.md)
