# Grafana Alloy — Instalação em Servidor Windows + SQL Server (Modo Agent)

Guia para instalar o Grafana Alloy em um servidor Windows que executa o Microsoft
SQL Server, configurando a coleta de métricas e logs do host Windows e do SQL Server
para o `alloy-gateway` da stack LGTM.

---

## Pré-requisitos

- Sistema operacional: Windows Server 2016 ou superior
- Microsoft SQL Server instalado e em execução
- Acesso de Administrador
- Servidor LGTM com `alloy-gateway` acessível na rede
- PowerShell 5.1 ou superior
- Audit Policy habilitada para coleta dos eventos de segurança

---

## 1. Configurar resolução de nome

O Alloy usará o hostname `lgtm-stack` para se conectar ao `alloy-gateway`.
Adicione a entrada no arquivo de hosts do Windows:

```powershell
# PowerShell como Administrador
$lgtmIp = "<IP_DO_SERVIDOR_LGTM>"
Add-Content -Path "C:\Windows\System32\drivers\etc\hosts" -Value "$lgtmIp  lgtm-stack"
```

Teste a resolução:

```powershell
ping lgtm-stack
```

---

## 2. Instalar o Grafana Alloy

Procedimento baseado na [documentação oficial](https://grafana.com/docs/alloy/latest/set-up/install/windows/).

```powershell
# PowerShell como Administrador

# Baixar o instalador MSI (ajuste a versão se necessário)
$version = "1.15.1"
$url = "https://github.com/grafana/alloy/releases/download/v$version/alloy-installer-windows-amd64.msi"
Invoke-WebRequest -Uri $url -OutFile "$env:TEMP\alloy-installer.msi"

# Instalar silenciosamente
msiexec /i "$env:TEMP\alloy-installer.msi" /quiet
```

O instalador:
- Cria o serviço Windows **Alloy**
- Instala os binários em `C:\Program Files\GrafanaLabs\Alloy\`
- Cria o diretório de dados em `C:\ProgramData\GrafanaLabs\Alloy\`

> **Versão de referência:** `v1.15.1` — mesma utilizada pelo `alloy-agent` na stack.

---

## 3. Criar o diretório de bookmarks

O Alloy usa o diretório de bookmarks para registrar a posição nos canais do
Event Log entre reinicializações:

```powershell
New-Item -ItemType Directory -Force -Path "C:\ProgramData\GrafanaLabs\Alloy\bookmarks"
```

---

## 4. Copiar e personalizar o arquivo de configuração

Clone o repositório ou copie o arquivo manualmente para o servidor remoto,
depois sobrescreva o arquivo de configuração padrão do Alloy:

```powershell
# Ajuste o caminho de origem se necessário
Copy-Item -Path "C:\lgtm-stack\examples\windows-mssql\config.alloy" `
          -Destination "C:\Program Files\GrafanaLabs\Alloy\config.alloy" `
          -Force
```

Abra o arquivo copiado e ajuste os valores de `environment`, `cloud_provider`,
`cloud_region` e `cloud_availability_zone` em todos os blocos de relabel.

O `instance` é lido automaticamente de `COMPUTERNAME` (variável nativa do Windows).
Para usar um nome diferente, substitua `sys.env("COMPUTERNAME")` por uma string fixa:

```powershell
# Ver o valor que será usado como instance
$env:COMPUTERNAME
```

### O que o `config.alloy` coleta

| Seção | O que coleta |
|-------|-------------|
| Alloy | Métricas de saúde do próprio agente |
| Windows host | Métricas do host (CPU, memória, disco, rede, arquivo de paginação) |
| SQL Server — métricas | `windows_mssql_*` via coletor WMI (accessmethods, bufman, databases, genstats, locks, memmgr, sqlstats, transactions, waitstats) |
| Segurança | Eventos de logon, autenticação e alterações de conta |
| Sistema | Eventos de hardware, drivers e erros do SO |
| Aplicação | Falhas do Agendador de Tarefas |
| Plataforma | Falhas de serviços Windows (SCM) |
| SQL Server — logs | Erros e alertas do engine MSSQL (Application Event Log, Provider `MSSQLSERVER`) |

> **Coletor `mssql`:** as métricas do SQL Server são coletadas via WMI pelo
> `windows_exporter` embutido no Alloy — não requer credenciais de banco de dados
> nem conexão ODBC. O SQL Server precisa estar em execução localmente no mesmo servidor.
>
> **Coletor `pagefile`:** expõe métricas de uso do arquivo de paginação
> (`windows_pagefile_current_bytes`, `windows_pagefile_free_bytes`,
> `windows_pagefile_limit_bytes`).
>
> **Filtro de volumes:** o relabel mantém apenas volumes com letra de unidade
> (`C:`, `D:`, etc.), descartando entradas do tipo `HarddiskVolume*` geradas
> internamente pelo Windows.

### Labels disponíveis para filtragem no Grafana

| Label | Fonte | Valor de exemplo | Uso |
|-------|-------|------------------|-----|
| `os` | `windows_os_info` | `"windows"` | Filtrar por sistema operacional |
| `os_product` | `windows_os_info` | `"Windows Server 2022 Datacenter"` | Filtrar por versão/edição do Windows |
| `os_version` | `windows_os_info` | `"10.0.20348"` | Filtrar por versão do SO |
| `mssql_instance` | `windows_mssql_*` | `"MSSQLSERVER"`, `"SQLEXPRESS"` | Filtrar por instância SQL Server |
| `instance` | config.alloy | `"win-srv-01"` | Identificar o servidor |
| `environment` | config.alloy | `"prd"`, `"stg"`, `"dev"` | Filtrar por ambiente |
| `cloud_provider` | config.alloy | `"aws"`, `"gcp"`, `"azure"`, `"mgc"` | Filtrar por provedor de nuvem |
| `cloud_region` | config.alloy | `"br-se1"`, `"us-east-1"` | Filtrar por região |
| `cloud_availability_zone` | config.alloy | `"a"`, `"b"`, `"c"` | Filtrar por zona de disponibilidade |

Os labels `os`, `os_product`, `os_version` e `mssql_instance` são extraídos
automaticamente das métricas do windows_exporter e não requerem configuração adicional.

---

## 5. Habilitar Audit Policy para eventos de segurança

O canal `Security` só registra eventos se a Audit Policy estiver ativa.
Verifique e habilite as categorias necessárias:

```powershell
# Verificar políticas atuais
auditpol /get /category:*

# Habilitar Audit Logon (cobre 4624, 4625, 4634, 4647)
auditpol /set /subcategory:"Logon" /success:enable /failure:enable

# Habilitar Audit Account Management (cobre 4720, 4725, 4726, 4740, 4767)
auditpol /set /subcategory:"User Account Management" /success:enable /failure:enable

# Habilitar Audit Special Logon (cobre 4672)
auditpol /set /subcategory:"Special Logon" /success:enable /failure:enable
```

---

## 6. Habilitar o canal do Agendador de Tarefas

O canal `Microsoft-Windows-TaskScheduler/Operational` vem desabilitado por padrão:

```powershell
wevtutil sl "Microsoft-Windows-TaskScheduler/Operational" /e:true
```

---

## 7. Permissão para leitura do Event Log Security

O serviço Alloy roda como **LocalSystem** por padrão, que já tem acesso ao canal
Security. Se for alterado para uma conta de serviço específica, adicione-a ao grupo:

```powershell
Add-LocalGroupMember -Group "Event Log Readers" -Member "NT SERVICE\Alloy"
```

---

## 8. Iniciar e habilitar o serviço

```powershell
# Reiniciar para aplicar as variáveis de ambiente e a nova configuração
Restart-Service -Name Alloy

# Confirmar que está rodando
Get-Service -Name Alloy
```

Verificar status detalhado:

```powershell
sc.exe query Alloy
```

---

## 9. Verificar o envio de dados

### Logs do Alloy em tempo real

**Método recomendado** — via Event Viewer:

```powershell
# Ver os últimos 10 eventos do Alloy (mais confiável)
Get-EventLog -LogName Application -Source Alloy -Newest 10 | Format-List TimeCreated, EntryType, Message
```

Procure por mensagens como:
- `"now listening for http traffic"` ✅ — serviço escutando
- `"finished complete graph evaluation"` ✅ — todos componentes carregados
- Nenhuma mensagem com `"error"` ou `"failed"` ✅

Se houver erros, verifique a sintaxe do config.alloy (seção "Solução de problemas").

**Alternativa** — arquivo de log direto (se configurado):

```powershell
Get-Content "C:\ProgramData\GrafanaLabs\Alloy\alloy.log" -Wait -Tail 50
```

### Interface web do Alloy

Acesse `http://127.0.0.1:12345` no navegador do servidor para ver o status dos
componentes carregados.

### Confirmar no Grafana

1. Acesse o Grafana da stack (`http://<IP_DO_SERVIDOR_LGTM>:3000`)
2. Abra o dashboard **Windows + MSSQL Exporter (remote)**
3. Selecione o `instance` e o `mssql_instance` correspondentes ao novo servidor
4. Verifique se métricas e logs estão chegando

---

## 10. Testar a coleta de logs por categoria

Execute os comandos abaixo para gerar eventos em cada categoria e validar o
pipeline completo até o Grafana. Aguarde ~30 segundos após cada bloco e verifique
o painel correspondente no dashboard **Windows + MSSQL Exporter (remote)**.

### Security — falha de login (EventID 4625)

```powershell
net use \\127.0.0.1\IPC$ /user:AlloyTestUser WrongPassword123! 2>$null
net use \\127.0.0.1\IPC$ /delete 2>$null
```

Verifique se o Audit Policy está ativo antes de testar:

```powershell
auditpol /get /subcategory:"Logon"
# Deve mostrar: Failure: Enable
```

### System — erro e aviso no System log

```powershell
# Registra uma fonte temporária de teste (só precisa fazer uma vez)
New-EventLog -LogName System -Source "AlloyTest" -ErrorAction SilentlyContinue

# Error (Level 2)
Write-EventLog -LogName System -Source "AlloyTest" -EventId 1001 -EntryType Error -Message "Alloy test - System Error Level 2"

# Warning (Level 3)
Write-EventLog -LogName System -Source "AlloyTest" -EventId 1001 -EntryType Warning -Message "Alloy test - System Warning Level 3"
```

### Application — falha no Agendador de Tarefas (Level 2)

```powershell
$action  = New-ScheduledTaskAction -Execute "C:\NonExistent\fake.exe"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(5)
Register-ScheduledTask -TaskName "AlloyTest" -Action $action -Trigger $trigger -Force | Out-Null
Start-ScheduledTask -TaskName "AlloyTest"
Start-Sleep -Seconds 10
Unregister-ScheduledTask -TaskName "AlloyTest" -Confirm:$false
```

O Task Scheduler registrará uma falha (Level=2) no canal `Microsoft-Windows-TaskScheduler/Operational`
porque o executável não existe.

### Platform — falha de serviço no SCM (Level 2)

```powershell
# Criar serviço com binário inexistente
sc.exe create AlloyTestSvc binPath= "C:\NonExistent\fake_service.exe" start= demand

# Tentar iniciar — SCM registra EventID 7000, Level=2 (Error)
sc.exe start AlloyTestSvc

# Remover após o teste
sc.exe delete AlloyTestSvc
```

O Service Control Manager registrará EventID 7000 (Level=2, Error) no canal System
quando o binário do serviço não for encontrado.

### SQL Server — erro no Application Event Log

Gera um evento de erro no Application Event Log com o provider `MSSQLSERVER`:

```powershell
sqlcmd -S localhost -Q "RAISERROR('Teste monitoramento LGTM stack', 17, 1) WITH LOG;"
```

Se o SQL Server usar autenticação SQL:

```powershell
sqlcmd -S localhost -U sa -P "<senha>" -Q "RAISERROR('Teste monitoramento LGTM stack', 17, 1) WITH LOG;"
```

> `WITH LOG` é obrigatório para o evento aparecer no Windows Event Log.
> Severity ≥ 17 faz o SQL Server escrever com Level=2 (Error) no Application Log.

Confirme o evento gerado:

```powershell
Get-WinEvent -FilterHashtable @{
  LogName      = 'Application'
  ProviderName = 'MSSQLSERVER'
  Level        = 2
} -MaxEvents 3 | Format-List TimeCreated, LevelDisplayName, Message
```

Verifique no Loki com a query:

```logql
{service_name="mssql", category="database"} | = "Teste monitoramento"
```

---

## Atualizar configurações

Quando houver atualizações no arquivo de configuração do repositório:

```powershell
Copy-Item -Path "C:\lgtm-stack\examples\windows-mssql\config.alloy" `
          -Destination "C:\Program Files\GrafanaLabs\Alloy\config.alloy" `
          -Force

Restart-Service -Name Alloy
```

---

## 12. Dimensionamento e Estudo de Capacidade (Sizing)

Para cálculos de projeção de disco, cardinalidade real por host e cenários de exemplo, consulte o documento central de capacidade da stack:

👉 **[SIZING.md](../../SIZING.md)**

---

## Solução de problemas

**Serviço não está iniciando (status: STOPPED)**

```powershell
# Ver detalhes do erro de inicialização
Get-EventLog -LogName Application -Source Alloy -Newest 10 | Format-List TimeCreated, EntryType, Message

# Se houver erro de sintaxe XPath, verifique:
# - Linhas com "xpath_query" no config.alloy
# - Certifique-se de que não há quebras de linha na XPath query
# - Windows Event Log XPath tem sintaxe limitada
```

**Verificar conectividade com o gateway antes de iniciar o Alloy**

```powershell
# Métricas (deve retornar HTTP 204 ou 400 — qualquer resposta confirma conectividade)
$r = Invoke-WebRequest -Uri "http://lgtm-stack:9999/api/v1/metrics/write" `
     -Method POST -UseBasicParsing -ErrorAction SilentlyContinue
$r.StatusCode

# Logs
$r = Invoke-WebRequest -Uri "http://lgtm-stack:9998/loki/api/v1/push" `
     -Method POST -UseBasicParsing -ErrorAction SilentlyContinue
$r.StatusCode
```

**Alloy não conecta em `lgtm-stack`**

```powershell
# Verificar se a entrada existe em hosts
Select-String -Path "C:\Windows\System32\drivers\etc\hosts" -Pattern "lgtm-stack"

# Testar a porta diretamente
Test-NetConnection -ComputerName lgtm-stack -Port 9999
```

**`instance` aparece vazio ou incorreto nos dashboards**

```powershell
# Verificar o valor de COMPUTERNAME que o Alloy lerá
$env:COMPUTERNAME

# Se quiser um nome diferente, edite o config.alloy e substitua:
# replacement = sys.env("COMPUTERNAME")
# por:
# replacement = "nome-desejado"
Restart-Service -Name Alloy
```

**Métricas `windows_mssql_*` não aparecem**

```powershell
# Confirmar que o SQL Server está rodando
Get-Service -Name MSSQLSERVER

# Verificar se o coletor mssql está expondo métricas localmente
Invoke-WebRequest -Uri http://localhost:12345/metrics -UseBasicParsing |
  Select-Object -ExpandProperty Content | Select-String "windows_mssql" | Select-Object -First 5
```

> O coletor `mssql` do windows_exporter coleta via WMI e não requer configuração
> adicional se o SQL Server estiver em execução na mesma máquina.

**Logs do SQL Server não aparecem (category=database)**

```powershell
# Verificar se existem eventos do MSSQLSERVER no Application Log
Get-WinEvent -FilterHashtable @{
  LogName      = 'Application'
  ProviderName = 'MSSQLSERVER'
} -MaxEvents 5 | Format-List TimeCreated, LevelDisplayName, Message

# Gerar evento de teste (severity 17+ escreve no Event Log com Level=Error)
sqlcmd -S localhost -Q "RAISERROR('Teste', 17, 1) WITH LOG;"
```

**Eventos de segurança não aparecem**

```powershell
# Verificar se o canal Security tem eventos
Get-WinEvent -LogName Security -MaxEvents 5 | Select-Object Id, Message

# Confirmar Audit Policy
auditpol /get /subcategory:"Logon"
```

**Canal do Agendador de Tarefas não encontrado**

```powershell
# Confirmar que o canal está habilitado
wevtutil gl "Microsoft-Windows-TaskScheduler/Operational"
# Procure: enabled: true

# Habilitar se necessário
wevtutil sl "Microsoft-Windows-TaskScheduler/Operational" /e:true
```

**Verificar configuração sem reiniciar**

```powershell
# Checar sintaxe do arquivo de configuração
& "C:\Program Files\GrafanaLabs\Alloy\alloy.exe" fmt `
    "C:\Program Files\GrafanaLabs\Alloy\config.alloy"
```
