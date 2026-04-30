-- ============================================================================
-- SCRIPT DE TESTE DE CARGA - POSTGRESQL (VERSÃO 2 - OTIMIZADA)
--
-- Objetivo: Gerar carga realista e observável em PostgreSQL
-- para validar coleta de métricas nos 6+2 Pilares
--
-- Características:
--   • 20M inserts iniciais + 5 ciclos de 2M (acumulativos)
--   • 1000s de SELECT queries para ativar cache hits
--   • UPDATEs e DELETEs para medir I/O
--   • ~6-7GB disco final (seguro nos 20GB)
--   • Dados persistem para observação pós-teste
--
-- Tempo estimado: 8-12 minutos
-- Uso:
--   psql -h 172.18.1.157 -U postgres -f postgres-load-test.sql
--
-- ============================================================================

\set QUIET on
\set ON_ERROR_STOP on

SET work_mem = '256MB';
SET maintenance_work_mem = '512MB';
SET max_parallel_workers_per_gather = 4;
SET random_page_cost = 1.1;
SET synchronous_commit = 'off';

\set QUIET off

\echo ''
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo 'TESTE DE CARGA - POSTGRESQL (Versão 2 - Otimizado para 20GB)'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo ''

DROP DATABASE IF EXISTS lgtm;
CREATE DATABASE lgtm WITH ENCODING='UTF8' LC_COLLATE='C.UTF-8' LC_CTYPE='C.UTF-8' TEMPLATE=template0;

\c lgtm

\echo '[1/4] Criando tabela cadastro...'

DROP TABLE IF EXISTS cadastro;

CREATE UNLOGGED TABLE cadastro (
    id BIGSERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    endereco VARCHAR(150) NOT NULL,
    telefone VARCHAR(20) NOT NULL,
    email VARCHAR(100),
    documento VARCHAR(20),
    data_criacao TIMESTAMP DEFAULT NOW(),
    data_atualizacao TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'ativo' CHECK (status IN ('ativo', 'inativo', 'processado', 'pendente')),
    valor_total NUMERIC(12,2) DEFAULT 0
);

CREATE INDEX idx_cadastro_status ON cadastro(status);
CREATE INDEX idx_cadastro_email ON cadastro(email);
CREATE INDEX idx_cadastro_data ON cadastro(data_criacao DESC);
CREATE INDEX idx_cadastro_documento ON cadastro(documento);

\echo 'Tabela cadastro criada com sucesso!'

\echo '[2/4] Criando função de teste...'

CREATE OR REPLACE FUNCTION gerar_carga_teste()
RETURNS TABLE (mensagem TEXT) AS $$
DECLARE
    inicio_fase TIMESTAMP;
    duracao_ms NUMERIC;
    tempo_inicio_global TIMESTAMP;
    duracao_total_ms NUMERIC;
    registros_atuais INT;
    i INT;
BEGIN
    tempo_inicio_global := CLOCK_TIMESTAMP();

    RETURN QUERY SELECT format(
        E'┌─────────────────────────────────────────────────────────────────┐\n' ||
        E'│ FASE 0: INSERT INICIAL (20 milhões de registros)               │\n' ||
        E'└─────────────────────────────────────────────────────────────────┘'
    );

    inicio_fase := CLOCK_TIMESTAMP();

    WITH dados AS (
        SELECT
            'Usuario_' || s || '_Base' AS nome,
            'Endereco Numero ' || s || ' - Rua Principal' AS endereco,
            '(11) 9' || lpad((s % 99999999)::text, 8, '0') AS telefone,
            'user' || s || '@company.com' AS email,
            'DOC' || lpad(s::text, 12, '0') AS documento,
            CASE WHEN s % 4 = 0 THEN 'ativo' WHEN s % 4 = 1 THEN 'inativo'
                 WHEN s % 4 = 2 THEN 'processado' ELSE 'pendente' END AS status,
            ROUND((RANDOM() * 100000)::NUMERIC, 2) AS valor_total
        FROM generate_series(1, 20000000) AS s
    )
    INSERT INTO cadastro (nome, endereco, telefone, email, documento, status, valor_total)
    SELECT nome, endereco, telefone, email, documento, status, valor_total FROM dados;

    duracao_ms := EXTRACT(EPOCH FROM (CLOCK_TIMESTAMP() - inicio_fase)) * 1000;
    RETURN QUERY SELECT format('✓ Inseridos 20.000.000 registros em %.2fs', duracao_ms/1000);

    RETURN QUERY SELECT '';
    RETURN QUERY SELECT format(
        E'┌─────────────────────────────────────────────────────────────────┐\n' ||
        E'│ FASE 1: Carga Acumulativa (5 ciclos x 2M inserts)             │\n' ||
        E'└─────────────────────────────────────────────────────────────────┘'
    );

    FOR i IN 1..5 LOOP
        inicio_fase := CLOCK_TIMESTAMP();

        WITH dados AS (
            SELECT
                'Usuario_' || s || '_C' || i AS nome,
                'Endereco Ciclo ' || i || ' - Numero ' || s AS endereco,
                '(11) 9' || lpad((s % 99999999)::text, 8, '0') AS telefone,
                'user_c' || i || '_' || s || '@company.com' AS email,
                'DCL' || lpad((i*1000000+s)::text, 10, '0') AS documento,
                CASE WHEN s % 4 = 0 THEN 'ativo' WHEN s % 4 = 1 THEN 'inativo'
                     ELSE 'processado' END AS status,
                ROUND((RANDOM() * 50000)::NUMERIC, 2) AS valor_total
            FROM generate_series(1, 2000000) AS s
        )
        INSERT INTO cadastro (nome, endereco, telefone, email, documento, status, valor_total)
        SELECT nome, endereco, telefone, email, documento, status, valor_total FROM dados;

        UPDATE cadastro SET
            status = CASE WHEN status = 'ativo' THEN 'processado'
                         WHEN status = 'inativo' THEN 'ativo' ELSE 'inativo' END,
            valor_total = valor_total * 1.05,
            nome = SUBSTR(nome, 1, 60) || '_UPD'
        WHERE MOD(id::BIGINT, 2) = 0;

        DELETE FROM cadastro
        WHERE id > (20000000 + (i-1)*2000000) AND MOD(id::BIGINT, 10) = 0;

        duracao_ms := EXTRACT(EPOCH FROM (CLOCK_TIMESTAMP() - inicio_fase)) * 1000;
        SELECT COUNT(*) INTO registros_atuais FROM cadastro;

        RETURN QUERY SELECT format(
            '[CICLO %s/5] Insert 2M, Update 50%%, Delete 10%% → %s registros (%.2fs)',
            i, to_char(registros_atuais, '999G999G999'), duracao_ms/1000
        );
    END LOOP;

    RETURN QUERY SELECT '';
    RETURN QUERY SELECT format(
        E'┌─────────────────────────────────────────────────────────────────┐\n' ||
        E'│ FASE 2: Stress em Leitura (1000s de SELECTs - 15 segundos)    │\n' ||
        E'└─────────────────────────────────────────────────────────────────┘'
    );

    inicio_fase := CLOCK_TIMESTAMP();
    i := 0;

    WHILE EXTRACT(EPOCH FROM (CLOCK_TIMESTAMP() - inicio_fase)) < 15 LOOP
        PERFORM COUNT(*) FROM cadastro WHERE status = 'ativo';
        PERFORM COUNT(*) FROM cadastro WHERE status = 'inativo';
        PERFORM SUM(valor_total) FROM cadastro WHERE status = 'processado';
        PERFORM COUNT(*) FROM cadastro WHERE email LIKE '%company.com';
        PERFORM MAX(id), MIN(id) FROM cadastro;
        PERFORM COUNT(DISTINCT status) FROM cadastro;
        PERFORM COUNT(*) FROM cadastro WHERE valor_total > 50000;
        i := i + 1;
    END LOOP;

    RETURN QUERY SELECT format('✓ Executadas ~%s queries SELECT (cache hit rate ativo)', i*7);

    tempo_fim_global := CLOCK_TIMESTAMP();
    duracao_total_ms := EXTRACT(EPOCH FROM (tempo_fim_global - tempo_inicio_global)) * 1000;
    SELECT COUNT(*) INTO registros_atuais FROM cadastro;

    RETURN QUERY SELECT '';
    RETURN QUERY SELECT format(
        E'┌─────────────────────────────────────────────────────────────────┐\n' ||
        E'│ RESULTADO FINAL                                                 │\n' ||
        E'└─────────────────────────────────────────────────────────────────┘'
    );

    RETURN QUERY SELECT format(
        'Registros finais: %s | Tempo total: %.2fs | Throughput: %s ops/seg',
        to_char(registros_atuais, '999G999G999'),
        duracao_total_ms/1000,
        to_char((registros_atuais / (duracao_total_ms/1000))::BIGINT, '999G999G999')
    );

END;
$$ LANGUAGE plpgsql;

\echo 'Função gerar_carga_teste criada com sucesso!'

\echo '[3/4] Executando teste de carga...'
\echo ''

SELECT * FROM gerar_carga_teste();

\echo ''
\echo '[4/4] Analisando resultado final...'
\echo ''

SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS tamanho_total,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS tamanho_dados,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS tamanho_indices
FROM pg_tables
JOIN pg_stat_user_tables ON tablename = relname
WHERE schemaname = 'public' AND tablename = 'cadastro';

\echo ''
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo 'PRÓXIMOS PASSOS: Visualizar métricas no Grafana'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo ''
\echo '1. Acesse: http://localhost:3000/d/linux-pgsql-hosts'
\echo '2. Configure: instance = "srv-pgsql-01"'
\echo '3. Observe os painéis:'
\echo '   ✓ HEALTH: pg_up (deve ser 1)'
\echo '   ✓ ACTIVITY: pg_stat_database_xact_commit (pico durante teste)'
\echo '   ✓ CAPACITY: pg_database_size_bytes e pg_wal_size_bytes'
\echo '   ✓ DIAGNOSTICS: pg_stat_database_deadlocks (deve ser 0)'
\echo '   ✓ Cache Hit Rate: blks_hit / (blks_hit + blks_read) × 100 (95%+)'
\echo ''
\echo 'Os dados persistem na tabela para análise contínua!'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo ''
