# Infraestrutura, Armazenamento e Instalação

> **Referência Técnica:** Este documento orienta o provisionamento físico, particionamento de disco (LVM), configuração de volumes e ciclo de vida da infraestrutura da LGTM Stack.

---

## 1. Introdução

A LGTM Stack é projetada para rodar em servidores dedicados ou máquinas virtuais (VMs), suportando bancos de dados de séries temporais de alta intensidade de escrita em disco (Mimir e Loki). Para garantir estabilidade e evitar que logs ou métricas concorram por espaço com o sistema operacional, a arquitetura recomenda a montagem de um disco ou volume de bloco dedicado montado em `/docker`.

---

## 2. Objetivo

1. **Garantir Performance de Armazenamento:** Isolar os dados da stack em um disco dedicado de alta velocidade (NVMe/SSD).
2. **Fornecer Procedimento Reproduzível:** Apresentar o roteiro de comandos necessários para preparar a máquina do zero até a subida da stack.
3. **Padronizar Operações de Ciclo de Vida:** Definir os comandos padrão para inicialização, parada, reinício e verificação de saúde da infraestrutura.

---

## 3. Pré-requisitos de Software

Antes de iniciar a instalação, certifique-se de que o host possui os seguintes pacotes instalados:

* **Docker Engine:** Versão 20.10.x ou superior ([Guia Oficial de Instalação](https://docs.docker.com/engine/install/)).
* **Docker Compose:** Versão V2 (comando `docker compose` nativo).
* **LVM2:** Gerenciador de volumes lógicos para criação de partições dinâmicas.

---

## 4. Estrutura de Armazenamento e Volumes Docker

Todos os dados persistentes da stack residem em **volumes Docker nomeados**, armazenados centralmente dentro do diretório `/docker/volumes/` gerenciado pelo daemon:

```text
/docker/                        ← Ponto de montagem do disco dedicado (Docker data-root)
  volumes/
    lgtm-stack-otel_grafana-data/    ← Banco SQLite, usuários e preferências do Grafana
    lgtm-stack-otel_loki-data/       ← Chunks compactados e WAL do Loki
    lgtm-stack-otel_mimir-data/      ← Blocos TSDB e compactor do Mimir
    lgtm-stack-otel_tempo-data/      ← Blocos de traces e WAL do Tempo
    lgtm-stack-otel_otel-agent-data/  ← Posição de leitura dos logs de container (otel-agent)
```

### Vantagens desse Modelo:
* **Portabilidade:** Ambientes de desenvolvimento e produção utilizam o mesmo arquivo `compose.yaml`, sem caminhos absolutos (*bind mounts*) engessados.
* **Segurança Operacional:** O comando `docker compose down` preserva todos os dados intactos; apenas `docker compose down -v` executa o reset completo.
* **Escalabilidade Simples:** Para aumentar a capacidade, basta expandir o volume de bloco no provedor de nuvem via LVM.

---

## 5. Roteiro de Instalação Passo a Passo (Ambiente Produtivo)

### 5.1 Instalar o Gerenciador LVM
```bash
# Em distribuições Debian / Ubuntu:
sudo apt update && sudo apt install lvm2 -y

# Em distribuições RedHat / Rocky / Fedora:
sudo dnf install lvm2 -y
```

### 5.2 Formatar e Montar o Disco Dedicado em `/docker`
```bash
# 1. Identificar o identificador do disco anexado (ex: /dev/vdb ou /dev/sdb):
lsblk

# 2. Criar o Physical Volume e Volume Group (substitua /dev/vdb pelo disco correto):
sudo pvcreate /dev/vdb
sudo vgcreate vgdocker /dev/vdb
sudo lvcreate -l 100%FREE -n lvdocker vgdocker
sudo mkfs.ext4 /dev/vgdocker/lvdocker

# 3. Criar o ponto de montagem e adicionar ao fstab para montagem automática:
sudo mkdir -p /docker
echo '/dev/mapper/vgdocker-lvdocker  /docker  ext4  defaults  0 2' | sudo tee -a /etc/fstab
sudo mount -a
sudo systemctl daemon-reload
```

### 5.3 Configurar o Docker para Utilizar o Disco `/docker`
```bash
# 1. Criar o arquivo de configuração do daemon apontando o data-root:
sudo mkdir -p /etc/docker
cat <<EOF | sudo tee /etc/docker/daemon.json
{
  "data-root": "/docker"
}
EOF

# 2. Iniciar e habilitar o serviço Docker:
sudo systemctl enable --now docker

# 3. Validar se o Docker está usando o novo diretório (deve retornar /docker):
sudo docker info | grep "Docker Root Dir"
```

### 5.4 Clonar o Repositório e Iniciar a Stack
```bash
# 1. Clonar o repositório da stack no servidor:
git clone <url-do-repositorio> lgtm-stack
cd lgtm-stack

# 2. Configurar o arquivo de variáveis de ambiente:
cp .env.example .env
# Edite as senhas e parâmetros de retenção conforme necessário no .env.
# DOCKER_DATA_ROOT deve ser igual ao "Docker Root Dir" do passo 5.3
# (padrão /docker; use /var/lib/docker se o data-root não foi alterado):
docker info --format '{{.DockerRootDir}}'
grep DOCKER_DATA_ROOT .env

# 3. Iniciar todos os containers em segundo plano:
docker compose up -d
```

---

## 6. Ciclo de Vida e Comandos Operacionais (Lifecycle)

| Operação | Comando | Descrição |
|---|---|---|
| **Iniciar a Stack** | `docker compose up -d` | Sobe todos os serviços em background. |
| **Parar a Stack** | `docker compose down` | Encerra os containers preservando todos os dados. |
| **Ver Status dos Serviços** | `docker compose ps` | Lista o status de execução de cada container. |
| **Acompanhar Logs em Tempo Real** | `docker compose logs -f` | Exibe logs contínuos de todos os containers. |
| **Reset Completo (Destrutivo)** | `docker compose down -v` | ⚠️ **Apaga todos os volumes e dados da stack.** |

---

## 7. Governança e Referências

* Para dimensionamento de memória e disco, consulte [SIZING.md](SIZING.md).
* Para a política de backup e recuperação de desastres, consulte [BACKUP.md](BACKUP.md).
* Para procedimentos seguros de atualização de versão, consulte [UPGRADE.md](UPGRADE.md).

---
🔙 Voltar: [README Principal](../README.md)
