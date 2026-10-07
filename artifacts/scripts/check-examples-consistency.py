#!/usr/bin/env python3
"""Valida os templates em examples/: sintaxe + identidade + consistência entre arquivos-irmãos.

Uso:
    python3 artifacts/scripts/check-examples-consistency.py

Durante a migração Alloy -> OpenTelemetry Collector convivem dois formatos:
  - OpenTelemetry Collector (YAML com bloco `receivers:`): `otelcol-contrib validate`
    contra OTELCOL_CONTRIB_VERSION e checagem da identidade OTel
    (resource_detection env+system com override, saída para o Gateway).
  - Alloy legado (*.alloy): `alloy validate` contra GRAFANA_ALLOY_VERSION e os
    5 labels de identidade antigos.

Requer Docker. Saída não-zero se qualquer verificação falhar.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLES = ROOT / "examples"
ENV_EXAMPLE = ROOT / ".env.example"

IDENTITY_LABELS = [
    "instance",
    "environment",
    "cloud_provider",
    "cloud_region",
    "cloud_availability_zone",
]

# Arquivos que enviam dados ao gateway central e, portanto, precisam carregar
# os 5 labels de identidade global em algum ponto do pipeline (via rule
# target_label=... ou via targets=[{...}] no modelo pull).
GATEWAY_FILES = [
    "push/windows/config.alloy",
    "push/windows-mssql/config.alloy",
    "pull/windows/windows-hosts.alloy",
    "pull/windows-mssql/windows-mssql-hosts.alloy",
]

# Grupos de arquivos cuja allowlist de métricas (mesmo prefixo) deve ser
# idêntica, porque o próprio repositório documenta que um espelha o outro
# (agente vs. pull do mesmo host/coletor).
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
        "files": [
            "push/windows/config.alloy",
            "push/windows-mssql/config.alloy",
            "pull/windows/windows-hosts.alloy",
            "pull/windows-mssql/windows-mssql-hosts.alloy",
        ],
    },
    {
        "name": "Windows MSSQL (windows_mssql_*)",
        "prefix": "windows_mssql_",
        "files": [
            "push/windows-mssql/config.alloy",
            "pull/windows-mssql/windows-mssql-hosts.alloy",
        ],
    },
]


def env_version(var: str, default: str = "latest") -> str:
    m = re.search(rf"^{var}=(\S+)", ENV_EXAMPLE.read_text(), re.MULTILINE)
    return m.group(1) if m else default


def alloy_image() -> str:
    return f"grafana/alloy:{env_version('GRAFANA_ALLOY_VERSION')}"


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


def validate_pull() -> bool:
    """Valida cada template pull MESCLADO com o otel-agent/config.yaml (como roda)."""
    image = otelcol_image()
    ok = True
    with tempfile.TemporaryDirectory() as hostfs:
        for f in pull_configs():
            result = subprocess.run(
                ["docker", "run", "--rm",
                 "-v", f"{hostfs}:/hostfs:ro",
                 "-v", f"{OTEL_AGENT_CONFIG}:/etc/otelcol-contrib/config.yaml:ro",
                 "-v", f"{f}:/etc/otelcol-contrib/pull.d/pull.yaml:ro",
                 image, "validate",
                 "--config=/etc/otelcol-contrib/config.yaml",
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
            if problems:
                ok = False
                print(f"FAIL {rel}")
                for pr in problems:
                    print(f"     {pr}")
            else:
                print(f"OK   {rel} (mesclado com otel-agent/config.yaml; identidade por alvo)")
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
        if result.returncode != 0:
            ok = False
            print(f"FAIL {rel}")
            print(result.stderr.strip()[-2000:])
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


def validate_syntax() -> bool:
    image = alloy_image()
    ok = True
    for f in sorted(EXAMPLES.rglob("*.alloy")):
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", f"{f}:/etc/alloy/config.alloy:ro",
                image, "validate", "/etc/alloy/config.alloy",
            ],
            capture_output=True, text=True,
        )
        rel = f.relative_to(ROOT)
        if result.returncode != 0:
            ok = False
            print(f"FAIL {rel}")
            print(result.stderr.strip())
        else:
            print(f"OK   {rel}")
    return ok


def check_identity_labels() -> bool:
    ok = True
    for rel in GATEWAY_FILES:
        path = EXAMPLES / rel
        if not path.exists():
            print(f"FAIL {rel}: arquivo não encontrado")
            ok = False
            continue
        text = path.read_text()
        missing = [label for label in IDENTITY_LABELS if f'"{label}"' not in text]
        if missing:
            ok = False
            print(f"FAIL examples/{rel}: labels de identidade ausentes: {', '.join(missing)}")
        else:
            print(f"OK   examples/{rel}: 5 labels de identidade presentes")
    return ok


def extract_keep_metric_names_yaml(text: str, prefix: str, exclude_prefix: str | None = None) -> set[str]:
    """Extrai a allowlist de um metric_relabel_configs (action: keep) em YAML."""
    names: set[str] = set()
    for m in re.finditer(r"action:\s*keep\s*\n\s*regex:\s*>-?\s*\n\s*(\S+)", text):
        for name in m.group(1).split("|"):
            # Mesmo critério do extrator .alloy: entradas com curinga (ex.:
            # node_disk_read.*) não entram na comparação.
            if "*" in name:
                continue
            if name.startswith(prefix) and not (exclude_prefix and name.startswith(exclude_prefix)):
                names.add(name)
    return names


def extract_keep_metric_names(text: str, prefix: str, exclude_prefix: str | None = None) -> set[str]:
    """Extrai nomes de métrica dentro de blocos `rule { ... action = "keep" ... regex = ... }`.

    Restrito a esses blocos (em vez do arquivo inteiro) para não capturar
    nomes de componentes Alloy (ex: `prometheus.relabel "windows_host_labels"`),
    que colidem com o mesmo prefixo das métricas.
    """
    names: set[str] = set()
    for m in re.finditer(r"rule\s*\{([^{}]*)\}", text, re.DOTALL):
        block = m.group(1)
        if '"keep"' in block and "regex" in block:
            # Itens de allowlist concatenados via `+` terminam em "|" dentro
            # das aspas (ex: "node_boot_time_seconds|"), exceto o último item
            # da lista — por isso o "|" opcional antes do fechamento.
            for name in re.findall(rf'"({re.escape(prefix)}[a-zA-Z0-9_.]*)\|?"', block):
                if exclude_prefix and name.startswith(exclude_prefix):
                    continue
                names.add(name)
    return names


def check_metric_groups() -> bool:
    ok = True
    for group in METRIC_GROUPS:
        sets = {}
        for rel in group["files"]:
            path = EXAMPLES / rel
            text = path.read_text()
            extract = extract_keep_metric_names_yaml if rel.endswith(".yaml") else extract_keep_metric_names
            sets[rel] = extract(text, group["prefix"], group.get("exclude_prefix"))

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
    print("== 1. Sintaxe OpenTelemetry Collector (otelcol-contrib validate) ==")
    ok0 = validate_otelcol()

    print("\n== 2. Identidade OpenTelemetry (configs do Collector) ==")
    ok00 = check_otel_identity()

    print("\n== 2b. Política Lean de métricas de host espelhada (template x otel-agent) ==")
    ok00 = check_host_metrics_mirrors() and ok00

    print("\n== 2c. Coletas pull (otel-agent/pull.d) ==")
    ok00 = validate_pull() and ok00

    print("\n== 3. Sintaxe Alloy legado (alloy validate) ==")
    ok1 = validate_syntax()

    print("\n== 4. Labels de identidade global (Alloy legado) ==")
    ok2 = check_identity_labels()

    print("\n== 5. Consistência de allowlists entre arquivos espelhados (Alloy legado) ==")
    ok3 = check_metric_groups()

    if not (ok0 and ok00 and ok1 and ok2 and ok3):
        print("\nFALHOU — corrija os itens acima antes de finalizar a edição.")
        sys.exit(1)

    print("\nOK — examples/ consistente.")


if __name__ == "__main__":
    main()
