import os
import time

import requests

from config import TIKTOK_ACCESS_TOKEN, TIKTOK_PRIVACY

API_BASE = "https://open.tiktokapis.com/v2"

# Limite de 1 chunk: TikTok exige chunk_size <= video_size e igual p/ todos chunks.
MAX_CHUNK = 64 * 1024 * 1024  # 64 MB


def _montar_titulo(titulo, descricao, tags):
    partes = [titulo or ""]
    if descricao:
        partes.append(descricao)
    if tags:
        partes.append(" ".join(f"#{t}" for t in tags if t))
    caption = "\n\n".join(p for p in partes if p)
    return caption[:150]


def upload_video(caminho_video, titulo, descricao="", tags=None,
                 access_token=None, privacy_level=None):
    """Faz upload direto (Direct Post) do vídeo no TikTok. Retorna publish_id ou None."""
    if not os.path.exists(caminho_video):
        print(f"  [ERRO] Vídeo não encontrado: {caminho_video}")
        return None

    token = access_token or TIKTOK_ACCESS_TOKEN
    if not token:
        print("  [ERRO] TIKTOK_ACCESS_TOKEN não configurado no .env")
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
