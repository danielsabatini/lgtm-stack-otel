# Manual de Upgrades e Lifecycle (Update SRE)

A substituição de versões em Bancos de Dados Time-Series (TSDBs) como Loki e Mimir **não deve** ser tratada como a simples atualização de um site. Um *"bump"* cego de versão sem leitura prévia de Release Notes pode corromper índices históricos (ex: migração para TSDB Blocks `v13` no Loki).

Nosso repositório concentra o controle de Múltiplas Imagens de forma unificada no arquivo base `.env`. Siga estritamente as regras de ouro abaixo antes de aplicar um upgrade em Produção.

---

## 🛑 Rule #1: Nunca Pule "Major Releases"
Se o seu arquivo `.env` constar Loki `2.9.0` e a Grafana Labs estiver lançando a `4.0.0`, **não avance diretamente para a 4.0.0**.
Você *precisa* passar sequencialmente pela `3.0`, iniciar o container para que ele efetue eventuais rotinas internas de *Migration* e Data-Translation no LVM, e só então saltar de `3.y` para a próxima barreira arquitetural.

Diferente do Frontend (Grafana local) que pode saltar *majors* facilmente devido à resiliência do mapeamento e migração automática do banco relacional SQLite subjacente, o Mimir e o Loki gerenciam petabytes fragmentados em chunk-files crús no disco ext4, e quebram se as premissas faltarem.

---

## 🛑 Rule #2: Schema Validation (A Bíblia do Upgrade)
Antes de alterar os números no seu `.env`:
1. Abra as **[Release Notes Oficiais do Loki](https://grafana.com/docs/loki/latest/setup/upgrade/)** ou as **[Release Notes do Mimir](https://grafana.com/docs/mimir/latest/operators-guide/upgrading/)**.
2. Dê `Ctrl+F` buscando pelas chaves `schema_config` e `Breaking Changes`.
3. Se a documentação exigir um novo Storage Index, você precisará editar os arquivos (`loki.yaml` / `mimir.yaml`) **ANTERIORMENTE** à subida do Container declarando a validade temporal do novo schema. Sem o arquivo ajustado antemão, o TSDB Travará no Boot.

---

## 🚀 Procedimento Padrão Executivo (Step-by-Step)

Se garantiu que não feriu as Rule 1 e 2, aplique o *upgrade*:

**1. O Downtime Estratégico**
Banco de Dados não se chuta "live" a não ser em HA/Kubernetes. Drene o recebimento:
```bash
docker compose stop
sync # Garanta que a sua RAM escoa todo log/trace remanescente pros LVs!
```

**2. Mudança Paramétrica**
Altere de forma unificada o arquivo de ambiente:
```bash
nano .env

# Altere as TAGS na cabeça do documento.
GRAFANA_LOKI_VERSION=3.8.0 # Nova versão.
```

**3. Download Estrito**
Baixe as dependências declaradas antes de forçar a subida. Se faltar disco no _pulling_, o seu setup velho estará são e salvo.
```bash
docker compose pull
```

**4. Inicialização a Seco**
Se quiser ser profissional extremo, comande a imagem do container novo baixada a ler seu YAML antigo de configuração apenas para checar "Syntax errors de Depreciação" antes de botar em produção:
```bash
docker run --rm -v $(pwd)/loki/loki.yaml:/etc/loki/local-config.yaml grafana/loki:3.8.0 -config.file=/etc/loki/local-config.yaml -verify-config
```

**5. Wake-Up Final**
Se não houver grito no verify. Reviva a infra!
```bash
docker compose up -d
docker compose logs -f loki
# Espere a palavra mágica: "server initialized" . E cheque a tela do Grafana OTLP.
```

## 🛡️ O Mecanismo Anti-Falha (Fallback Nativo)

> Se alguém executar `docker compose up -d` sem possuir o arquivo `.env` (ex: um pull novo do Git onde .env não existe) ou deletar os headers acidentalmente, a nuvem não cairá! Nosso `compose.yaml` orquestra a técnica de *Safe-Fallback*:

`image: grafana/loki:${GRAFANA_LOKI_VERSION:-3.7.1}`

Neste exemplo real, se o Docker notar amnésia do operador, ele rejeitará a ordem de usar versão genérica `:latest` e invocará magicamente a trava nativa `3.7.1` salvando sua partição na Cloud.
