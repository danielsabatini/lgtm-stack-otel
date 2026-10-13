#!/usr/bin/env python3
"""
Serviço HTTP genérico de 3 camadas para validar propagação de contexto
distribuído do OBI (OpenTelemetry eBPF Instrumentation) — SEM nenhuma instrumentação manual.

Somente stdlib. Nenhum import de OpenTelemetry. Nenhuma manipulação de
cabeçalho `traceparent`. Toda a correlação entre serviços é produzida pelo
OBI via `ebpf: context_propagation: headers` (examples/push/linux/obi.yaml).

Configuração por ambiente:
  TIER_NAME   nome lógico do serviço (apenas para o corpo da resposta/log)
  TIER_PORT   porta de escuta
  TIER_NEXT   URL base do próximo serviço da cadeia (vazio = folha)

Rotas:
  /        sucesso     -> 200
  /slow    lentidão    -> 200 após ~1.2s na folha (exercita tail sampling >1000ms)
  /error   falha       -> 500 (retenção de 100% dos erros no gateway)
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NAME = os.environ.get("TIER_NAME", "tier")
PORT = int(os.environ.get("TIER_PORT", "8080"))
NEXT = os.environ.get("TIER_NEXT", "").rstrip("/")

# Latência aplicada pela folha na rota /slow. Acima do limiar de 1000ms usado
# pelo tail sampling do OTel Gateway.
SLOW_SECONDS = 1.2

ROUTES = ("/", "/slow", "/error")


def call_next(path: str) -> tuple[int, dict]:
    """Chama o próximo serviço da cadeia via HTTP simples (cleartext).

    O OBI injeta o cabeçalho `traceparent` nesta requisição de saída no nível
    do kernel. O código abaixo não sabe que traces existem.
    """
    url = f"{NEXT}{path}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        body = exc.read() or b"{}"
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"raw": body.decode("utf-8", "replace")}
        return exc.code, payload
    except Exception as exc:  # noqa: BLE001 - erro de transporte vira 502 lógico
        return 502, {"service": NAME, "downstream_error": str(exc)}


class Handler(BaseHTTPRequestHandler):
    # HTTP/1.1 com keep-alive: reflete tráfego real e mantém o padrão de
    # requisição que o OBI observa entre as camadas.
    protocol_version = "HTTP/1.1"
    server_version = f"tier/{NAME}"

    def log_message(self, fmt: str, *args) -> None:
        sys.stdout.write(f"[{NAME}] {fmt % args}\n")
        sys.stdout.flush()

    def _respond(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - assinatura da stdlib
        path = self.path.split("?", 1)[0]

        if path not in ROUTES:
            self._respond(404, {"service": NAME, "path": path})
            return

        # Camada intermediária: repassa a chamada e devolve o status recebido.
        if NEXT:
            status, downstream = call_next(path)
            self._respond(status, {"service": NAME, "downstream": downstream})
            return

        # Camada folha: onde o comportamento de fato acontece.
        if path == "/slow":
            time.sleep(SLOW_SECONDS)
            self._respond(200, {"service": NAME, "route": path, "slept": SLOW_SECONDS})
        elif path == "/error":
            self._respond(500, {"service": NAME, "route": path, "error": "simulated failure"})
        else:
            self._respond(200, {"service": NAME, "route": path})


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    sys.stdout.write(f"[{NAME}] listening on :{PORT} next={NEXT or '<leaf>'}\n")
    sys.stdout.flush()
    server.serve_forever()


if __name__ == "__main__":
    main()
