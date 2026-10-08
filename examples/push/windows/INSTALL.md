# OpenTelemetry Collector — Instalação em Servidor Windows (Modo Agent)

Guia para instalar o agente OpenTelemetry em um servidor Windows e enviar
métricas e logs do Event Log ao `otel-gateway` da stack LGTM — **tudo em OTLP,
com a [OTel Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)**.

| Sinal | Origem | Nomes |
|---|---|---|
| Métricas de host | `host_metrics` | `system.*` — **os mesmos nomes e a mesma lista dos agentes Linux** (um painel serve aos dois) |
| Logs | `windows_event_log` (Security, System, Service Control Manager, TaskScheduler) | severidade OTel a partir do Level do evento |
| Self-monitoring | telemetria interna do Collector | `otelcol_*` com `service.name=otel-agent` |

Validado em Windows Server 2022 (Collector `0.162.0`, MSI oficial): ~29 séries
de host com 2 vCPUs, 1 disco e 1 interface.

---

## Pré-requisitos

- Windows Server 2016 ou superior, PowerShell como **Administrador**
- Servidor LGTM com o `otel-gateway` acessível na porta **4317** (OTLP gRPC)

---

## 1. Resolução de nome e teste do Gateway

```powershell
$LGTM_IP = "<IP_DO_SERVIDOR_LGTM>"
Add-Content -Path "$env:windir\System32\drivers\etc\hosts" -Value "$LGTM_IP  lgtm-stack"
Test-NetConnection lgtm-stack -Port 4317 -InformationLevel Quiet   # True
```

---

## 2. Instalar o OpenTelemetry Collector Contrib (MSI oficial)

Use a versão homologada (variável `OTELCOL_CONTRIB_VERSION` do `.env.example`).
O script **aborta antes de instalar** se o checksum não conferir:

```powershell
$ErrorActionPreference = "Stop"; $ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$v    = "<OTELCOL_CONTRIB_VERSION>"     # ex.: 0.162.0
$base = "https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v$v"
$msi  = "$env:TEMP\otelcol-contrib_$($v)_windows_x64.msi"

Invoke-WebRequest "$base/otelcol-contrib_$($v)_windows_x64.msi"        -OutFile $msi -UseBasicParsing
Invoke-WebRequest "$base/otelcol-contrib_$($v)_windows_x64.msi.sha256" -OutFile "$msi.sha256" -UseBasicParsing

$expected = ((Get-Content "$msi.sha256" -Raw).Trim() -split "\s+")[0].ToLower()
$actual   = (Get-FileHash $msi -Algorithm SHA256).Hash.ToLower()
if ($expected -ne $actual) { throw "Checksum NÃO confere ($actual) — não instale" }

Start-Process msiexec.exe -ArgumentList "/i `"$msi`" /qn /norestart" -Wait
Get-Service otelcol-contrib
```

> Leia o `.sha256` de um **arquivo** (`Get-Content`): no PowerShell 5.1 o
> `.Content` de `Invoke-WebRequest` vem como bytes e a comparação falharia.

O MSI cria o serviço **`otelcol-contrib`** (início automático) com o binário e a
config em `C:\Program Files\OpenTelemetry Collector\`.

---

## 3. Identidade do host e endereço do Gateway

A identidade de todos os sinais é definida **uma única vez**, nas variáveis de
ambiente **do serviço** (valor `Environment` da chave do serviço no registro —
mecanismo nativo do Windows para serviços):

```powershell
$envs = @(
  "OTEL_RESOURCE_ATTRIBUTES=deployment.environment.name=prd,cloud.provider=mgc,cloud.region=br-se1,cloud.availability_zone=a",
  "LGTM_GATEWAY_ENDPOINT=lgtm-stack:4317"
)
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\otelcol-contrib" `
  -Name Environment -PropertyType MultiString -Value $envs -Force | Out-Null
```

`host.name` (nome do computador) e `os.type` vêm automaticamente do detector `system`.

---

## 4. Configurar e iniciar

```powershell
$dir = "C:\Program Files\OpenTelemetry Collector"
Copy-Item "<repositorio>\examples\push\windows\config.yaml" "$dir\config.yaml" -Force

# Validar com as mesmas variáveis do serviço
$envs | ForEach-Object { $k,$val = $_ -split "=",2; [Environment]::SetEnvironmentVariable($k, $val, "Process") }
& "$dir\otelcol-contrib.exe" validate --config "$dir\config.yaml"; "validate: $LASTEXITCODE"   # 0

Restart-Service otelcol-contrib
Get-Service otelcol-contrib
```

Os logs do próprio Collector vão para o **Event Log Application** (origem
`otelcol-contrib`):

```powershell
Get-WinEvent -FilterHashtable @{LogName="Application"; ProviderName="otelcol-contrib"} -MaxEvents 20 |
  Where-Object { $_.LevelDisplayName -ne "Information" -or $_.Message -match "Everything is ready" } |
  Format-Table TimeCreated, LevelDisplayName, Message -Wrap
```

---

## 5. O que é coletado (Política Lean)

**Métricas:** mesma lista `system.*` dos agentes Linux. Excluídos no Windows:
unidades de CD/DVD (`CDFS`/`UDF`), partições sem letra (`HarddiskVolumeN` —
EFI de sistema e recuperação) e interfaces virtuais (`Loopback Pseudo-Interface`,
`isatap`, `Teredo`).

**Event Log** (filtro XPath na origem; posição de leitura guardada entre reinícios):

| Receiver | Canal / filtro | `service.name` | `category` |
|---|---|---|---|
| `windows_event_log/security` | Security — IDs 4624, 4625, 4634, 4647, 4648, 4672, 4720, 4725, 4726, 4740, 4767 | `windows-security` | `security` |
| `windows_event_log/system` | System — Critical/Error/Warning, **exceto** Service Control Manager | `windows-system` | `system` |
| `windows_event_log/services` | System — Service Control Manager, Critical/Error/Warning | `windows-services` | `platform` |
| `windows_event_log/task_scheduler` | TaskScheduler/Operational — Critical/Error/Warning | `windows-task-scheduler` | `application` |

Conversão para o OTel Logs Data Model: o Body é a mensagem do evento; viram
atributos `windows.eventlog.event_id`, `windows.eventlog.provider`,
`windows.eventlog.channel`, `process.pid` e, nos eventos de segurança,
`user.name`, `source.address` e `windows.logon.type`. Falha de logon (4625) e
conta bloqueada (4740) — registradas como Information pelo Windows — são
elevadas para `WARN`.

> O XPath do Event Log aceita um subconjunto da linguagem: use `!=` (não há
> `not()`). Teste uma consulta antes de usá-la:
> `Get-WinEvent -LogName System -FilterXPath "<xpath>" -MaxEvents 5`.

---

## 6. Verificar o envio de dados

A partir do servidor LGTM (rede interna `lgtm`):

```bash
H="<NOME_DO_COMPUTADOR>"
docker run --rm --network lgtm curlimages/curl -sG "http://mimir:9009/prometheus/api/v1/query" \
  --data-urlencode "query=count({__name__=~\"system[.].+\", \"host.name\"=\"$H\"})"
docker run --rm --network lgtm curlimages/curl -sG "http://loki:3100/loki/api/v1/query_range" \
  --data-urlencode "query={host_name=\"$H\", service_name=\"windows-security\"}" --data-urlencode 'limit=5'
```

No Grafana: **Explore** → **Loki** →
`{service_name="windows-security"} | windows_eventlog_event_id="4625"` (falhas de logon).

No Grafana: dashboard **Hosts → Windows Hosts** (o mesmo para servidores com
agente e coletados por pull).

---

## Atualizar configurações

```powershell
Copy-Item "<repositorio>\examples\push\windows\config.yaml" "C:\Program Files\OpenTelemetry Collector\config.yaml" -Force
Restart-Service otelcol-contrib
```

---

## Solução de problemas

| Sintoma | Verificação |
|---|---|
| Serviço não inicia | Event Log Application, origem `otelcol-contrib` (`failed to get config` = YAML inválido) |
| `subscription handle is not open` em um receiver do Event Log | XPath inválido — teste com `Get-WinEvent -FilterXPath` |
| Identidade ausente (`deployment.environment.name`, `cloud.*`) | `(Get-ItemProperty HKLM:\SYSTEM\CurrentControlSet\Services\otelcol-contrib).Environment` e reiniciar o serviço |
| Nada chega ao Gateway | `Test-NetConnection lgtm-stack -Port 4317` e firewall de saída |
