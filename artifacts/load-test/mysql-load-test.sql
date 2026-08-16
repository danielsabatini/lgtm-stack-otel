-- ============================================================================
-- SCRIPT DE TESTE DE CARGA - MYSQL (VERSÃO 2 - OTIMIZADA)
--
-- Objetivo: Gerar carga realista e observável em MySQL
-- para validar coleta de métricas nos 6+2 Pilares
--
-- Características:
--   • 20M inserts iniciais + 5 ciclos de 2M (acumulativos)
--   • 1000s de SELECT queries para ativar cache hits
--   • UPDATEs e DELETEs para medir I/O
--   • ~7-8GB disco final (seguro nos 20GB)
--   • Dados persistem para observação pós-teste
--
-- Tempo estimado: 8-12 minutos
-- Uso:
--   mysql -h 192.168.1.13 -u root -p < mysql-load-test.sql
--
-- ============================================================================

SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';
SET SESSION max_allowed_packet = 67108864;           -- 64MB para bulk inserts
SET SESSION innodb_autoinc_lock_mode = 2;            -- Lightweight locks
SET SESSION innodb_flush_log_at_trx_commit = 2;      -- Balance perf/durabilidade

-- ============================================================================
-- 1. PREPARAÇÃO DO BANCO
-- ============================================================================

DROP DATABASE IF EXISTS lgtm;
CREATE DATABASE lgtm CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE lgtm;

SELECT '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' AS info;
SELECT 'TESTE DE CARGA - MYSQL (Versão 2 - Otimizado para 20GB)' AS status;
SELECT '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' AS info;

-- ============================================================================
-- 2. CRIAR TABELA
-- ============================================================================

DROP TABLE IF EXISTS cadastro;

CREATE TABLE cadastro (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    nome VARCHAR(100) NOT NULL,
    endereco VARCHAR(150) NOT NULL,
    telefone VARCHAR(20) NOT NULL,
    email VARCHAR(100),
    documento VARCHAR(20),
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    status ENUM('ativo', 'inativo', 'processado', 'pendente') DEFAULT 'ativo',
    valor_total DECIMAL(12,2) DEFAULT 0,
    KEY idx_status (status),
    KEY idx_email (email),
    KEY idx_data_criacao (data_criacao),
    KEY idx_documento (documento)
) ENGINE=InnoDB
    DEFAULT CHARSET=utf8mb4
    COLLATE=utf8mb4_unicode_ci
    ROW_FORMAT=DYNAMIC;

SELECT 'Tabela cadastro criada com sucesso' AS status;

-- ============================================================================
-- 3. CRIAR PROCEDURE OTIMIZADA
-- ============================================================================

DELIMITER //

DROP PROCEDURE IF EXISTS gerar_carga_teste //

CREATE PROCEDURE gerar_carga_teste()
MODIFIES SQL DATA
SQL SECURITY INVOKER
BEGIN
    DECLARE i INT DEFAULT 1;
    DECLARE inicio_fase TIMESTAMP;
    DECLARE fim_fase TIMESTAMP;
    DECLARE duracao_ms INT;
    DECLARE tempo_inicio_global TIMESTAMP;
    DECLARE tempo_fim_global TIMESTAMP;
    DECLARE duracao_total_ms INT;
    DECLARE registros_atuais INT;

    SET tempo_inicio_global = NOW(6);

    SELECT CONCAT(
        '┌─────────────────────────────────────────────────────────────────┐\n',
        '│ FASE 0: INSERT INICIAL (20 milhões de registros)               │\n',
        '└─────────────────────────────────────────────────────────────────┘'
    ) AS fase;

    SET inicio_fase = NOW(6);

    -- ========================================================================
    -- FASE 0: INSERT MASSIVO INICIAL
    -- Cria dataset base para testar buffer pool, cache hit rate, índices
    -- ========================================================================

    INSERT INTO cadastro (nome, endereco, telefone, email, documento, status, valor_total)
    SELECT
        CONCAT('Usuario_', s, '_Base'),
        CONCAT('Endereco Numero ', s, ' - Rua Principal'),
        CONCAT('(11) 9', LPAD(MOD(s, 99999999), 8, '0')),
        CONCAT('user', s, '@company.com'),
        CONCAT('DOC', LPAD(s, 12, '0')),
        CASE WHEN s % 4 = 0 THEN 'ativo'
             WHEN s % 4 = 1 THEN 'inativo'
             WHEN s % 4 = 2 THEN 'processado'
             ELSE 'pendente' END,
        ROUND(RAND() * 100000, 2)
    FROM
        (SELECT @row:=@row+1 as s FROM
            (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
             UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) t1,
            (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
             UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) t2,
            (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
             UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) t3,
            (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
             UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) t4,
            (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
             UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) t5,
            (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
             UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) t6,
            (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
             UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) t7,
            (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
             UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) t8,
            (SELECT @row:=-1) init
         LIMIT 20000000) x;

    SET fim_fase = NOW(6);
    SET duracao_ms = TIMESTAMPDIFF(MICROSECOND, inicio_fase, fim_fase) / 1000;
    SELECT CONCAT('✓ Inseridos 20.000.000 registros em ', FORMAT(duracao_ms/1000, 2), 's') AS resultado;

    -- ========================================================================
    -- FASE 1: CICLOS DE CARGA ACUMULATIVA (5 iterações)
    -- Simula operações reais: INSERT, UPDATE, DELETE com dados persistindo
    -- ========================================================================

    SELECT '' AS '';
    SELECT CONCAT(
        '┌─────────────────────────────────────────────────────────────────┐\n',
        '│ FASE 1: Carga Acumulativa (5 ciclos x 2M inserts)             │\n',
        '└─────────────────────────────────────────────────────────────────┘'
    ) AS fase;

    SET i = 1;
    ciclo_loop: LOOP
        IF i > 5 THEN LEAVE ciclo_loop; END IF;

        SET inicio_fase = NOW(6);

        -- INSERT: 2 milhões por ciclo
        INSERT INTO cadastro (nome, endereco, telefone, email, documento, status, valor_total)
        SELECT
            CONCAT('Usuario_', s, '_C', i),
            CONCAT('Endereco Ciclo ', i, ' - Numero ', s),
            CONCAT('(11) 9', LPAD(MOD(s, 99999999), 8, '0')),
            CONCAT('user_c', i, '_', s, '@company.com'),
            CONCAT('DCL', LPAD(i*1000000+s, 10, '0')),
            CASE WHEN s % 4 = 0 THEN 'ativo'
                 WHEN s % 4 = 1 THEN 'inativo'
                 ELSE 'processado' END,
            ROUND(RAND() * 50000, 2)
        FROM
            (SELECT @row:=@row+1 as s FROM
                (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
                 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) t1,
                (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
                 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) t2,
                (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
                 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) t3,
                (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
                 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) t4,
                (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
                 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) t5,
                (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
                 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) t6,
                (SELECT @row:=-1) init
             LIMIT 2000000) x;

        -- UPDATE: 50% dos registros (ciclo + anteriores)
        UPDATE cadastro
        SET status = CASE
                WHEN status = 'ativo' THEN 'processado'
                WHEN status = 'inativo' THEN 'ativo'
                ELSE 'inativo'
            END,
            valor_total = valor_total * 1.05,
            nome = CONCAT(SUBSTR(nome, 1, 60), '_UPD')
        WHERE MOD(id, 2) = 0;

        -- DELETE: 10% dos registros mais novos
        DELETE FROM cadastro
        WHERE id > (20000000 + (i-1)*2000000) AND MOD(id, 10) = 0;

        SET fim_fase = NOW(6);
        SET duracao_ms = TIMESTAMPDIFF(MICROSECOND, inicio_fase, fim_fase) / 1000;

        SELECT registros_atuais := (SELECT COUNT(*) FROM cadastro);
        SELECT CONCAT(
            '[CICLO ', i, '/5] Insert 2M, Update 50%, Delete 10% → ',
            FORMAT(registros_atuais, 0), ' registros (',
            FORMAT(duracao_ms/1000, 2), 's)'
        ) AS progresso;

        SET i = i + 1;
    END LOOP;

    -- ========================================================================
    -- FASE 2: QUERIES SELECT (CACHE HIT RATE)
    -- 15 segundos de queries leitura para medir cache hit rate e índice usage
    -- ========================================================================

    SELECT '' AS '';
    SELECT CONCAT(
        '┌─────────────────────────────────────────────────────────────────┐\n',
        '│ FASE 2: Stress em Leitura (1000s de SELECTs - 15 segundos)    │\n',
        '└─────────────────────────────────────────────────────────────────┘'
    ) AS fase;

    SET inicio_fase = NOW(6);
    SET i = 1;

    SELECT_LOOP: LOOP
        IF TIMESTAMPDIFF(SECOND, inicio_fase, NOW()) >= 15 THEN LEAVE SELECT_LOOP; END IF;

        -- Diferentes padrões de query para ativar índices e cache
        DO (SELECT COUNT(*) FROM cadastro WHERE status = 'ativo');
        DO (SELECT COUNT(*) FROM cadastro WHERE status = 'inativo');
        DO (SELECT SUM(valor_total) FROM cadastro WHERE status = 'processado');
        DO (SELECT COUNT(*) FROM cadastro WHERE email LIKE '%company.com');
        DO (SELECT MAX(id), MIN(id) FROM cadastro);
        DO (SELECT COUNT(DISTINCT status) FROM cadastro);
        DO (SELECT COUNT(*) FROM cadastro WHERE valor_total > 50000);

        SET i = i + 1;
    END LOOP;

    SELECT CONCAT('✓ Executadas ~', i*7, ' queries SELECT (cache hit rate ativo)') AS resultado;

    -- ========================================================================
    -- FASE 3: ANÁLISE FINAL
    -- ========================================================================

    SET tempo_fim_global = NOW(6);
    SET duracao_total_ms = TIMESTAMPDIFF(MICROSECOND, tempo_inicio_global, tempo_fim_global) / 1000;

    SELECT '' AS '';
    SELECT CONCAT(
        '┌─────────────────────────────────────────────────────────────────┐\n',
        '│ RESULTADO FINAL                                                 │\n',
        '└─────────────────────────────────────────────────────────────────┘'
    ) AS resultado;

    SELECT registros_atuais := (SELECT COUNT(*) FROM cadastro);

    SELECT CONCAT(
        'Registros finais: ', FORMAT(registros_atuais, 0), ' | ',
        'Tempo total: ', FORMAT(duracao_total_ms/1000, 2), 's | ',
        'Throughput: ', FORMAT(registros_atuais / (duracao_total_ms/1000), 0), ' ops/seg'
    ) AS resumo;

    SELECT TABLE_NAME, ENGINE, TABLE_ROWS,
           ROUND(DATA_LENGTH/1024/1024/1024, 2) AS data_gb,
           ROUND(INDEX_LENGTH/1024/1024/1024, 2) AS index_gb,
           ROUND((DATA_LENGTH + INDEX_LENGTH)/1024/1024/1024, 2) AS total_gb
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = 'lgtm' AND TABLE_NAME = 'cadastro';

END //

DELIMITER ;

-- ============================================================================
-- 4. EXECUTAR TESTE
-- ============================================================================

CALL gerar_carga_teste();

-- ============================================================================
-- 5. INSTRUÇÕES PARA VISUALIZAR MÉTRICAS
-- ============================================================================

SELECT '' AS '';
SELECT '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' AS info;
SELECT 'PRÓXIMOS PASSOS: Visualizar métricas no Grafana' AS instrucao;
SELECT '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' AS info;
SELECT '' AS '';

SELECT CONCAT(
    '1. Acesse: http://localhost:3000/d/linux-mysql-hosts\n',
    '2. Configure: instance = "srv-mysql-01"\n',
    '3. Observe os painéis:\n',
    '   ✓ HEALTH: mysql_up (deve ser 1)\n',
    '   ✓ ACTIVITY: mysql_global_status_questions (pico durante teste)\n',
    '   ✓ CAPACITY: innodb_buffer_pool_bytes_data (3-5GB em uso)\n',
    '   ✓ DIAGNOSTICS: innodb_data_reads (I/O ativo)\n',
    '   ✓ Cache Hit Rate: blks_hit / (blks_hit + blks_read) × 100 (95%+)'
) AS metricas_esperadas;

SELECT '' AS '';
SELECT 'Os dados persistem na tabela para análise contínua!' AS nota;
