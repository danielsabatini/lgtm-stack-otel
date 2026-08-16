#!/usr/bin/env python3
"""Valida os templates em examples/: sintaxe Alloy + consistência entre arquivos-irmãos.

Uso:
    python3 scripts/check-examples-consistency.py

Requer Docker (para `alloy validate` contra a versão pinada em .env.example).
Saída não-zero se qualquer verificação falhar.
"""
import re
import subprocess
import sys
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
    "linux/config.alloy",
    "linux-mysql/config.alloy",
    "linux-pgsql/config.alloy",
    "windows/config.alloy",
    "windows-mssql/config.alloy",
    "remote-scrape/pull-linux-hosts.alloy",
    "remote-scrape/pull-windows-hosts.alloy",
    "remote-scrape/pull-windows-mssql-hosts.alloy",
    "remote-scrape/pull-linux-dbaas-mysql-hosts.alloy",
    "remote-scrape/pull-linux-dbaas-pgsql-hosts.alloy",
    "remote-scrape/pull-coredns-hosts.alloy",
    "remote-scrape/pull-etcd-hosts.alloy",
]

# Grupos de arquivos cuja allowlist de métricas (mesmo prefixo) deve ser
# idêntica, porque o próprio repositório documenta que um espelha o outro
# (agente vs. pull do mesmo host/coletor).
METRIC_GROUPS = [
    {
        "name": "Linux host (node_*)",
        "prefix": "node_",
        "files": ["linux/config.alloy", "remote-scrape/pull-linux-hosts.alloy"],
    },
    {
        "name": "Windows host (windows_* exceto windows_mssql_*)",
        "prefix": "windows_",
        "exclude_prefix": "windows_mssql_",
        "files": [
            "windows/config.alloy",
            "windows-mssql/config.alloy",
            "remote-scrape/pull-windows-hosts.alloy",
            "remote-scrape/pull-windows-mssql-hosts.alloy",
        ],
    },
    {
        "name": "Windows MSSQL (windows_mssql_*)",
        "prefix": "windows_mssql_",
        "files": [
            "windows-mssql/config.alloy",
            "remote-scrape/pull-windows-mssql-hosts.alloy",
        ],
    },
]


def alloy_image() -> str:
    text = ENV_EXAMPLE.read_text()
    m = re.search(r"GRAFANA_ALLOY_VERSION=(\S+)", text)
    version = m.group(1) if m else "latest"
    return f"grafana/alloy:{version}"


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
            sets[rel] = extract_keep_metric_names(text, group["prefix"], group.get("exclude_prefix"))

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
    print("== 1. Sintaxe (alloy validate) ==")
    ok1 = validate_syntax()

    print("\n== 2. Labels de identidade global ==")
    ok2 = check_identity_labels()

    print("\n== 3. Consistência de allowlists entre arquivos espelhados ==")
    ok3 = check_metric_groups()

    if not (ok1 and ok2 and ok3):
        print("\nFALHOU — corrija os itens acima antes de finalizar a edição.")
        sys.exit(1)

    print("\nOK — examples/ consistente.")


if __name__ == "__main__":
    main()
