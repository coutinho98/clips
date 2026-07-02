import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
NICHO = os.getenv("NICHO", "curiosidades_sombrias")
VOZ = os.getenv("VOZ", "pt-BR-AntonioNeural")
QUANTIDADE_IMAGENS = int(os.getenv("QUANTIDADE_IMAGENS", "6"))
DURACAO_IMAGEM = int(os.getenv("DURACAO_IMAGEM_SEGUNDOS", "8"))
RESOLUCAO = tuple(int(x) for x in os.getenv("RESOLUCAO", "1080x1920").split("x"))

PASTA_TEMP = os.path.join(os.path.dirname(__file__), "temp")
PASTA_OUTPUT = os.path.join(os.path.dirname(__file__), "output")
PASTA_ASSETS = os.path.join(os.path.dirname(__file__), "assets")

PASTA_FILA = os.path.join(os.path.dirname(__file__), "fila")
PASTA_POSTADOS = os.path.join(PASTA_FILA, "postados")
PASTA_FALHADOS = os.path.join(PASTA_FILA, "falhados")
PASTA_LOGS = os.path.join(os.path.dirname(__file__), "logs")
PASTA_SECRETS = os.path.join(os.path.dirname(__file__), "secrets")

YOUTUBE_CLIENT_SECRET = os.getenv(
    "YOUTUBE_CLIENT_SECRET",
    os.path.join(PASTA_SECRETS, "client_secret.json"),
)
YOUTUBE_TOKEN = os.getenv(
    "YOUTUBE_TOKEN",
    os.path.join(PASTA_SECRETS, "youtube_token.json"),
)
YOUTUBE_CATEGORIA = os.getenv("YOUTUBE_CATEGORIA", "22")
YOUTUBE_PRIVACY = os.getenv("YOUTUBE_PRIVACY", "public")

TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN")
TIKTOK_PRIVACY = os.getenv("TIKTOK_PRIVACY", "PUBLIC_TO_EVERYONE")
TIKTOK_SCOPES = os.getenv("TIKTOK_SCOPES", "video.upload,user.info.basic")
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")
TIKTOK_REDIRECT_URI = os.getenv("TIKTOK_REDIRECT_URI", "http://localhost:9876/callback")
TIKTOK_TOKEN_PATH = os.path.join(PASTA_SECRETS, "tiktok_token.json")

POSTAR_PLATAFORMAS = [
    p.strip().lower()
    for p in os.getenv("POSTAR_PLATAFORMAS", "youtube,tiktok").split(",")
    if p.strip()
]
POSTAR_MAX_RETRY = int(os.getenv("POSTAR_MAX_RETRY", "3"))

WHISPER_METODO = os.getenv("WHISPER_METODO", "local")
WHISPER_MODELO = os.getenv("WHISPER_MODELO", "small")
WHISPER_INITIAL_PROMPT = os.getenv(
    "WHISPER_INITIAL_PROMPT",
    "Live de streaming, Twitch, YouTube. Linguagem informal brasileira com gírias: "
    "mano, véi, bicho, tá, né, bora, falou, cara, véio, pow, vish, rapaz, nossa, "
    "porra, caralho, foda, merda, cacete. Conversa de amigos, podcast, gameplay, "
    "reação, humor, zoeira. Palavras como tipo, sacou, beleza, trampo, pika, "
    "pá, mano, tchê, tiu, guri, maninho."
)
LIVE_CLIPPER_MAX_CORTES = int(os.getenv("LIVE_CLIPPER_MAX_CORTES", "5"))
LIVE_CLIPPER_DURACAO_MIN = int(os.getenv("LIVE_CLIPPER_DURACAO_MIN", "25"))
LIVE_CLIPPER_DURACAO_MAX = int(os.getenv("LIVE_CLIPPER_DURACAO_MAX", "45"))
LIVE_CLIPPER_CROP_VERTICAL = os.getenv("LIVE_CLIPPER_CROP_VERTICAL", "true").lower() == "true"
LIVE_CLIPPER_LEGENDAS = os.getenv("LIVE_CLIPPER_LEGENDAS", "true").lower() == "true"
LIVE_CLIPPER_ESTILO_LEGENDAS = os.getenv("LIVE_CLIPPER_ESTILO_LEGENDAS", "neon")
LIVE_CLIPPER_DETECTAR_POR = os.getenv("LIVE_CLIPPER_DETECTAR_POR", "ia")

WATERMARK_LOGO = os.getenv("WATERMARK_LOGO", os.path.join(os.path.dirname(__file__), "logo.png"))
WATERMARK_SIZE = int(os.getenv("WATERMARK_SIZE", "150"))
WATERMARK_OPACITY = float(os.getenv("WATERMARK_OPACITY", "0.8"))
WATERMARK_POS = os.getenv("WATERMARK_POS", "W-w-30:H-h-220")

os.makedirs(PASTA_TEMP, exist_ok=True)
os.makedirs(PASTA_OUTPUT, exist_ok=True)
os.makedirs(PASTA_FILA, exist_ok=True)
os.makedirs(PASTA_POSTADOS, exist_ok=True)
os.makedirs(PASTA_FALHADOS, exist_ok=True)
os.makedirs(PASTA_LOGS, exist_ok=True)
os.makedirs(PASTA_SECRETS, exist_ok=True)


def get_watermark():
    if WATERMARK_LOGO and os.path.exists(WATERMARK_LOGO):
        return {
            "path": WATERMARK_LOGO,
            "size": WATERMARK_SIZE,
            "opacity": WATERMARK_OPACITY,
            "pos": WATERMARK_POS,
        }
    return None
