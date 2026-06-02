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

WHISPER_METODO = os.getenv("WHISPER_METODO", "local")
WHISPER_MODELO = os.getenv("WHISPER_MODELO", "medium")
LIVE_CLIPPER_MAX_CORTES = int(os.getenv("LIVE_CLIPPER_MAX_CORTES", "5"))
LIVE_CLIPPER_DURACAO_MIN = int(os.getenv("LIVE_CLIPPER_DURACAO_MIN", "30"))
LIVE_CLIPPER_DURACAO_MAX = int(os.getenv("LIVE_CLIPPER_DURACAO_MAX", "90"))
LIVE_CLIPPER_CROP_VERTICAL = os.getenv("LIVE_CLIPPER_CROP_VERTICAL", "true").lower() == "true"
LIVE_CLIPPER_LEGENDAS = os.getenv("LIVE_CLIPPER_LEGENDAS", "true").lower() == "true"
LIVE_CLIPPER_ESTILO_LEGENDAS = os.getenv("LIVE_CLIPPER_ESTILO_LEGENDAS", "neon")
LIVE_CLIPPER_DETECTAR_POR = os.getenv("LIVE_CLIPPER_DETECTAR_POR", "ia")

os.makedirs(PASTA_TEMP, exist_ok=True)
os.makedirs(PASTA_OUTPUT, exist_ok=True)
