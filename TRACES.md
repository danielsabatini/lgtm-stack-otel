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

1. **Keep-Errors:** Ele descobre se qualquer span ou requisição deu status Crash/500/Fail. Se sim, ele retém **100% da cadeia do erro** obrigatoriamente.
2. **Keep-Slow:** Ele mede o tempo de duração da rota. Bateu acima de **1000 milissegundos** (1 Lento/pesado)? Ele arquivará a jornada `100%` da requisição para você debugar o gargalo.
3. **Drop Sample-OK:** Para os infames 99% das chamadas rápidas e com pleno sucesso, ele arquivará uma proporção pífia (probabilidade randômica de **5% a 10%**). Assim, você terá uma "amostra estatística base" preservada, jogando mais de 90% dos bytes duplicados no limbo.

*O limite e probabilidade para "Corte" podem ser livremente configurados dentro da tag `otelcol.processor.tail_sampling` do arquivo `alloy-gateway/config.alloy`. Reajuste para seu escopo.*

## Retenção em Disco

O expurgo natural do Tempo é manipulado no banco central de retenções `.env` na chave associada `TEMPO_RETENTION` e declarada unicamente em horas (Ex: `336h`).
Sempre consulte o painel para auditar o número de traces salvos, calculando um peso médio de ~`1,5 KB` de ocupação em disco virtual por span processado.

---
🔙 Voltar: [README Principal](README.md)
