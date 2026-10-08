#!/usr/bin/env python3
"""Verifica os dashboards provisionados contra docs/OBSERVABILITY-METHODOLOGY.md.

Regras objetivas checadas em cada aba de cada linha:
  - abas só da taxonomia: Health, Capacity, Activity, Diagnostics, Inventory,
    Logs e Traces (§4, §5) — e nenhuma aba vazia (§9.2);
  - limiares e cores de alarme só no Health (§3);
  - Capacity em unidades absolutas, nunca em % (§3, §4.2);
  - Health só com %, status binário (UP/DOWN) ou latência p99 de serviço (§4.1, §9.1).

Uso: python3 artifacts/scripts/check-dashboards-methodology.py grafana/provisioning/dashboards
Saída não-zero se houver violação.
"""
import glob, json, sys
ALLOWED = {"Health", "Capacity", "Activity", "Diagnostics", "Inventory", "Logs", "Traces"}
PCT = {"percent", "percentunit"}
problems = 0
for f in sorted(glob.glob(sys.argv[1] + "/*/*.json")):
    d = json.load(open(f)); sp = d["spec"]; els = sp["elements"]
    for row in sp["layout"]["spec"]["rows"]:
        for t in row["spec"]["layout"]["spec"]["tabs"]:
            tab = t["spec"]["title"]
            if tab not in ALLOWED:
                print(f"ABA   {sp['title']} / {row['spec']['title']} / {tab}: aba fora da taxonomia"); problems += 1
            if not t["spec"]["layout"]["spec"]["items"]:
                print(f"VAZIA {sp['title']} / {row['spec']['title']} / {tab}"); problems += 1
            for it in t["spec"]["layout"]["spec"]["items"]:
                p = els[it["spec"]["element"]["name"]]["spec"]; df = p["vizConfig"]["spec"]["fieldConfig"]["defaults"]
                unit = df.get("unit", ""); steps = df.get("thresholds", {}).get("steps", [])
                alarm = any(s.get("color") not in ("green", "text", "transparent") for s in steps) or \
                    df.get("custom", {}).get("thresholdsStyle", {}).get("mode", "off") != "off"
                where = f"{sp['title']} / {row['spec']['title']} / {tab} / {p['title']}"
                if alarm and tab != "Health":
                    print(f"LIMIAR fora do Health: {where}"); problems += 1
                if tab == "Capacity" and unit in PCT:
                    print(f"CAPACITY em %: {where}"); problems += 1
                if tab == "Health" and p["vizConfig"]["group"] in ("stat", "gauge"):
                    binary = "mappings" in df or alarm and unit in ("", "short", "none") and not p["title"].lower().startswith(("coletores",))
                    ok = unit in PCT or binary or "p99" in p["title"].lower() or unit == "bps" and not alarm
                    if not ok:
                        print(f"HEALTH sem %/binário: {where} [{unit}]"); problems += 1
print("problemas:", problems)
sys.exit(1 if problems else 0)
