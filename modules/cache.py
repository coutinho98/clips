import os
import json
from config import PASTA_TEMP


CACHE_DIR = os.path.join(PASTA_TEMP, "cache")


def _cache_path(job_id):
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{job_id}.json")


def salvar_cache(job_id, etapa, dados):
    path = _cache_path(job_id)
    cache = {}

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            cache = json.load(f)

    cache[etapa] = dados
    cache["etapa_atual"] = etapa

    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    return path


def carregar_cache(job_id):
    path = _cache_path(job_id)
    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def tem_etapa(job_id, etapa):
    cache = carregar_cache(job_id)
    if cache is None:
        return False
    return etapa in cache


def obter_etapa(job_id, etapa):
    cache = carregar_cache(job_id)
    if cache is None:
        return None
    return cache.get(etapa)


def limpar_cache(job_id):
    path = _cache_path(job_id)
    if os.path.exists(path):
        os.remove(path)


def gerar_job_id(url=None, caminho_video=None):
    if url:
        return url.split("/")[-1][:30].replace("=", "").replace("?", "").replace("&", "")
    if caminho_video:
        nome = os.path.basename(caminho_video)
        return nome.replace(".", "_").replace(" ", "_")[:30]
    return "unknown"


def lista_etapas_concluidas(job_id):
    cache = carregar_cache(job_id)
    if cache is None:
        return []
    return [k for k in cache.keys() if k != "etapa_atual"]


ETAPAS = [
    "download",
    "audio",
    "transcricao",
    "picos_audio",
    "highlights",
    "cortes",
]
