# Traces (Tempo e OTLP)

Este documento cobre somente a política de traces da stack.

## Endpoints

Você programará suas aplicações para enviar spans via OpenTelemetry apontando o exporter para o IP do seu servidor nas portas:

*   **gRPC (Otimizado):** Porta `4317` (Exposta pelo Alloy Gateway)
*   **HTTP (Protobuf/JSON):** Porta `4318` (Exposta pelo Alloy Gateway)

### Modelo de Código Recomendado:
*(Exemplo genérico para linguagens com SDKs Oficiais do OTel)*
```go
exporter, _ := otlptracegrpc.New(ctx,
    otlptracegrpc.WithEndpoint("SEU_HOST:4317"),
    otlptracegrpc.WithInsecure(), // Ou gere um certificado SSL via reverse proxy
)
```

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
