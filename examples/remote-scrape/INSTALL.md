# Coleta Remota (Pull Scrape) — Guia de Instalação

Este guia descreve como configurar a coleta de métricas em servidores onde não é possível instalar o Alloy Agent nativamente. O **Alloy Gateway** realizará o scrape ativo (Pull) nos exporters remotos.

---

## Como funciona

```mermaid
graph LR
    subgraph "Servidor Remoto (Legacy)"
        E[Exporter]
    end
    subgraph "Servidor LGTM"
        G[Alloy Gateway] --> M[(Mimir)]
    end
    G -- "HTTP GET /metrics" --> E
```

O Gateway faz o scrape, filtra o "lixo" via relabeling e encaminha os dados higienizados para o Mimir.

---

## 1. Preparação no Gateway (Servidor LGTM)

1. Escolha o template adequado nesta pasta:
   * `pull-legacy-linux.alloy`
   * `pull-legacy-windows.alloy`
   * `pull-legacy-windows-mssql.alloy`


2. Copie para o diretório de configuração do Gateway:
   ```bash
   cp examples/remote-scrape/pull-legacy-<tipo>.alloy alloy-gateway/conf.d/
   ```

3. Edite o arquivo em `alloy-gateway/conf.d/` para incluir o IP e nome do seu servidor na lista `targets`.

4. O Gateway recarregará a configuração automaticamente.

---

## 2. Configuração dos Exporters (Servidor Remoto)

Para garantir que as métricas sejam compatíveis com os dashboards da stack, configure os coletores conforme abaixo.

### Windows (Apenas Host)
1. Instale o [windows_exporter](https://github.com/prometheus-community/windows_exporter).
2. Utilize o arquivo de configuração `config.yml`:
```yaml
collectors:
  enabled: cpu,logical_disk,memory,net,os,system,pagefile
```
3. Inicie o serviço:
```powershell
.\windows_exporter.exe --config.file=config.yml
```

### Windows + SQL Server (MSSQL)
1. Utilize o arquivo de configuração `config.yml`:
```yaml
collectors:
  enabled: cpu,logical_disk,memory,net,os,system,mssql,pagefile
```
2. Inicie o serviço:
```powershell
.\windows_exporter.exe --config.file=config.yml
```

### Linux (node_exporter)
1. Instale o [node_exporter](https://github.com/prometheus/node_exporter).
2. Execute com os coletores padrão:
```bash
./node_exporter
```

---

## 3. Verificação

Após configurar o exporter e o gateway, valide a coleta:

1. **Conectividade:** Do servidor LGTM, teste o acesso:
   ```bash
   curl -s http://<IP-REMOTO>:<PORTA>/metrics | head -n 5
   ```

2. **Ingestão:** Verifique se os dados chegaram ao Mimir:
   ```bash
   docker exec grafana curl -sG "http://mimir:9009/prometheus/api/v1/query" \
     --data-urlencode 'query=up{instance="<nome-do-host>"}' | jq '.data.result'
   ```

---

## 4. Dimensionamento (Sizing)

Para cálculos de projeção de disco e cardinalidade, consulte:
👉 **[SIZING.md](../../SIZING.md)**
