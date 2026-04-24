# Setup Físico e Dimensionamentos (Infrastructure)

Este documento cobre setup físico, disco, volumes e permissões.

## Pré-requisitos de Software

Para rodar esta stack, é necessário ter o Docker e o Docker Compose instalados no host:

- **Docker Engine:** Versão 20.10.x ou superior.
- **Docker Compose:** Versão V2 (comando `docker compose` nativo).
- **Guia de Instalação Oficial:** [Docker Engine Installation Guide](https://docs.docker.com/engine/install/)

---

## Limites Físicos Sugeridos (Hardware Limiters)

- **Padrão Gold:** Em produção (alta carga de APM), exija um host/VM com `8 Cores` e `32 GB RAM`.
- A distribuição de uso de núcleo segue os limites definidos no `compose.yaml` e pode ser sobrescrita via `.env`:
  - Loki e Mimir: ~2 vCPU / 6 GB a 8 GB RAM.
  - Tempo: ~2 vCPU / 6 GB RAM.
  - Alloy Gateway e Grafana: ~1 vCPU / 2 GB a 4 GB.
  - Alloy Agent: ~0.5 vCPU / 1 GB.
- A soma do worst-case retém até 4 GB livres para o OS (bash, sshd).

---

## Modelo de Disco

Todos os dados da stack vivem em **volumes Docker nomeados**, gerenciados pelo daemon sob o `data-root` configurado no `daemon.json`.

> [!IMPORTANT]
> **Recomendação de Performance:** Para sustentar a carga de IOPS exigida pelo Mimir (TSDB) e Loki (Chunks/WAL), utilize preferencialmente discos do tipo **NVMe**. O uso de discos lentos pode impactar diretamente a latência de ingestão e a velocidade das queries.

```
/docker/                        ← data-root do Docker
  volumes/
    lgtm-stack_grafana-data/    ← Grafana (SQLite, dashboards, etc.)
    lgtm-stack_loki-data/       ← Loki (chunks, WAL)
    lgtm-stack_mimir-data/      ← Mimir (TSDB, compactor, ruler)
    lgtm-stack_tempo-data/      ← Tempo (blocos, WAL)
    lgtm-stack_alloy-gateway-data/
    lgtm-stack_alloy-agent-data/
```

**Vantagens:**
- Dev e prod usam o mesmo `compose.yaml` — sem bind mounts, sem diretórios manuais.
- Reset completo: `docker compose down -v` remove tudo.
- Escalar: basta garantir espaço no disco montado em `/docker`.

---

## Roteiro de Implantação (Produção com Disco Dedicado)

### 1. Montar o disco dedicado em `/docker`

```bash
# Exemplo com LVM (disco vdb)
sudo pvcreate /dev/vdb
sudo vgcreate vg_docker /dev/vdb
sudo lvcreate -l 100%FREE -n lv_docker vg_docker
sudo mkfs.ext4 /dev/vg_docker/lv_docker

sudo mkdir -p /docker

# Adicionar ao fstab para montagem automática
echo '/dev/mapper/vg_docker-lv_docker  /docker  ext4  defaults  0 2' | sudo tee -a /etc/fstab
sudo mount -a
```

### 2. Prevenção de Auto-Start (Mask)

Para evitar que o Docker crie diretórios em `/var/lib/docker` durante a instalação, bloqueie o serviço:

```bash
sudo systemctl mask docker.service docker.socket
```

### 3. Instalação do Docker Engine

Instale os pacotes oficiais. O serviço tentará subir e falhará (devido ao mask), o que é o comportamento desejado neste momento:

```bash
# Exemplo para Debian/Ubuntu
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### 4. Configuração do `data-root` e Ativação

Aponte o daemon para o disco dedicado e libere os serviços:

```bash
sudo mkdir -p /etc/docker
cat <<EOF | sudo tee /etc/docker/daemon.json
{
  "data-root": "/docker"
}
EOF

# Liberar e iniciar o serviço corretamente
sudo systemctl unmask docker.service docker.socket
sudo systemctl enable --now docker
```

> Verifique com `docker info | grep "Docker Root Dir"` — deve retornar `/docker`.

### 5. Subir a stack

```bash
git clone <seu-repo> lgtm-stack
cd lgtm-stack
cp .env.example .env
# Edite o .env conforme o ambiente
docker compose up -d
```

---

## Lifecycle

| Operação | Comando |
|----------|---------|
| Subir a stack | `docker compose up -d` |
| Parar (mantém dados) | `docker compose down` |
| Reset completo — apaga todos os dados | `docker compose down -v` |
| Ver status | `docker compose ps` |
| Logs em tempo real | `docker compose logs -f` |

---

🔙 Voltar: [README Principal](README.md)
