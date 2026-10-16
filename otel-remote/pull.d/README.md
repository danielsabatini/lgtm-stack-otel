# otel-remote/pull.d — coletas pull de servidores legados

Cada arquivo `*.yaml` deste diretório pode ser referenciado no `command:` do
serviço `otel-remote` no `compose.yaml` como configuração adicional do
OpenTelemetry Collector (mesclada ao `config.yaml` e `pull-semconv.yaml`).

Use para servidores onde não é possível instalar o agente (ex.: só há
`node_exporter`): o `otel-remote` faz o scrape, converte para OTLP com a
identidade OpenTelemetry do servidor remoto e para o mesmo formato do agente
(processors de `../pull-semconv.yaml`) e envia ao `otel-gateway`.

Os templates ficam em `examples/pull/<tipo>/` — copie para cá, ajuste os
alvos, adicione `--config=/etc/otelcol-contrib/pull.d/<arquivo>.yaml` no
`compose.yaml` e aplique: `docker compose up -d otel-remote`.

Os arquivos `*.yaml` daqui contêm IPs/nomes do ambiente e não são versionados
(ver `.gitignore`).
