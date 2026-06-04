import os
import json
import requests
import time
from config import PASTA_OUTPUT, PASTA_TEMP


def upload_reel(caminho_video, titulo, descricao="", tags=None,
                ig_user_id=None, ig_access_token=None):
    if not ig_user_id or not ig_access_token:
        print("  [ERRO] IG_USER_ID e IG_ACCESS_TOKEN necessários")
        return None

    print(f"  Upload Instagram Reels: {titulo}")

    tamanho_mb = os.path.getsize(caminho_video) / (1024 * 1024)
    if tamanho_mb > 100:
        print(f"  [ERRO] Vídeo muito grande ({tamanho_mb:.1f} MB). Limite: 100 MB")
        return None

    caption = titulo
    if descricao:
        caption += f"\n\n{descricao}"
    if tags:
        tag_str = " ".join(f"#{t}" for t in tags if t)
        caption += f"\n\n{tag_str}"

    api_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"

    create_data = {
        "media_type": "REELS",
        "video_url": "",
        "caption": caption[:2200],
        "access_token": ig_access_token,
    }

    print("  [ERRO] Upload direto requer URL pública do vídeo.")
    print("  Use upload_reel_local() para upload via container.")

    return None


def upload_reel_local(caminho_video, titulo, descricao="", tags=None,
                       ig_user_id=None, ig_access_token=None):
    if not ig_user_id or not ig_access_token:
        print("  [ERRO] Configure IG_USER_ID e IG_ACCESS_TOKEN no .env")
        print("  Para obter:")
        print("  1. Crie um app em https://developers.facebook.com")
        print("  2. Ative Instagram Basic Display / Content Publishing")
        print("  3. Obtenha o token com instagram_manage_media permission")
        return None

    print(f"  [IG Upload] Iniciando: {titulo}")

    tamanho_mb = os.path.getsize(caminho_video) / (1024 * 1024)
    if tamanho_mb > 100:
        print(f"  [ERRO] Vídeo muito grande ({tamanho_mb:.1f} MB). Limite: 100 MB")
        return None

    caption = titulo
    if descricao:
        caption += f"\n\n{descricao}"
    if tags:
        tag_str = " ".join(f"#{t}" for t in tags if t)
        caption += f"\n\n{tag_str}"

    api_base = f"https://graph.facebook.com/v19.0/{ig_user_id}"

    try:
        print("  [IG Upload] Criando container...")
        resp = requests.post(
            f"{api_base}/media",
            data={
                "media_type": "REELS",
                "caption": caption[:2200],
                "access_token": ig_access_token,
            },
            timeout=30,
        )

        if resp.status_code != 200:
            print(f"  [ERRO] Falha ao criar container: {resp.text}")
            return None

        container_id = resp.json().get("id")
        print(f"  [IG Upload] Container criado: {container_id}")

        print("  [IG Upload] Verificando processamento...")
        max_checks = 60
        for check in range(max_checks):
            time.sleep(5)

            status_resp = requests.get(
                f"https://graph.facebook.com/v19.0/{container_id}",
                params={
                    "fields": "status_code,status",
                    "access_token": ig_access_token,
                },
                timeout=15,
            )

            if status_resp.status_code != 200:
                continue

            status = status_resp.json().get("status_code", "")
            if status == "FINISHED":
                break
            elif status == "ERROR":
                print(f"  [ERRO] Container falhou: {status_resp.json()}")
                return None
            else:
                print(f"  [IG Upload] Processando... ({check + 1}/{max_checks})")
        else:
            print("  [ERRO] Timeout ao processar container")
            return None

        print("  [IG Upload] Publicando Reel...")
        publish_resp = requests.post(
            f"{api_base}/media_publish",
            data={
                "creation_id": container_id,
                "access_token": ig_access_token,
            },
            timeout=30,
        )

        if publish_resp.status_code != 200:
            print(f"  [ERRO] Falha ao publicar: {publish_resp.text}")
            return None

        media_id = publish_resp.json().get("id")
        print(f"  [IG Upload] Reel publicado com sucesso! ID: {media_id}")
        return media_id

    except Exception as e:
        print(f"  [ERRO] Upload falhou: {e}")
        return None


def upload_multiplos(resultados, ig_user_id=None, ig_access_token=None):
    uploads = []

    for r in resultados:
        if r.get("status") != "ok":
            continue

        media_id = upload_reel_local(
            caminho_video=r["caminho"],
            titulo=r.get("titulo", ""),
            descricao=r.get("descricao", ""),
            tags=r.get("tags", []),
            ig_user_id=ig_user_id,
            ig_access_token=ig_access_token,
        )

        uploads.append({
            "titulo": r.get("titulo"),
            "media_id": media_id,
            "status": "ok" if media_id else "erro",
        })

    return uploads
