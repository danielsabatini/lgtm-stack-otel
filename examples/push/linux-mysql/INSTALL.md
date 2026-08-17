# Instalação — Agente Linux + MySQL (Modo Push)

> **Objetivo:** Instalar o Grafana Alloy diretamente no servidor Linux com MySQL para coletar métricas do banco (InnoDB, queries, conexões) e logs de erro/slow query, enviando via push para o Alloy Gateway central.

---

## 1. Pré-requisitos e Usuário MySQL

No servidor MySQL, crie um usuário de monitoramento com permissões de leitura:

```sql
CREATE USER 'alloy'@'localhost' IDENTIFIED BY 'SuaSenhaSegura';
GRANT PROCESS, REPLICATION CLIENT, SELECT ON *.* TO 'alloy'@'localhost';
FLUSH PRIVILEGES;
```

---

## 2. Instalação Passo a Passo

### 2.1 Instalar o Grafana Alloy

```bash
# Adicionar repositório oficial da Grafana
sudo mkdir -p /etc/apt/keyrings/
wget -q -O - https://apt.grafana.com/gpg.key | gpg --dearmor | sudo tee /etc/apt/keyrings/grafana.gpg > /dev/null
echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" | sudo tee /etc/apt/sources.list.d/grafana.list

# Instalar o Alloy
sudo apt update && sudo apt install alloy -y
```

### 2.2 Configurar Resolução de Nome

Adicione o IP do servidor central da LGTM Stack no `/etc/hosts`:

```bash
echo "<IP_DO_SERVIDOR_LGTM> lgtm-stack" | sudo tee -a /etc/hosts
```

### 2.3 Copiar e Ajustar a Configuração

```bash
# Copiar o arquivo de configuração
sudo cp config.alloy /etc/alloy/config.alloy
```

Edite o `/etc/alloy/config.alloy` e ajuste a string de conexão:
```alloy
prometheus.exporter.mysql "mysql_instance" {
  data_source_name = "alloy:SuaSenhaSegura@(localhost:3306)/"
}
```

### 2.4 Iniciar o Serviço

```bash
# Habilitar e iniciar o serviço Alloy
sudo systemctl enable --now alloy
```

---

## 3. Validação Rápida

```bash
# 1. Verificar status do serviço
sudo systemctl status alloy

# 2. Conferir envio nos logs
sudo journalctl -u alloy -f | grep -E "level=info|level=error"
```

No Grafana, acesse o dashboard **`Hosts + Database > Linux + MySQL Hosts`** para conferir as métricas e logs em tempo real.

---
🔙 Voltar: [README Principal](../../../README.md)
