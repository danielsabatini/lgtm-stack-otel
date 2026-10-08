"""MGC Internal DNS (adth4vt): visão de cluster (variável host multi, padrão All).
Linha Linux = mesmas abas system.* dos hosts em modo multi-host (pull
convertido para OTel); linhas CoreDNS e etcd = porte do dashboard original
(sem OTel Semantic Conventions, mantêm os nomes dos exporters).

As linhas CoreDNS e etcd são mantidas a partir do próprio dashboard provisionado
(portadas do dashboard original e com os ajustes da metodologia aplicados aqui);
só a linha Linux é regerada. Idempotente.
Uso: dns.py <dashboard provisionado (entrada e saída)>
"""
import json
import sys
from lib import Dash
from hosts import host_tabs

SRC = OUT = sys.argv[1]
old = json.load(open(SRC))
ospec = old["spec"]

d = Dash("adth4vt", ospec["title"], sorted(set(ospec.get("tags", [])) | {"opentelemetry"}))
d.query_var("host", "Host", 'query_result(count by ("host.name") ({"coredns_build_info"}))',
            '/host\\.name="([^"]+)"/', multi=True)
d.row("Linux", host_tabs(d, "linux", multi=True))
new = d.build()

# linhas CoreDNS e etcd do porte (elementos renomeados para não colidir)
keep = [r for r in ospec["layout"]["spec"]["rows"] if r["spec"]["title"] != "Linux"]
used = set()


def collect(layout):
    k, s = layout["kind"], layout["spec"]
    if k == "TabsLayout":
        for t in s["tabs"]:
            collect(t["spec"]["layout"])
    elif "items" in s:
        for it in s["items"]:
            n = it["spec"]["element"]["name"]
            if not n.startswith("dns-"):
                it["spec"]["element"]["name"] = "dns-" + n
            used.add(n)


# Metodologia: taxas ficam em Activity (sai do Health) e limiares/cores de
# alarme só no Health (§3, §4.1).
for r in keep:
    for t in r["spec"]["layout"]["spec"]["tabs"]:
        items = t["spec"]["layout"]["spec"]["items"]
        if t["spec"]["title"] == "Health":
            items[:] = [it for it in items
                        if ospec["elements"][it["spec"]["element"]["name"]]["spec"]["title"] != "Query Rate"]
        else:
            for it in items:
                fc = ospec["elements"][it["spec"]["element"]["name"]]["spec"]["vizConfig"]["spec"]["fieldConfig"]
                fc["defaults"]["thresholds"] = {"mode": "absolute", "steps": [{"value": 0, "color": "text"}]}
                fc["defaults"].get("custom", {}).pop("thresholdsStyle", None)
                fc["defaults"]["color"] = {"mode": "thresholds"} if fc["defaults"].get("color", {}).get("mode") == "thresholds" \
                    else fc["defaults"].get("color", {"mode": "palette-classic"})
for r in keep:
    collect(r["spec"]["layout"])
for n in sorted(used):
    new["spec"]["elements"][n if n.startswith("dns-") else "dns-" + n] = ospec["elements"][n]
new["spec"]["layout"]["spec"]["rows"] += keep
json.dump(new, open(OUT, "w"), indent=2, ensure_ascii=False)
open(OUT, "a").write("\n")
print("linhas:", [r["spec"]["title"] for r in new["spec"]["layout"]["spec"]["rows"]], "elementos:", len(new["spec"]["elements"]))
