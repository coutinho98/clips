import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "").strip() or None
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
OPENAI_TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "whisper-1")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
NICHO = os.getenv("NICHO", "curiosidades_sombrias")
VOZ = os.getenv("VOZ", "pt-BR-AntonioNeural")
QUANTIDADE_IMAGENS = int(os.getenv("QUANTIDADE_IMAGENS", "6"))
DURACAO_IMAGEM = int(os.getenv("DURACAO_IMAGEM_SEGUNDOS", "8"))
RESOLUCAO = tuple(int(x) for x in os.getenv("RESOLUCAO", "1080x1920").split("x"))

PASTA_TEMP = os.path.join(os.path.dirname(__file__), "temp")
PASTA_OUTPUT = os.path.join(os.path.dirname(__file__), "output")
PASTA_ASSETS = os.path.join(os.path.dirname(__file__), "assets")

WHISPER_METODO = os.getenv("WHISPER_METODO", "local")
WHISPER_MODELO = os.getenv("WHISPER_MODELO", "medium")
LIVE_CLIPPER_MAX_CORTES = int(os.getenv("LIVE_CLIPPER_MAX_CORTES", "5"))
LIVE_CLIPPER_DURACAO_MIN = int(os.getenv("LIVE_CLIPPER_DURACAO_MIN", "30"))
LIVE_CLIPPER_DURACAO_MAX = int(os.getenv("LIVE_CLIPPER_DURACAO_MAX", "90"))
LIVE_CLIPPER_CROP_VERTICAL = os.getenv("LIVE_CLIPPER_CROP_VERTICAL", "true").lower() == "true"
LIVE_CLIPPER_LEGENDAS = os.getenv("LIVE_CLIPPER_LEGENDAS", "true").lower() == "true"
LIVE_CLIPPER_ESTILO_LEGENDAS = os.getenv("LIVE_CLIPPER_ESTILO_LEGENDAS", "neon")
LIVE_CLIPPER_DETECTAR_POR = os.getenv("LIVE_CLIPPER_DETECTAR_POR", "ia")


def criar_cliente_openai():
    from openai import OpenAI

    kwargs = {}
    if OPENAI_API_KEY:
        kwargs["api_key"] = OPENAI_API_KEY
    if OPENAI_BASE_URL:
        kwargs["base_url"] = OPENAI_BASE_URL.rstrip("/")
    return OpenAI(**kwargs)


def nome_provedor_openai():
    return "OpenAI-compatible" if OPENAI_BASE_URL else "OpenAI"

os.makedirs(PASTA_TEMP, exist_ok=True)
os.makedirs(PASTA_OUTPUT, exist_ok=True)
