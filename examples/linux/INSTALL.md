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
Defina o IP do servidor LGTM e adicione a entrada no `/etc/hosts`:

```bash
LGTM_IP="<IP_DO_SERVIDOR_LGTM>"
echo "$LGTM_IP  lgtm-stack" | sudo tee -a /etc/hosts
```

> Se estiver acessando este servidor via SSH a partir da máquina LGTM,
> o IP pode ser obtido automaticamente:
> ```bash
> LGTM_IP=$(echo $SSH_CLIENT | awk '{print $1}')
> echo "$LGTM_IP  lgtm-stack" | sudo tee -a /etc/hosts
> ```

Teste a resolução:

```bash
ping -c 1 lgtm-stack
```

---

## 3. Instalar o Grafana Alloy

Procedimento baseado na [documentação oficial](https://grafana.com/docs/alloy/latest/set-up/install/linux/).

### Debian / Ubuntu

#### Adicionar o repositório Grafana

```bash
sudo apt-get install -y gpg

sudo mkdir -p /etc/apt/keyrings
sudo wget -O /etc/apt/keyrings/grafana.asc https://apt.grafana.com/gpg-full.key
sudo chmod 644 /etc/apt/keyrings/grafana.asc

echo "deb [signed-by=/etc/apt/keyrings/grafana.asc] https://apt.grafana.com stable main" \
  | sudo tee /etc/apt/sources.list.d/grafana.list
```

#### Instalar a versão compatível com a stack

```bash
sudo apt-get update
sudo apt-get install -y alloy=1.15.1-1
```

> Para consultar as versões disponíveis: `apt-cache madison alloy`

---

### Red Hat / CentOS / Fedora

#### Adicionar o repositório Grafana

```bash
wget -q -O gpg.key https://rpm.grafana.com/gpg.key
sudo rpm --import gpg.key

sudo tee /etc/yum.repos.d/grafana.repo << 'EOF'
[grafana]
name=grafana
baseurl=https://rpm.grafana.com
repo_gpgcheck=1
enabled=1
gpgcheck=1
gpgkey=https://rpm.grafana.com/gpg.key
sslverify=1
sslcacert=/etc/pki/tls/certs/ca-bundle.crt
EOF
```

#### Instalar a versão compatível com a stack

```bash
sudo dnf install -y alloy-1.15.1-1
```

> Para consultar as versões disponíveis: `dnf list --showduplicates alloy`

---

> **Versão de referência:** `v1.15.1` — mesma utilizada pelo `alloy-agent` na stack.

---

## 4. Verificar o arquivo de ambiente do serviço

O arquivo `/etc/default/alloy` criado pelo pacote define variáveis lidas pelo
serviço. O Alloy já aponta para `/etc/alloy/config.alloy` por padrão — confirme
que o arquivo não foi alterado e que `HOSTNAME` está disponível:

```bash
cat /etc/default/alloy
```

O `HOSTNAME` é lido automaticamente do ambiente do sistema pelo `config.alloy`
via `sys.env("HOSTNAME")`. Se o valor retornado for vazio ou incorreto, defina-o
explicitamente no `/etc/default/alloy`:

```bash
# Adicionar apenas se sys.env("HOSTNAME") não retornar o nome correto
echo "HOSTNAME=$(hostname)" | sudo tee -a /etc/default/alloy
```

---

## 5. Copiar o arquivo de configuração

O arquivo já está disponível no repositório clonado no passo 1.
Copie-o para o diretório do Alloy:

```bash
sudo cp ~/lgtm-stack/examples/linux/config.alloy /etc/alloy/config.alloy
```

### O que o `config.alloy` coleta

| Seção | O que coleta |
|-------|-------------|
| Alloy | Métricas de saúde do próprio agente |
| Linux host | Métricas do host (CPU, memória, disco, rede) |
| Segurança | Logs do SSH (autenticações, sessões) |
| Sistema | Logs do kernel (erros, warnings) |
| Aplicação | Logs do cron (falhas de jobs) |
| Plataforma | Logs do systemd (falhas de units) |

### Labels disponíveis para filtragem no Grafana

O `config.alloy` extrai automaticamente informações do sistema como labels, permitindo filtrar métricas no Grafana:

| Label | Fonte | Valor de exemplo | Uso |
|-------|-------|------------------|-----|
| `os` | `node_uname_info` | `"Linux"` | Filtrar por sistema operacional |
| `architecture` | `node_uname_info` | `"x86_64"`, `"aarch64"` | Filtrar por arquitetura (32-bit, 64-bit, ARM) |
| `kernel_release` | `node_uname_info` | `"6.12.74+deb13+1-amd64"` | Filtrar por versão específica do kernel |
| `instance` | config.alloy | `"srv-producao-01"` | Identificar o servidor (configurado no deploy) |
| `environment` | config.alloy | `"prd"`, `"stg"`, `"dev"` | Filtrar por ambiente |
| `cloud_provider` | config.alloy | `"aws"`, `"gcp"`, `"azure"`, `"mgc"` | Filtrar por provedor de nuvem |
| `cloud_region` | config.alloy | `"br-se1"`, `"us-east-1"` | Filtrar por região |
| `cloud_availability_zone` | config.alloy | `"a"`, `"b"`, `"c"` | Filtrar por zona de disponibilidade |

Os labels `os`, `architecture` e `kernel_release` são extraídos automaticamente da métrica
`node_uname_info` coletada pelo node_exporter. Os demais labels são configuráveis no
`config.alloy` durante o deployment.

---

## 6. Permissão para leitura do journal

O usuário do serviço Alloy precisa de acesso aos logs do systemd:

```bash
sudo usermod -aG systemd-journal alloy
```

---

## 7. Iniciar e habilitar o serviço

```bash
sudo systemctl enable alloy
sudo systemctl start alloy
```

Verificar status:

```bash
sudo systemctl status alloy
```

---

## 8. Verificar o envio de dados

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
2. Abra o dashboard **Node Exporter Linux (Remote)**
3. Selecione o `instance` correspondente ao novo servidor
4. Verifique se métricas e logs estão chegando

---

## Atualizar configurações

Quando houver atualizações nos arquivos de configuração do repositório:

```bash
cd ~/lgtm-stack
git pull
sudo cp examples/linux/config.alloy /etc/alloy/config.alloy
sudo systemctl restart alloy
```

---
 
## 9. Dimensionamento e Estudo de Capacidade (Sizing)
 
 Para cálculos de projeção de disco, cardinalidade real por host e cenários de exemplo, consulte o documento central de capacidade da stack:
 
 👉 **[SIZING.md](../../SIZING.md)**
 
 ---

## Solução de problemas

**Verificar conectividade com o gateway antes de iniciar o Alloy**
```bash
# Métricas (deve retornar HTTP 204 ou 400 — qualquer resposta confirma conectividade)
curl -s -o /dev/null -w "%{http_code}" -X POST http://lgtm-stack:9999/api/v1/metrics/write

# Logs (deve retornar HTTP 204 ou 400)
curl -s -o /dev/null -w "%{http_code}" -X POST http://lgtm-stack:9998/loki/api/v1/push
```

**Alloy não conecta em `lgtm-stack`**
```bash
# Verifique se a entrada existe em /etc/hosts
grep lgtm-stack /etc/hosts

# Teste a porta diretamente
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
alloy fmt /etc/alloy/config.alloy
```
