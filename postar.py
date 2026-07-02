import sys
import os
import json
import glob
import time
import shutil
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from config import (
    PASTA_FILA,
    PASTA_POSTADOS,
    PASTA_FALHADOS,
    PASTA_LOGS,
    POSTAR_PLATAFORMAS,
    POSTAR_MAX_RETRY,
)

VIDEO_EXTS = ("*.mp4", "*.mov", "*.mkv", "*.avi", "*.webm")
LOCK_FILE = os.path.join(PASTA_FILA, ".postando.lock")
LOG_FILE = os.path.join(PASTA_LOGS, "postagens.log")


def _log(linha):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[{ts}] {linha}"
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def _adquirir_lock():
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return False  # processo ainda rodando
        except (ValueError, ProcessLookupError, PermissionError):
            pass  # lock travado/zumbi -> assumir
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    return True


def _liberar_lock():
    try:
        os.remove(LOCK_FILE)
    except FileNotFoundError:
        pass


def _listar_videos():
    arquivos = []
    for ext in VIDEO_EXTS:
        arquivos.extend(glob.glob(os.path.join(PASTA_FILA, ext)))
    return sorted(
        arquivos,
        key=lambda p: (os.path.getmtime(p), p),
    )


def _carregar_meta(video_path):
    base = os.path.splitext(video_path)[0]
    meta_path = base + ".json"
    meta = {"titulo": "", "descricao": "", "tags": []}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta.update(json.load(f))
        except Exception as e:
            print(f"  [AVISO] meta inválida ({meta_path}): {e}")

    if not meta.get("titulo"):
        meta["titulo"] = os.path.splitext(os.path.basename(video_path))[0].replace("_", " ")
    meta.setdefault("tags", [])
    meta.setdefault("descricao", "")
    return meta


def _mover(video_path, destino_dir):
    os.makedirs(destino_dir, exist_ok=True)
    base = os.path.basename(video_path)
    novo_video = os.path.join(destino_dir, base)

    # evita sobrescrever
    i = 1
    raiz, ext = os.path.splitext(novo_video)
    while os.path.exists(novo_video):
        novo_video = f"{raiz}_{i}{ext}"
        i += 1

    shutil.move(video_path, novo_video)

    # leva junto meta (.json) e resultado (_resultado.json)
    base_sem_ext = os.path.splitext(video_path)[0]
    for extra in (base_sem_ext + ".json", base_sem_ext + "_resultado.json"):
        if os.path.exists(extra):
            shutil.move(extra, os.path.join(destino_dir, os.path.basename(extra)))
    return novo_video


def _postar_youtube(video_path, meta):
    from modules.youtube_uploader import upload_short
    return upload_short(
        caminho_video=video_path,
        titulo=meta.get("titulo"),
        descricao=meta.get("descricao", ""),
        tags=meta.get("tags", []),
    )


def _postar_tiktok(video_path, meta):
    from modules.tiktok_uploader import upload_video
    return upload_video(
        caminho_video=video_path,
        titulo=meta.get("titulo"),
        descricao=meta.get("descricao", ""),
        tags=meta.get("tags", []),
    )


POSTADORES = {
    "youtube": _postar_youtube,
    "tiktok": _postar_tiktok,
}


# --- Estado por vídeo/plataforma -------------------------------------------

def _state_path(video_path):
    return os.path.join(PASTA_FILA, "." + os.path.basename(video_path) + ".state.json")


def _ler_state(video_path):
    sp = _state_path(video_path)
    if os.path.exists(sp):
        try:
            with open(sp, encoding="utf-8") as f:
                s = json.load(f)
            s.setdefault("posts", {})
            s.setdefault("tentativas", {})
            return s
        except Exception:
            pass
    return {"posts": {}, "tentativas": {}}


def _salvar_state(video_path, state):
    with open(_state_path(video_path), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _limpar_state(video_path):
    try:
        os.remove(_state_path(video_path))
    except FileNotFoundError:
        pass


def _ja_postado(video_path, plataforma):
    return bool(_ler_state(video_path)["posts"].get(plataforma))


def _proximo_pendente(plataforma):
    for v in _listar_videos():
        if not _ja_postado(v, plataforma):
            return v
    return None


def _escrever_resultado(video_path, meta, state):
    with open(os.path.splitext(video_path)[0] + "_resultado.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "video": os.path.basename(video_path),
                "titulo": meta.get("titulo"),
                "posts": state.get("posts", {}),
                "tentativas": state.get("tentativas", {}),
                "data": datetime.now().isoformat(),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )


def _postar_em(plataforma, video_path, meta):
    postador = POSTADORES.get(plataforma)
    if not postador:
        _log(f"  [PULAR] plataforma desconhecida: {plataforma}")
        return None
    print(f"\n--- {plataforma.upper()} ---")
    try:
        ref = postador(video_path, meta)
    except Exception as e:
        print(f"  [ERRO] exceção em {plataforma}: {e}")
        ref = None
    if ref:
        _log(f"  [{plataforma}] OK -> {ref}")
    else:
        _log(f"  [{plataforma}] FALHOU")
    return ref


def main():
    parser = argparse.ArgumentParser(description="Posta vídeos da fila no YouTube + TikTok")
    parser.add_argument("--auth-youtube", action="store_true", help="Autenticação OAuth do YouTube (1ª vez, interativo)")
    parser.add_argument("--auth-tiktok", action="store_true", help="Autenticação OAuth do TikTok (1ª vez, interativo)")
    parser.add_argument("--plataformas", help="Plataforma(s) desta execução (ex: youtube). Default: todas")
    parser.add_argument("--um", action="store_true", help="Postar só 1 vídeo por plataforma e sair")
    parser.add_argument("--dry-run", action="store_true", help="Simular sem postar")
    args = parser.parse_args()

    if args.auth_youtube:
        from modules.youtube_uploader import autenticar
        ok = autenticar()
        sys.exit(0 if ok else 1)

    if args.auth_tiktok:
        from modules.tiktok_uploader import autenticar
        ok = autenticar()
        sys.exit(0 if ok else 1)

    alvo = (
        [p.strip().lower() for p in args.plataformas.split(",") if p.strip()]
        if args.plataformas else list(POSTAR_PLATAFORMAS)
    )
    alvo = [p for p in alvo if p in POSTADORES]

    if not alvo:
        print("Nenhuma plataforma válida.")
        sys.exit(0)

    _log(f"Iniciando job. Plataformas desta execução: {', '.join(alvo)}")

    if not _adquirir_lock():
        _log("Outro postar.py já está rodando. Saindo.")
        sys.exit(0)

    try:
        for plataforma in alvo:
            video = _proximo_pendente(plataforma)
            if not video:
                _log(f"Nenhum vídeo pendente para {plataforma}.")
                continue

            meta = _carregar_meta(video)
            _log(f">>> [{plataforma}] {os.path.basename(video)} | {meta['titulo']}")

            if args.dry_run:
                _log(f"  [DRY-RUN] pularia {plataforma}: {os.path.basename(video)}")
                if args.um:
                    break
                continue

            ref = _postar_em(plataforma, video, meta)

            state = _ler_state(video)
            if ref:
                state["posts"][plataforma] = ref
                state["tentativas"].pop(plataforma, None)
            else:
                state["tentativas"][plataforma] = state["tentativas"].get(plataforma, 0) + 1
            _salvar_state(video, state)
            _escrever_resultado(video, meta, state)

            tentativas_p = state["tentativas"].get(plataforma, 0)
            postado_p = state["posts"].get(plataforma)
            tudo_postado = all(state["posts"].get(p) for p in POSTAR_PLATAFORMAS)

            if not postado_p and tentativas_p >= POSTAR_MAX_RETRY:
                _log(f"Máximo de tentativas ({POSTAR_MAX_RETRY}) em {plataforma} -> falhados/")
                novo = _mover(video, PASTA_FALHADOS)
                _limpar_state(novo)
            elif tudo_postado:
                _log(f"Todos os posts concluídos ({', '.join(POSTAR_PLATAFORMAS)}) -> postados/")
                novo = _mover(video, PASTA_POSTADOS)
                _limpar_state(novo)

            if args.um:
                break
            time.sleep(2)

        _log("Job finalizado.")
    finally:
        _liberar_lock()


if __name__ == "__main__":
    main()
