# Traces (Tempo e OTLP)

Traces distribuídos capturam a jornada integral de uma requisição pelo seu sistema e microsserviços. Eles são essenciais na identificação de gargalos de desempenho e quebra da arquitetura Lógica. O recebedor disso na nossa Stack é o banco Grafana Tempo, porém todo rastro passa antes pelo nosso filtro de inteligência (Alloy Gateway).

## O Endpoint (Recebedor Pùblico)

Você programará suas aplicações para enviar spans via OpenTelemetry apontando o exporter para o IP do seu servidor nas portas:

*   **HTTP (Protobuf/JSON):** Porta `4318`
*   **gRPC (Otimizado):** Porta `4317`

### Modelo de Código Recomendado:
*(Exemplo genérico para linguagens com SDKs Oficiais do OTel)*
```go
exporter, _ := otlptracegrpc.New(ctx,
    otlptracegrpc.WithEndpoint("SEU_HOST:4317"),
    otlptracegrpc.WithInsecure(), // Ou gere um certificado SSL via reverse proxy
)
```

## A Grande Economia: Tail Sampling (Amostragem Categórica)

Um fato matemático na captura de Traces em produção: Seu banco Tempo afogará em disco se receber milhões de repetições de _HTTP 200 OK_. A esmagadora maioria são chamadas perfeitas e imutáveis das funções, sem variação analítica pertinente, ocupando RAM e disco.

Nós ativamos o padrão arquitetural Enterprise batizado de `Tail Sampling` direto no processador OTLP do nosso Alloy Gateway (Porta invisível). Ele guarda os traces "na memória" e julga antes de encaminhá-los pro Tempo:

1. **Keep-Errors:** Retém **100%** dos traces onde qualquer span possui status OpenTelemetry `ERROR`. **Importante:** isso depende do SDK da aplicação mapear o erro para o status OTel `ERROR` — a maioria dos SDKs modernos faz isso automaticamente para exceções não tratadas e respostas HTTP 5xx, mas verifique o comportamento do seu SDK.
2. **Keep-Slow:** Mede a duração total do trace. Acima de **1000 ms**? Arquiva **100%** da jornada para diagnóstico de gargalo.
3. **Drop Sample-OK:** Para as chamadas rápidas e bem-sucedidas restantes, preserva apenas **5%** como amostra estatística — descartando os 95% duplicados sem valor analítico.

*Os thresholds podem ser ajustados em `alloy-gateway/conf.d/00-core.alloy` dentro do bloco `otelcol.processor.tail_sampling "lean"`.*

## Retenção em Disco

O expurgo natural do Tempo é manipulado no banco central de retenções `.env` na chave associada `TEMPO_RETENTION` e declarada unicamente em horas (Ex: `336h`).
Sempre consulte o painel para auditar o número de traces salvos, calculando um peso médio de ~`1,5 KB` de ocupação em disco virtual por span processado.

---
🔙 Voltar: [README Principal](README.md)
