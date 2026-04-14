# Grafana Alloy — Instalação em Servidor Linux (Modo Agent)

Guia para instalar o Grafana Alloy em um servidor Linux remoto e configurá-lo
para enviar métricas e logs para o `alloy-gateway` da stack LGTM.

---

## Pré-requisitos

- Sistema operacional: Debian / Ubuntu (ou derivado)
- Acesso root ou sudo
- Servidor LGTM com `alloy-gateway` acessível na rede
- `git` instalado (`sudo apt-get install -y git`)
- `systemd` em execução (obrigatório para coleta de journal logs)

---

## 1. Clonar o repositório

No servidor remoto, clone o repositório da stack para obter os arquivos
de configuração e este guia:

```bash
git clone <url-do-repositorio> lgtm-stack
cd lgtm-stack/examples/linux
```

> Para atualizar os arquivos no futuro, basta executar `git pull` dentro
> do diretório `lgtm-stack/`.

---

## 2. Configurar resolução de nome

O Alloy usará o hostname `lgtm-stack` para se conectar ao `alloy-gateway`.
Adicione uma entrada no `/etc/hosts` apontando para o IP do servidor que
executa a stack LGTM:

```bash
sudo nano /etc/hosts
```

Adicione a linha:

```
<IP_DO_SERVIDOR_LGTM>  lgtm-stack
```

Teste a resolução:

```bash
ping -c 1 lgtm-stack
```

---

## 3. Instalar o Grafana Alloy

### Adicionar o repositório Grafana

```bash
sudo apt-get install -y apt-transport-https software-properties-common wget

sudo mkdir -p /etc/apt/keyrings/
wget -q -O - https://apt.grafana.com/gpg.key \
  | gpg --dearmor \
  | sudo tee /etc/apt/keyrings/grafana.gpg > /dev/null

echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" \
  | sudo tee /etc/apt/sources.list.d/grafana.list
```

### Instalar a versão compatível com a stack

```bash
sudo apt-get update
sudo apt-get install -y alloy=1.15.0-1
```

> **Versão de referência:** `v1.15.0` — mesma utilizada pelo `alloy-agent` na stack.
> Para consultar as versões disponíveis: `apt-cache madison alloy`

---

## 4. Configurar variáveis de ambiente

As variáveis abaixo são usadas pelos pipelines para enriquecer os labels
de todas as métricas e logs enviados.

Edite o arquivo de ambiente do serviço:

```bash
sudo nano /etc/default/alloy
```

Adicione o conteúdo abaixo, ajustando os valores para este servidor:

```bash
# Identidade do servidor
HOSTNAME=nome-do-servidor         # ex: web-01, db-prod-01

# Ambiente (ex: prd, stg, dev, hml)
ENVIRONMENT=prd

# Provedor de nuvem (ex: aws, gcp, azure, mgc, on-premise)
CLOUD_PROVIDER=mgc

# Região (ex: us-east-1, br-se1, eastus)
CLOUD_REGION=br-se1

# Zona de disponibilidade (ex: a, b, c)
CLOUD_AVAILABILITY_ZONE=a
```

---

## 5. Configurar o Alloy para usar conf.d

Por padrão o Alloy lê um único arquivo. Configure-o para usar um diretório
`conf.d/`, igual ao padrão da stack.

Edite o arquivo de serviço (override):

```bash
sudo systemctl edit alloy
```

Adicione o conteúdo:

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/alloy run /etc/alloy/conf.d/
```

Salve e crie o diretório de configuração:

```bash
sudo mkdir -p /etc/alloy/conf.d
```

---

## 6. Copiar os arquivos de configuração

Os arquivos já estão disponíveis no repositório clonado no passo 1.
Copie-os para o diretório do Alloy:

```bash
sudo cp ~/lgtm-stack/examples/linux/*.alloy /etc/alloy/conf.d/
sudo chmod 644 /etc/alloy/conf.d/*.alloy
```

### Arquivos instalados

| Arquivo | O que coleta |
|---------|-------------|
| `000-metric-alloy-local.alloy` | Métricas de saúde do próprio Alloy |
| `001-metric-node-local.alloy` | Métricas do host (CPU, memória, disco, rede) |
| `200-log-sec-ssh.alloy` | Logs do SSH (autenticações, sessões) |
| `225-log-sys-kernel.alloy` | Logs do kernel (erros, warnings) |
| `252-log-app-cron.alloy` | Logs do cron (falhas de jobs) |
| `275-log-plt-systemd.alloy` | Logs do systemd (falhas de units) |

---

## 7. Permissão para leitura do journal

O usuário do serviço Alloy precisa de acesso aos logs do systemd:

```bash
sudo usermod -aG systemd-journal alloy
```

---

## 8. Iniciar e habilitar o serviço

```bash
sudo systemctl daemon-reload
sudo systemctl enable alloy
sudo systemctl start alloy
```

Verificar status:

```bash
sudo systemctl status alloy
```

---

## 9. Verificar o envio de dados

### Logs do Alloy em tempo real

```bash
sudo journalctl -u alloy -f
```

Procure por linhas indicando conexão bem-sucedida com `lgtm-stack`:

```
msg="Writing metrics" url=http://lgtm-stack:9999/api/v1/metrics/write
msg="Successfully flushed" url=http://lgtm-stack:9998/loki/api/v1/push
```

### Confirmar no Grafana

1. Acesse o Grafana da stack (`http://<IP_DO_SERVIDOR_LGTM>:3000`)
2. Abra o dashboard **Node Exporter (Remote)**
3. Selecione o `instance` correspondente ao novo servidor
4. Verifique se métricas e logs estão chegando

---

## Atualizar configurações

Quando houver atualizações nos arquivos de configuração do repositório:

```bash
cd ~/lgtm-stack
git pull
sudo cp examples/linux/*.alloy /etc/alloy/conf.d/
sudo systemctl restart alloy
```

---

## Solução de problemas

**Alloy não conecta em `lgtm-stack`**
```bash
curl -v http://lgtm-stack:9999/api/v1/metrics/write
# Verifique /etc/hosts e se a porta está acessível (firewall)
```

**Logs do journal não aparecem**
```bash
# Confirme que o usuário alloy está no grupo systemd-journal
groups alloy

# Reinicie o serviço após adicionar ao grupo
sudo systemctl restart alloy
```

**Verificar configuração sem reiniciar**
```bash
alloy fmt /etc/alloy/conf.d/
```
