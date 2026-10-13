#!/usr/bin/env python3
"""Regenera todos os dashboards provisionados e verifica a conformidade com a metodologia.

Os JSONs em grafana/provisioning/dashboards/ são GERADOS por estes scripts (fonte
da verdade dos dashboards): altere o gerador e rode

    python3 artifacts/dashboards/build.py

O Grafana recarrega os arquivos em até 30 s. Ao final roda
artifacts/scripts/check-dashboards-methodology.py (saída não-zero se houver violação).
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DASH = ROOT / "grafana/provisioning/dashboards"

# gerador -> arquivo de saída
TARGETS = [
    ("linux_hosts.py", "Hosts/linux-hosts.json"),
    ("windows_hosts.py", "Hosts/windows-hosts.json"),
    ("linux_mysql.py", "Hosts + Database/linux-mysql-hosts.json"),
    ("linux_pgsql.py", "Hosts + Database/linux-pgsql-hosts.json"),
    ("windows_mssql.py", "Hosts + Database/windows-hosts-mssql.json"),
    ("lgtm_stack.py", "LGTM/lgtm-stack.json"),
    ("dns.py", "DNS/mgc-internal-dns.json"),  # regera a linha Linux; CoreDNS/etcd vêm do próprio arquivo
]


def main() -> int:
    for script, out in TARGETS:
        target = DASH / out
        target.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run([sys.executable, script, str(target)], cwd=HERE, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"FALHA {script}:\n{result.stderr}")
            return 1
        print(f"OK   {out}")
    check = ROOT / "artifacts/scripts/check-dashboards-methodology.py"
    return subprocess.run([sys.executable, str(check), str(DASH)]).returncode


if __name__ == "__main__":
    sys.exit(main())
