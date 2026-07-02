import os
import time
import json
import hashlib
import secrets as _secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, urlencode, parse_qs

import requests

from config import (
    TIKTOK_ACCESS_TOKEN,
    TIKTOK_PRIVACY,
    TIKTOK_CLIENT_KEY,
    TIKTOK_CLIENT_SECRET,
    TIKTOK_REDIRECT_URI,
    TIKTOK_TOKEN_PATH,
    TIKTOK_SCOPES,
)

API_BASE = "https://open.tiktokapis.com/v2"
AUTH_BASE = "https://www.tiktok.com/v2/auth"
SCOPES = TIKTOK_SCOPES

MAX_CHUNK = 64 * 1024 * 1024  # 64 MB


def _gerar_pkce():
    """Gera (code_verifier, code_challenge S256) para PKCE.
    O TikTok exige HEX encoding do SHA256 (NÃO base64url)."""
    verifier = _secrets.token_urlsafe(64)
    challenge = hashlib.sha256(verifier.encode()).hexdigest()
    return verifier, challenge


# --- Persistência e renovação de token -------------------------------------

def _ler_token():
    if os.path.exists(TIKTOK_TOKEN_PATH):
        try:
            with open(TIKTOK_TOKEN_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _salvar_token(dados):
    os.makedirs(os.path.dirname(TIKTOK_TOKEN_PATH), exist_ok=True)
    with open(TIKTOK_TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def _refresh_token():
    """Renova o access_token usando o refresh_token salvo."""
    dados = _ler_token()
    refresh = dados.get("refresh_token")
    if not refresh or not TIKTOK_CLIENT_KEY or not TIKTOK_CLIENT_SECRET:
        return None

    print("  [TT Auth] Token expirado, renovando via refresh_token...")
    try:
        resp = requests.post(
            f"{API_BASE}/oauth/token/",
            data={
                "client_key": TIKTOK_CLIENT_KEY,
                "client_secret": TIKTOK_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": refresh,
            },
            timeout=30,
        )
        r = resp.json()
    except Exception as e:
        print(f"  [ERRO] refresh falhou: {e}")
        return None

    if "access_token" not in r:
        print(f"  [ERRO] refresh rejeitado: {r}")
        return None

    dados.update({
        "access_token": r["access_token"],
        "refresh_token": r.get("refresh_token", refresh),
        "expires_at": time.time() + int(r.get("expires_in", 86400)),
        "refresh_expires_at": time.time() + int(r.get("refresh_expires_in", 31536000)),
        "open_id": r.get("open_id", dados.get("open_id")),
    })
    _salvar_token(dados)
    print("  [TT Auth] Token renovado.")
    return dados["access_token"]


def _access_token():
    """Retorna um access_token válido: do arquivo (renovando se preciso) ou do .env."""
    dados = _ler_token()
    if dados.get("access_token"):
        if dados.get("expires_at", 0) - 60 < time.time():
            novo = _refresh_token()
            if novo:
                return novo
            print("  [ERRO] Não foi possível renovar o token TikTok.")
            return None
        return dados["access_token"]
    # fallback: token fixo do .env (expira em 24h, sem renovação)
    return TIKTOK_ACCESS_TOKEN


# --- OAuth interativo (1ª vez) ---------------------------------------------

def autenticar():
    """Fluxo OAuth interativo (uma única vez). Abre o navegador."""
    if not TIKTOK_CLIENT_KEY or not TIKTOK_CLIENT_SECRET:
        print("  [ERRO] Configure TIKTOK_CLIENT_KEY e TIKTOK_CLIENT_SECRET no .env")
        print("  (painel do app TikTok → Basic settings)")
        return False

    parsed = urlparse(TIKTOK_REDIRECT_URI)
    host = parsed.hostname or "localhost"
    port = parsed.port or 9876
    state = _secrets.token_urlsafe(8)
    verifier, challenge = _gerar_pkce()

    params = urlencode({
        "client_key": TIKTOK_CLIENT_KEY,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": TIKTOK_REDIRECT_URI,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    auth_url = f"{AUTH_BASE}/authorize?{params}"

    resultado = {"code": None, "erro": None}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            q = parse_qs(urlparse(self.path).query)
            if q.get("state", [""])[0] != state:
                self.send_response(400); self.end_headers(); return
            if q.get("code"):
                resultado["code"] = q["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h1>OK! Pode fechar esta aba.</h1>")
            else:
                resultado["erro"] = q.get("error_description", q.get("error", ["desconhecido"]))[0]
                self.send_response(400); self.end_headers()

        def log_message(self, *a):
            pass

    httpd = HTTPServer((host, port), Handler)
    print(f"  [TT Auth] Abra este link no navegador e autorize:")
    print(f"  {auth_url}\n")
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    timer = threading.Timer(180, lambda: httpd.shutdown())
    timer.daemon = True
    timer.start()
    httpd.serve_forever()
    httpd.server_close()
    timer.cancel()

    if resultado["erro"]:
        print(f"  [ERRO] Autorização negada: {resultado['erro']}")
        return False
    if not resultado["code"]:
        print("  [ERRO] Não recebeu o código. Tente novamente.")
        return False

    # troca o code pelo token
    try:
        resp = requests.post(
            f"{API_BASE}/oauth/token/",
            data={
                "client_key": TIKTOK_CLIENT_KEY,
                "client_secret": TIKTOK_CLIENT_SECRET,
                "code": resultado["code"],
                "grant_type": "authorization_code",
                "redirect_uri": TIKTOK_REDIRECT_URI,
                "code_verifier": verifier,
            },
            timeout=30,
        )
        r = resp.json()
    except Exception as e:
        print(f"  [ERRO] troca de token falhou: {e}")
        return False

    if "access_token" not in r:
        print(f"  [ERRO] troca rejeitada: {r}")
        return False

    _salvar_token({
        "access_token": r["access_token"],
        "refresh_token": r["refresh_token"],
        "expires_at": time.time() + int(r.get("expires_in", 86400)),
        "refresh_expires_at": time.time() + int(r.get("refresh_expires_in", 31536000)),
        "open_id": r.get("open_id"),
        "scope": r.get("scope"),
    })
    print(f"  [OK] Token salvo em {TIKTOK_TOKEN_PATH}")
    print("  Renovação automática ativada (refresh_token válido por ~365 dias).")
    return True


# --- Upload ----------------------------------------------------------------

def _montar_titulo(titulo, descricao, tags):
    partes = [titulo or ""]
    if descricao:
        partes.append(descricao)
    if tags:
        partes.append(" ".join(f"#{t}" for t in tags if t))
    caption = "\n\n".join(p for p in partes if p)
    return caption[:150]


def upload_video(caminho_video, titulo, descricao="", tags=None,
                 privacy_level=None):
    """Faz upload direto (Direct Post) do vídeo no TikTok. Retorna publish_id ou None."""
    if not os.path.exists(caminho_video):
        print(f"  [ERRO] Vídeo não encontrado: {caminho_video}")
        return None

    token = _access_token()
    if not token:
        print("  [ERRO] Sem token TikTok. Rode: python postar.py --auth-tiktok")
        return None

    print(f"  [TT Upload] Iniciando: {titulo}")

    tamanho = os.path.getsize(caminho_video)
    tamanho_mb = tamanho / (1024 * 1024)
    if tamanho_mb > 287:
        print(f"  [ERRO] Vídeo muito grande ({tamanho_mb:.1f} MB). Limite: 287 MB")
        return None

    chunk_size = min(tamanho, MAX_CHUNK)
    total_chunk_count = (tamanho + chunk_size - 1) // chunk_size
    caption = _montar_titulo(titulo, descricao, tags)
    privacy = privacy_level or TIKTOK_PRIVACY

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
    }
    init_body = {
        "post_info": {
            "title": caption,
            "privacy_level": privacy,
            "disable_complement": True,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "SOURCE_FILE_UPLOAD",
            "video_size": tamanho,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunk_count,
        },
    }

    try:
        resp = requests.post(
            f"{API_BASE}/post/publish/video/init/",
            headers=headers,
            json=init_body,
            timeout=30,
        )
        data = resp.json()
    except Exception as e:
        print(f"  [ERRO] init falhou: {e}")
        return None

    if data.get("error", {}).get("code") != "ok":
        print(f"  [ERRO] init rejeitado: {data}")
        return None

    publish_id = data["data"]["publish_id"]
    upload_url = data["data"]["upload_url"]
    print(f"  [TT Upload] publish_id: {publish_id}")

    # Upload dos chunks (mesma upload_url, com Content-Range)
    enviados = 0
    chunk_index = 0
    try:
        with open(caminho_video, "rb") as f:
            while enviados < tamanho:
                chunk = f.read(chunk_size)
                cl = len(chunk)
                put_headers = {
                    "Content-Range": f"bytes {enviados}-{enviados + cl - 1}/{tamanho}",
                    "Content-Length": str(cl),
                }
                put_resp = requests.put(
                    upload_url,
                    headers=put_headers,
                    data=chunk,
                    timeout=600,
                )
                if put_resp.status_code >= 300:
                    print(f"  [ERRO] chunk {chunk_index} ({put_resp.status_code}): {put_resp.text[:300]}")
                    return None
                enviados += cl
                chunk_index += 1
                print(f"  [TT Upload] chunk {chunk_index}/{total_chunk_count} enviado")
    except Exception as e:
        print(f"  [ERRO] upload de chunk falhou: {e}")
        return None

    # Publicação é automática após o upload; checamos o status final.
    status = _checar_status(token, publish_id)
    if status == "FAILED":
        print("  [ERRO] TikTok processou e rejeitou o vídeo.")
        return None

    print(f"  [TT Upload] Vídeo publicado! publish_id: {publish_id}")
    return publish_id


def _checar_status(token, publish_id, max_tentativas=60):
    url = f"{API_BASE}/post/publish/status/fetch/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
    }
    for tentativa in range(max_tentativas):
        try:
            resp = requests.post(
                url,
                headers=headers,
                json={"publish_id": publish_id},
                timeout=15,
            )
            data = resp.json()
            status = data.get("data", {}).get("status", "")
            if status in ("PROCESSING_DOWNLOAD", "PROCESSING_UPLOAD", "SEND_TO_USER_INBOX"):
                if tentativa % 5 == 0:
                    print(f"  [TT Upload] Processando... ({status})")
                time.sleep(5)
                continue
            if status == "PUBLISH_COMPLETE":
                return status
            return status or "UNKNOWN"
        except Exception:
            time.sleep(5)
    print("  [TT Upload] Timeout checando status (upload pode ter sido aceito).")
    return "TIMEOUT"
