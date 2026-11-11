"""
Requisição HTTP com diagnóstico da falha.

Distingue o motivo para o log/estado não ficar só em "falhou":
  BLOQUEIO_PROXY   proxy corporativo recusou o túnel (403/407 no CONNECT)
  TIMEOUT          sem resposta (firewall descartando ou site lento)
  CONEXAO_RECUSADA host/porta fechados ou DNS não resolve
  HTTP_<código>    o site respondeu com erro (404 = CNPJ inexistente, 429 = limite)
  RESPOSTA_INVALIDA resposta não é JSON (página de desafio anti-robô, por exemplo)

urllib usa HTTP_PROXY/HTTPS_PROXY/NO_PROXY do ambiente automaticamente.
"""
import json
import socket
import urllib.error
import urllib.request

UA = {
    "User-Agent": "ecoprospect/1.0 (+consulta cadastral CNPJ)",
    "Accept": "application/json",
}


def classificar_erro(erro: Exception) -> str:
    if isinstance(erro, urllib.error.HTTPError):
        return f"HTTP_{erro.code}"
    texto = str(erro)
    if "Tunnel connection failed" in texto or "407" in texto or ("403" in texto and "Tunnel" in texto):
        return "BLOQUEIO_PROXY"
    if isinstance(erro, (socket.timeout, TimeoutError)) or "timed out" in texto:
        return "TIMEOUT"
    if isinstance(erro, urllib.error.URLError):
        motivo = getattr(erro, "reason", None)
        if isinstance(motivo, (socket.timeout, TimeoutError)):
            return "TIMEOUT"
        if isinstance(motivo, socket.gaierror):
            return "DNS_FALHOU"
        if isinstance(motivo, ConnectionRefusedError):
            return "CONEXAO_RECUSADA"
        if "CERTIFICATE_VERIFY_FAILED" in texto:
            return "TLS_CERTIFICADO"
    return f"ERRO_{type(erro).__name__}"


def get_json(url: str, timeout: int = 15):
    """Retorna (dados, None) em sucesso ou (None, 'CODIGO: detalhe') em falha."""
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            corpo = resp.read().decode("utf-8", errors="replace")
    except Exception as erro:  # noqa: BLE001 - classificado abaixo
        return None, f"{classificar_erro(erro)}: {erro}"
    try:
        return json.loads(corpo), None
    except ValueError:
        return None, f"RESPOSTA_INVALIDA: {corpo[:120]!r}"
