# Coleta Remota — Servidores Windows Legados (windows_exporter)

Para servidores Windows onde **não é possível instalar o agente OpenTelemetry**
e há o `windows_exporter`. O `otel-agent` da stack faz o scrape (`:9182`),
converte as métricas para o **mesmo formato do agente** (`system.*`, OTel
Semantic Conventions) com a identidade OpenTelemetry do servidor e envia ao
`otel-gateway` — o Gateway continua recebendo só OTLP, sem conversão.

| Aspecto | Pull legado (este guia) | Agente OpenTelemetry ([push/windows](../../push/windows/INSTALL.md)) |
|---|---|---|
| Métricas de SO | `system.*` (convertidas de `windows_*` no `otel-agent`) | `system.*` (mesmos nomes do Linux) |
| Dashboard | **Windows Hosts** (o mesmo do agente) | **Windows Hosts** |
| Event Log | ❌ | ✅ |
| Identidade | declarada por alvo neste template | detectada no próprio host |

> **Prefira o agente** sempre que possível; use o pull como transição.

Validado com windows_exporter **0.31.8** em Windows Server 2022.

---

## 1. No servidor Windows (legado)

### 1.1 Instalar o windows_exporter (com verificação de checksum)

```powershell
$ErrorActionPreference = "Stop"; $ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$v    = "0.31.8"
$base = "https://github.com/prometheus-community/windows_exporter/releases/download/v$v"
$msi  = "$env:TEMP\windows_exporter-$v-amd64.msi"
Invoke-WebRequest "$base/windows_exporter-$v-amd64.msi" -OutFile $msi -UseBasicParsing
Invoke-WebRequest "$base/sha256sums.txt" -OutFile "$msi.sums" -UseBasicParsing
$expected = ((Get-Content "$msi.sums" | Where-Object { $_ -match "windows_exporter-$v-amd64\.msi" }) -split "\s+")[0].ToLower()
if ((Get-FileHash $msi -Algorithm SHA256).Hash.ToLower() -ne $expected) { throw "Checksum NÃO confere — não instale" }

Start-Process msiexec.exe -Wait -ArgumentList "/i `"$msi`" /qn /norestart ENABLED_COLLECTORS=cpu,logical_disk,memory,net,os,system,pagefile LISTEN_PORT=9182"
Get-Service windows_exporter
```

### 1.2 Restringir o acesso à porta 9182 (obrigatório)

O `windows_exporter` expõe `:9182` em HTTP **sem autenticação**. Libere a
porta **somente para o IP do servidor da stack**:

```powershell
$STACK_IP = "<IP_DO_SERVIDOR_LGTM>"
Get-NetFirewallRule | Where-Object DisplayName -match "windows_exporter" | Disable-NetFirewallRule
New-NetFirewallRule -DisplayName "windows_exporter (stack LGTM)" -Direction Inbound -Protocol TCP `
  -LocalPort 9182 -RemoteAddress $STACK_IP -Action Allow
```

---

## 2. No servidor da stack LGTM

```bash
cp examples/pull/windows/windows-hosts.yaml otel-agent/pull.d/
```

Edite `otel-agent/pull.d/windows-hosts.yaml` — um item por servidor:

```yaml
- targets: ["10.0.0.31:9182"]
  labels:
    host_name: "srv-win-01"               # vira host.name
    deployment_environment_name: prd      # vira deployment.environment.name
    cloud_provider: mgc                   # vira cloud.provider
    cloud_region: br-se1                  # vira cloud.region
    cloud_availability_zone: a            # vira cloud.availability_zone
```

```bash
curl -s -m 5 -o /dev/null -w "%{http_code}\n" http://10.0.0.31:9182/metrics   # 200
docker compose restart otel-agent
docker logs otel-agent 2>&1 | grep -E "carregando coleta pull|Everything is ready"
```

O arquivo em `otel-agent/pull.d/` contém IPs do ambiente e não é versionado.

---

## 3. O que é coletado (Política Lean)

Só a lista `keep` do template — os insumos da conversão para `system.*` (CPU,
memória, pagefile, discos lógicos com letra, rede, boot e `windows_os_info`) — e
o `up`. Descartados: partições sem letra (`HarddiskVolumeN`), interfaces
virtuais e séries sintéticas `scrape_*`.

A conversão (`*_windows_semconv` em `otel-agent/pull-semconv.yaml`) grava os
mesmos nomes, atributos e semântica do `host_metrics` do agente no Windows —
validada contra o agente no mesmo servidor: `privileged` → `system`, memória
`free` = disponível, `volume`/`nic` → `device`; o SO vai para o `target_info`
(`os.description`) e o resource recebe `os.type=windows`. Sem equivalente no
exporter: load average e tempo de disco ocupado (painéis sem dados para hosts
pull).

Referência validada: **26 séries por servidor**, contra ~1.650 expostas pelo
windows_exporter.

---

## 4. Validação

```bash
H="srv-win-01"
docker run --rm --network lgtm curlimages/curl -sG "http://mimir:9009/prometheus/api/v1/query" \
  --data-urlencode "query={\"up\", \"host.name\"=\"$H\"}"
docker run --rm --network lgtm curlimages/curl -sG "http://mimir:9009/prometheus/api/v1/query" \
  --data-urlencode "query=max by (state) ({\"system.memory.usage\", \"host.name\"=\"$H\"})"
```

No Grafana: dashboard **Hosts → Windows Hosts**, selecionando o servidor.

---

## Solução de problemas

| Sintoma | Causa provável |
|---|---|
| `up = 0` | Firewall do Windows (seção 1.2), serviço `windows_exporter` parado ou IP errado |
| Template não carregado | Arquivo precisa ter extensão `.yaml` em `otel-agent/pull.d/`; reinicie o `otel-agent` |

---
🔙 Voltar: [README Principal](../../../README.md)
