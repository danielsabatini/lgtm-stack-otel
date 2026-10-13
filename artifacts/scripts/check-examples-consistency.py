#!/usr/bin/env python3
"""Valida os templates do OpenTelemetry Collector em examples/.

Uso:
    python3 artifacts/scripts/check-examples-consistency.py

Verificações (contra OTELCOL_CONTRIB_VERSION do .env.example; requer Docker):
  1. Agentes (examples/push): `otelcol-contrib validate`.
  2. Identidade OpenTelemetry dos agentes (resource_detection env+system com
     override, saída para o Gateway).
  3. Política Lean de métricas de host idêntica entre agentes e otel-agent.
  4. Coletas pull (examples/pull): validação mesclada com otel-agent/config.yaml e
     otel-agent/pull-semconv.yaml, identidade por alvo, ausência de
     resource_detection e conversão OTel de cada exporter no pipeline.
  5. Allowlists idênticas entre templates pull que coletam o mesmo exporter.

Saída não-zero se qualquer verificação falhar.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLES = ROOT / "examples"
ENV_EXAMPLE = ROOT / ".env.example"

# Templates pull que coletam o mesmo exporter (mesmo prefixo de métrica) e
# precisam manter a mesma allowlist Lean.
METRIC_GROUPS = [
    {
        "name": "Linux host (node_*)",
        "prefix": "node_",
        "files": ["pull/linux/linux-hosts.yaml", "pull/linux-dbaas-mysql/linux-dbaas-mysql-hosts.yaml", "pull/linux-dbaas-pgsql/linux-dbaas-pgsql-hosts.yaml", "pull/dns/dns-hosts.yaml"],
    },
    {
        "name": "Windows host (windows_* exceto windows_mssql_*)",
        "prefix": "windows_",
        "exclude_prefix": "windows_mssql_",
        "files": ["pull/windows/windows-hosts.yaml", "pull/windows-mssql/windows-mssql-hosts.yaml"],
    },
]


def env_version(var: str, default: str = "latest") -> str:
    m = re.search(rf"^{var}=(\S+)", ENV_EXAMPLE.read_text(), re.MULTILINE)
    return m.group(1) if m else default


def otelcol_image() -> str:
    return f"otel/opentelemetry-collector-contrib:{env_version('OTELCOL_CONTRIB_VERSION')}"


def otelcol_configs() -> list[Path]:
    """Configs completas do Collector (agentes) em examples/push/."""
    return sorted(
        f for f in (EXAMPLES / "push").rglob("*.yaml")
        if re.search(r"^receivers:", f.read_text(), re.MULTILINE)
    )


def pull_configs() -> list[Path]:
    """Templates de coleta pull (examples/pull/), carregados pelo otel-agent."""
    return sorted(
        f for f in (EXAMPLES / "pull").rglob("*.yaml")
        if re.search(r"^receivers:", f.read_text(), re.MULTILINE)
    )


OTEL_AGENT_CONFIG = ROOT / "otel-agent/config.yaml"
PULL_SEMCONV = ROOT / "otel-agent/pull-semconv.yaml"

# Cada exporter coletado por pull precisa da conversão para a OTel Semantic
# Conventions no pipeline (push e pull gravam o mesmo formato).
PULL_CONVERSIONS = {
    "job_name: node-exporter": "filter/node_semconv",
    "job_name: windows-exporter": "filter/windows_semconv",
    "windows_mssql_": "filter/mssql_semconv",
    "job_name: mysqld-exporter": "filter/mysql_semconv",
    "job_name: postgres-exporter": "filter/pgsql_semconv",
}


def validate_pull() -> bool:
    """Valida cada template pull MESCLADO com config.yaml + pull-semconv.yaml (como roda)."""
    image = otelcol_image()
    ok = True
    with tempfile.TemporaryDirectory() as hostfs:
        for f in pull_configs():
            result = subprocess.run(
                ["docker", "run", "--rm",
                 "-v", f"{hostfs}:/hostfs:ro",
                 "-v", f"{OTEL_AGENT_CONFIG}:/etc/otelcol-contrib/config.yaml:ro",
                 "-v", f"{PULL_SEMCONV}:/etc/otelcol-contrib/pull-semconv.yaml:ro",
                 "-v", f"{f}:/etc/otelcol-contrib/pull.d/pull.yaml:ro",
                 image, "validate",
                 "--config=/etc/otelcol-contrib/config.yaml",
                 "--config=/etc/otelcol-contrib/pull-semconv.yaml",
                 "--config=/etc/otelcol-contrib/pull.d/pull.yaml"],
                capture_output=True, text=True,
            )
            rel = f.relative_to(ROOT)
            text = f.read_text()
            problems = []
            if result.returncode != 0:
                problems.append(result.stderr.strip()[-1500:])
            if "resource_detection" in re.sub(r"#.*", "", text):
                problems.append("pipeline pull não pode usar resource_detection (atribuiria a identidade da stack)")
            if "host_name:" not in text:
                problems.append("alvos sem identidade host_name")
            for marker, proc in PULL_CONVERSIONS.items():
                if marker in text and proc not in text:
                    problems.append(f"falta a conversão OTel ({proc} de otel-agent/pull-semconv.yaml) no pipeline")
            if problems:
                ok = False
                print(f"FAIL {rel}")
                for pr in problems:
                    print(f"     {pr}")
            else:
                print(f"OK   {rel} (mesclado com config.yaml + pull-semconv.yaml; identidade por alvo; conversão OTel)")
    return ok


# Identidade OTel exigida em toda config de Collector que envia ao Gateway.
OTEL_IDENTITY_CHECKS = {
    "resource_detection com detectors [env, system]": r"detectors:\s*\[\s*env\s*,\s*system\s*\]",
    "resource_detection com override: true": r"resource_detection:[\s\S]*?override:\s*true",
    "exportador para o Gateway (LGTM_GATEWAY_ENDPOINT)": r"\$\{env:LGTM_GATEWAY_ENDPOINT",
}


# Configs de Collector que coletam o MESMO conjunto de métricas de host e
# precisam manter a política Lean idêntica (template de host x agent da stack).
HOST_METRICS_MIRRORS = [
    ROOT / "examples/push/linux/config.yaml",
    ROOT / "examples/push/linux-mysql/config.yaml",
    ROOT / "examples/push/linux-pgsql/config.yaml",
    ROOT / "examples/push/windows/config.yaml",
    ROOT / "examples/push/windows-mssql/config.yaml",
    ROOT / "otel-agent/config.yaml",
]


def enabled_metrics(text: str, prefix: str) -> dict[str, bool]:
    """Extrai `<métrica>: { enabled: true|false }` com o prefixo dado."""
    return {
        name: flag == "true"
        for name, flag in re.findall(rf"^\s+({re.escape(prefix)}[\w.]+):\s*\{{\s*enabled:\s*(true|false)", text, re.MULTILINE)
    }


def check_host_metrics_mirrors() -> bool:
    sets = {p: enabled_metrics(p.read_text(), "system.") for p in HOST_METRICS_MIRRORS}
    base_path, base = next(iter(sets.items()))
    ok = True
    for p, m in sets.items():
        if m != base:
            ok = False
            diff = sorted(set(m.items()) ^ set(base.items()))
            print(f"FAIL {p.relative_to(ROOT)} difere de {base_path.relative_to(ROOT)}: {diff}")
    if ok:
        on = sum(base.values())
        print(f"OK   host_metrics idêntico em {len(sets)} configs ({on} métricas system.* habilitadas, {len(base) - on} desabilitadas)")
    return ok


def validate_otelcol() -> bool:
    image = otelcol_image()
    ok = True
    for f in otelcol_configs():
        # Variáveis ${env:VAR} SEM default (ex.: credenciais) recebem valor
        # fictício: aqui só a sintaxe/estrutura é validada. As que têm
        # ${env:VAR:-default} usam o próprio default.
        env_vars = sorted(set(re.findall(r"\$\{env:([A-Z0-9_]+)\}", f.read_text())))
        env_args = [arg for v in env_vars for arg in ("-e", f"{v}=validate-placeholder")]
        result = subprocess.run(
            ["docker", "run", "--rm", *env_args, "-v", f"{f}:/etc/otelcol-contrib/config.yaml:ro",
             image, "validate", "--config=/etc/otelcol-contrib/config.yaml"],
            capture_output=True, text=True,
        )
        rel = f.relative_to(ROOT)
        # Configs Windows: o validate roda em container Linux, onde o receiver
        # windows_event_log se recusa a ser criado. Se esse for o ÚNICO erro, a
        # estrutura foi interpretada inteira (o validate real roda no Windows).
        windows_only = (
            result.returncode != 0
            and "windows eventlog receiver is only supported on Windows" in result.stderr
            and result.stderr.count("Error:") == 1
        )
        if result.returncode != 0 and not windows_only:
            ok = False
            print(f"FAIL {rel}")
            print(result.stderr.strip()[-2000:])
        elif windows_only:
            print(f"OK   {rel} (estrutura OK; receivers do Event Log só são criados no Windows)")
        else:
            print(f"OK   {rel}")
    return ok


def check_otel_identity() -> bool:
    ok = True
    for f in otelcol_configs():
        text = f.read_text()
        missing = [name for name, rx in OTEL_IDENTITY_CHECKS.items() if not re.search(rx, text)]
        rel = f.relative_to(ROOT)
        if missing:
            ok = False
            print(f"FAIL {rel}: {'; '.join(missing)}")
        else:
            print(f"OK   {rel}: identidade OTel (env + system, override) e saída para o Gateway")
    return ok


def extract_keep_metric_names_yaml(text: str, prefix: str, exclude_prefix: str | None = None) -> set[str]:
    """Extrai a allowlist de um metric_relabel_configs (action: keep) em YAML."""
    names: set[str] = set()
    for m in re.finditer(r"action:\s*keep\s*\n\s*regex:\s*>-?\s*\n\s*(\S+)", text):
        for name in m.group(1).split("|"):
            # Entradas com curinga (ex.: node_disk_read.*) não entram na comparação.
            if "*" in name:
                continue
            if name.startswith(prefix) and not (exclude_prefix and name.startswith(exclude_prefix)):
                names.add(name)
    return names


def check_metric_groups() -> bool:
    ok = True
    for group in METRIC_GROUPS:
        sets = {}
        for rel in group["files"]:
            path = EXAMPLES / rel
            text = path.read_text()
            sets[rel] = extract_keep_metric_names_yaml(text, group["prefix"], group.get("exclude_prefix"))

        union: set[str] = set()
        for names in sets.values():
            union |= names

        group_ok = True
        for rel, names in sets.items():
            missing = sorted(union - names)
            if missing:
                group_ok = False
                ok = False
                print(f"FAIL [{group['name']}] examples/{rel}: faltam {missing}")

        if group_ok:
            print(f"OK   [{group['name']}] {len(group['files'])} arquivos consistentes ({len(union)} métricas)")
    return ok


def main() -> None:
    print("== 1. Agentes: sintaxe (otelcol-contrib validate) ==")
    ok = validate_otelcol()

    print("\n== 2. Agentes: identidade OpenTelemetry ==")
    ok = check_otel_identity() and ok

    print("\n== 3. Política Lean de métricas de host (agentes x otel-agent) ==")
    ok = check_host_metrics_mirrors() and ok

    print("\n== 4. Coletas pull (otel-agent/pull.d) ==")
    ok = validate_pull() and ok

    print("\n== 5. Allowlists dos templates pull ==")
    ok = check_metric_groups() and ok

    if not ok:
        print("\nFALHOU — corrija os itens acima antes de finalizar a edição.")
        sys.exit(1)

    print("\nOK — examples/ consistente.")


if __name__ == "__main__":
    main()
