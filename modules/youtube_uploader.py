import os

from config import (
    YOUTUBE_CLIENT_SECRET,
    YOUTUBE_TOKEN,
    YOUTUBE_CATEGORIA,
    YOUTUBE_PRIVACY,
)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _load_credentials():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    token_path = YOUTUBE_TOKEN
    creds = None
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(token_path, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
            except Exception as e:
                print(f"  [ERRO] Falha ao renovar token YouTube: {e}")
                return None
        else:
            print("  [ERRO] YouTube não autenticado.")
            print("  Rode uma vez: python postar.py --auth-youtube")
            return None

    return creds


def autenticar():
    """Fluxo OAuth interativo (uma única vez). Abre o navegador."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not os.path.exists(YOUTUBE_CLIENT_SECRET):
        print(f"  [ERRO] {YOUTUBE_CLIENT_SECRET} não encontrado.")
        print("  Baixe o OAuth Client ID em:")
        print("  https://console.cloud.google.com/apis/credentials")
        print("  Tipo: 'Desktop app'. Cole o JSON em secrets/client_secret.json")
        print("  Habilite 'YouTube Data API v3' no projeto.")
        return False

    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    flow = InstalledAppFlow.from_client_secrets_file(YOUTUBE_CLIENT_SECRET, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(YOUTUBE_TOKEN, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

    print(f"  [OK] Token salvo em {YOUTUBE_TOKEN}")
    return True


def upload_short(caminho_video, titulo, descricao="", tags=None,
                 categoria=None, privacy=None):
    """Faz upload de um vídeo como Short (vertical). Retorna o video_id ou None."""
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError

    if not os.path.exists(caminho_video):
        print(f"  [ERRO] Vídeo não encontrado: {caminho_video}")
        return None

    creds = _load_credentials()
    if not creds:
        return None

    print(f"  [YT Upload] Iniciando: {titulo}")

    tags = list(tags or [])
    tags_lower = [t.lower() for t in tags]
    if "shorts" not in tags_lower:
        tags.append("shorts")

    tamanho_mb = os.path.getsize(caminho_video) / (1024 * 1024)
    if tamanho_mb > 256:
        print(f"  [ERRO] Vídeo muito grande ({tamanho_mb:.1f} MB). Limite: 256 MB")
        return None

    body = {
        "snippet": {
            "title": (titulo or "Short")[:100],
            "description": (descricao or "")[:5000],
            "tags": tags,
            "categoryId": categoria or YOUTUBE_CATEGORIA,
        },
        "status": {
            "privacyStatus": privacy or YOUTUBE_PRIVACY,
            "selfDeclaredMadeForKids": False,
        },
    }

    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    media = MediaFileUpload(caminho_video, chunksize=-1, resumable=True)

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    try:
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"  [YT Upload] Enviando... {int(status.progress() * 100)}%")

        video_id = response.get("id")
        if video_id:
            print(f"  [YT Upload] Short publicado! ID: {video_id}")
            print(f"  https://youtube.com/shorts/{video_id}")
            return video_id
        print(f"  [ERRO] Resposta sem ID: {response}")
        return None
    except HttpError as e:
        print(f"  [ERRO] YouTube API: {e}")
        return None
    except Exception as e:
        print(f"  [ERRO] Upload falhou: {e}")
        return None
