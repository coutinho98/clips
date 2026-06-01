import sys
import os
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from config import PASTA_OUTPUT, PASTA_TEMP, OPENAI_API_KEY
from modules.cache import (
    salvar_cache, tem_etapa, obter_etapa, limpar_cache,
    gerar_job_id, lista_etapas_concluidas, ETAPAS,
)
from modules.live_downloader import baixar_live
from modules.audio_analyzer import extrair_audio_do_video, detectar_momentos_interessantes
from modules.transcriber import transcrever_audio, salvar_transcricao, gerar_srt
from modules.heuristic_detector import detectar_highlights_heuristico
from modules.clip_extractor import extrair_multiplos_cortes, gerar_preview


def processar_live(
    url=None,
    caminho_video=None,
    max_cortes=12,
    metodo_transcricao="local",
    modelo_whisper="base",
    crop_vertical=True,
    legendas=False,
    estilo_legendas="neon",
    detectar_por="ia",
    bg_music=None,
    bg_music_volume=0.15,
    preview=False,
    upload_ig=False,
    resume=True,
):
    print("=" * 55)
    print("  DARK CHANNEL - Cortes Automaticos (Reels)")
    print("=" * 55)

    if not url and not caminho_video:
        print("\n  [ERRO] Forneça uma URL ou caminho para o video da live.")
        print("  Uso: python live_clipper.py --url <URL>")
        print("       python live_clipper.py --video <caminho>")
        return

    job_id = gerar_job_id(url, caminho_video)
    print(f"  Job ID: {job_id}")

    if resume:
        concluidas = lista_etapas_concluidas(job_id)
        if concluidas:
            print(f"  Etapas em cache: {', '.join(concluidas)}")

    if bg_music and os.path.exists(bg_music):
        print(f"  Background music: {bg_music}")

    # --- ETAPA 1: DOWNLOAD ---
    if resume and tem_etapa(job_id, "download"):
        caminho_video = obter_etapa(job_id, "download")["caminho"]
        print(f"\n[1/6] [CACHE] Video ja baixado: {caminho_video}")
    else:
        if url and not caminho_video:
            print(f"\n[1/6] Baixando live (melhor qualidade)...")
            caminho_video = baixar_live(url)
            if not caminho_video:
                print("  [ERRO] Falha ao baixar a live.")
                return
        else:
            print(f"\n[1/6] Usando video local: {caminho_video}")

        if resume:
            salvar_cache(job_id, "download", {"caminho": caminho_video, "url": url})

    # --- ETAPA 1.5: INFO ---
    duracao_video = _obter_duracao_video(caminho_video)
    if duracao_video > 0:
        print(f"  Duracao: {duracao_video / 60:.1f} min | Max cortes: {max_cortes}")

    # --- ETAPA 2: EXTRAIR AUDIO ---
    if resume and tem_etapa(job_id, "audio"):
        caminho_audio = obter_etapa(job_id, "audio")["caminho"]
        print(f"\n[2/6] [CACHE] Audio ja extraido: {caminho_audio}")
    else:
        print(f"\n[2/6] Extraindo audio do video...")
        caminho_audio = extrair_audio_do_video(caminho_video)
        if not caminho_audio:
            print("  [ERRO] Falha ao extrair audio.")
            return
        if resume:
            salvar_cache(job_id, "audio", {"caminho": caminho_audio})

    # --- ETAPA 3: TRANSCREVER ---
    if resume and tem_etapa(job_id, "transcricao"):
        transc_path = obter_etapa(job_id, "transcricao")["caminho"]
        print(f"\n[3/6] [CACHE] Transcricao ja existe: {transc_path}")
        with open(transc_path, "r", encoding="utf-8") as f:
            transcricao = json.load(f)
    else:
        print(f"\n[3/6] Transcrevendo audio (metodo: {metodo_transcricao})...")
        transcricao = transcrever_audio(
            caminho_audio,
            metodo=metodo_transcricao,
            modelo=modelo_whisper,
        )
        if not transcricao:
            print("  [ERRO] Falha na transcricao.")
            return
        transc_path = salvar_transcricao(transcricao)
        gerar_srt(transcricao["segmentos"])
        if resume:
            salvar_cache(job_id, "transcricao", {"caminho": transc_path})

    # --- ETAPA 4: ANALISAR AUDIO ---
    if resume and tem_etapa(job_id, "picos_audio"):
        momentos_audio = obter_etapa(job_id, "picos_audio")["picos"]
        print(f"\n[4/6] [CACHE] {len(momentos_audio)} picos de audio")
    else:
        print(f"\n[4/6] Analisando audio para detectar picos...")
        momentos_audio = detectar_momentos_interessantes(caminho_audio)
        if resume:
            salvar_cache(job_id, "picos_audio", {"picos": momentos_audio})

    # --- ETAPA 5: DETECTAR HIGHLIGHTS ---
    if resume and tem_etapa(job_id, "highlights"):
        cortes = obter_etapa(job_id, "highlights")["cortes"]
        print(f"\n[5/6] [CACHE] {len(cortes)} cortes detectados")
    else:
        print(f"\n[5/6] Detectando melhores momentos ({detectar_por})...")
        cortes = []

        if detectar_por in ("heuristicas", "ambos"):
            print("  Analisando com heuristicas (100% gratis)...")
            cortes_heur = detectar_highlights_heuristico(
                transcricao, momentos_audio, max_cortes=max_cortes,
            )
            cortes.extend(cortes_heur)

        if detectar_por in ("ia", "ambos") and OPENAI_API_KEY:
            try:
                from modules.highlights_detector import detectar_highlights, detectar_highlights_por_audio
                print("  Analisando com IA (GPT)...")
                cortes_ia = detectar_highlights(
                    transcricao, picos_audio=momentos_audio, max_cortes=max_cortes,
                )
                cortes.extend(cortes_ia)
            except Exception as e:
                print(f"  [AVISO] IA falhou: {e}")

        if detectar_por == "audio":
            from modules.highlights_detector import detectar_highlights_por_audio
            cortes_audio = detectar_highlights_por_audio(
                momentos_audio, transcricao, max_cortes=max_cortes,
            )
            cortes.extend(cortes_audio)

        cortes = _remover_duplicatas(cortes)
        cortes = sorted(cortes, key=lambda x: x.get("score_viral") or 0, reverse=True)
        cortes = cortes[:max_cortes]

        if resume:
            salvar_cache(job_id, "highlights", {"cortes": cortes})

    if not cortes:
        print("  [ERRO] Nenhum momento interessante detectado.")
        return

    print(f"\n  {len(cortes)} cortes selecionados:")
    for i, c in enumerate(cortes, 1):
        score = c.get("score_viral", "?")
        titulo = c.get("titulo", "sem titulo")
        hook = c.get("hook_text", "")
        duracao = c.get("fim_seg", 0) - c.get("inicio_seg", 0)
        print(f"    {i}. [{score}/10] {titulo} ({duracao:.0f}s)")
        print(f"       Hook: {hook}")

    # --- PREVIEW ---
    if preview:
        print(f"\n  Gerando previews (sem encodar)...")
        previews = gerar_preview(caminho_video, cortes, crop_vertical=crop_vertical)

        preview_path = os.path.join(PASTA_OUTPUT, f"preview_{job_id}.json")
        with open(preview_path, "w", encoding="utf-8") as f:
            json.dump(previews, f, ensure_ascii=False, indent=2)

        print(f"\n  Previews gerados: {preview_path}")
        print("  Use sem --preview para gerar os videos.")
        return

    # --- ETAPA 6: EXTRAIR CORTES ---
    print(f"\n[6/6] Extraindo {len(cortes)} cortes (formato Reels)...")
    resultados = extrair_multiplos_cortes(
        caminho_video,
        cortes,
        crop_vertical=crop_vertical,
        adicionar_legenda=legendas,
        transcricao=transcricao if legendas else None,
        bg_music_path=bg_music,
        bg_music_volume=bg_music_volume,
    )

    if resume:
        salvar_cache(job_id, "cortes", {
            "resultados": [r for r in resultados if r["status"] == "ok"]
        })

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    relatorio_path = os.path.join(PASTA_OUTPUT, f"relatorio_cortes_{timestamp}.json")
    with open(relatorio_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            "video_origem": caminho_video,
            "total_cortes": len(resultados),
            "sucesso": sum(1 for r in resultados if r["status"] == "ok"),
            "erros": sum(1 for r in resultados if r["status"] == "erro"),
            "cortes": resultados,
        }, f, ensure_ascii=False, indent=2)

    metadata_path = os.path.join(PASTA_OUTPUT, f"reels_metadata_{timestamp}.txt")
    with open(metadata_path, "w", encoding="utf-8") as f:
        f.write("METADATA PRONTA PARA REELS\n")
        f.write("=" * 40 + "\n\n")
        for r in resultados:
            if r["status"] == "ok":
                f.write(f"VIDEO: {r['caminho']}\n")
                f.write(f"TITULO: {r['titulo']}\n")
                desc = r.get("descricao", "")
                if desc:
                    f.write(f"DESCRICAO: {desc}\n")
                tags = r.get("tags", [])
                if tags:
                    f.write(f"TAGS: {', '.join(tags)}\n")
                f.write(f"DURACAO: {r.get('duracao', 0):.0f}s\n")
                f.write("-" * 40 + "\n\n")

    # --- UPLOAD INSTAGRAM ---
    if upload_ig:
        from modules.instagram_uploader import upload_multiplos
        ig_user_id = os.getenv("IG_USER_ID")
        ig_token = os.getenv("IG_ACCESS_TOKEN")
        if ig_user_id and ig_token:
            print(f"\n  Enviando para Instagram...")
            uploads = upload_multiplos(resultados, ig_user_id, ig_token)
            for u in uploads:
                print(f"  [{'OK' if u['status'] == 'ok' else 'ERRO'}] {u['titulo']}")

    print("\n" + "=" * 55)
    print("  RESULTADO FINAL - CORTES PARA REELS")
    print("=" * 55)

    for r in resultados:
        if r["status"] == "ok":
            tamanho = os.path.getsize(r["caminho"]) / (1024 * 1024)
            duracao = r.get("duracao", 0)
            print(f"\n  [OK] {r['titulo']} ({duracao:.0f}s / {tamanho:.1f} MB)")
            print(f"       {r['caminho']}")
        else:
            print(f"\n  [ERRO] {r['titulo']}: {r.get('erro', 'desconhecido')}")

    print(f"\n  Relatorio: {relatorio_path}")
    print(f"  Metadata:  {metadata_path}")
    print("=" * 55)


def processar_batch(arquivo_urls, max_cortes=5, **kwargs):
    if not os.path.exists(arquivo_urls):
        print(f"  [ERRO] Arquivo nao encontrado: {arquivo_urls}")
        return

    with open(arquivo_urls, "r") as f:
        urls = [linha.strip() for linha in f if linha.strip() and not linha.startswith("#")]

    if not urls:
        print("  [ERRO] Nenhuma URL no arquivo")
        return

    print(f"\n  BATCH: {len(urls)} videos para processar")
    print("=" * 55)

    resultados_batch = []

    for i, url in enumerate(urls, 1):
        print(f"\n{'=' * 55}")
        print(f"  VIDEO {i}/{len(urls)}: {url[:60]}...")
        print("=" * 55)

        try:
            processar_live(url=url, max_cortes=max_cortes, **kwargs)
            resultados_batch.append({"url": url, "status": "ok"})
        except Exception as e:
            print(f"  [ERRO BATCH] {url}: {e}")
            resultados_batch.append({"url": url, "status": "erro", "erro": str(e)})

    print("\n" + "=" * 55)
    print("  RESUMO DO BATCH")
    print("=" * 55)
    for r in resultados_batch:
        status = "[OK]" if r["status"] == "ok" else "[ERRO]"
        print(f"  {status} {r['url'][:60]}...")
    ok = sum(1 for r in resultados_batch if r["status"] == "ok")
    print(f"\n  Total: {ok}/{len(resultados_batch)} processados com sucesso")
    print("=" * 55)


def _obter_duracao_video(caminho_video):
    try:
        import subprocess
        resultado = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", caminho_video],
            capture_output=True, text=True, timeout=30,
        )
        return float(resultado.stdout.strip())
    except Exception:
        return 0


def _remover_duplicatas(cortes, distancia_min=20):
    if not cortes:
        return cortes

    vistos = []
    unicos = []

    for c in cortes:
        inicio = c.get("inicio_seg", 0)
        duplicado = False
        for v in vistos:
            if abs(inicio - v) < distancia_min:
                duplicado = True
                break
        if not duplicado:
            vistos.append(inicio)
            unicos.append(c)

    return unicos


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Dark Channel - Cortes Automaticos de Lives para Reels"
    )

    parser.add_argument("--url", type=str, help="URL da live (Twitch, YouTube, etc)")
    parser.add_argument("--video", type=str, help="Caminho para arquivo de video local")
    parser.add_argument("--batch", type=str, help="Arquivo txt com lista de URLs")
    parser.add_argument("-n", "--max-cortes", type=int, default=12, help="Numero maximo de cortes (default: 12)")
    parser.add_argument("--transcricao", type=str, default="local",
                        choices=["local", "api"], help="Metodo de transcricao (default: local)")
    parser.add_argument("--modelo-whisper", type=str, default="base",
                        choices=["tiny", "base", "small", "medium", "large"],
                        help="Modelo Whisper (default: base)")
    parser.add_argument("--sem-crop", action="store_true", help="Desativar crop vertical 9:16")
    parser.add_argument("--legendas", action="store_true", help="Ativar legendas")
    parser.add_argument("--estilo-legendas", type=str, default="neon",
                        choices=["neon", "karaoke", "box", "sombra"],
                        help="Estilo das legendas (default: neon)")
    parser.add_argument("--detectar-por", type=str, default="ia",
                        choices=["heuristicas", "ia", "audio", "ambos"],
                        help="Metodo de deteccao (default: ia - usa GPT pra entender o conteudo)")
    parser.add_argument("--bg-music", type=str, help="Caminho para musica de fundo")
    parser.add_argument("--bg-music-volume", type=float, default=0.15,
                        help="Volume da musica de fundo (0.0 a 1.0, default: 0.15)")
    parser.add_argument("--preview", action="store_true",
                        help="Gerar so thumbnails (sem encodar video)")
    parser.add_argument("--upload", action="store_true", help="Auto-upload Instagram")
    parser.add_argument("--no-cache", action="store_true", help="Desativar cache/resume")

    args = parser.parse_args()

    kwargs = {
        "max_cortes": args.max_cortes,
        "metodo_transcricao": args.transcricao,
        "modelo_whisper": args.modelo_whisper,
        "crop_vertical": not args.sem_crop,
        "legendas": args.legendas,
        "estilo_legendas": args.estilo_legendas,
        "detectar_por": args.detectar_por,
        "bg_music": args.bg_music,
        "bg_music_volume": args.bg_music_volume,
        "preview": args.preview,
        "upload_ig": args.upload,
        "resume": not args.no_cache,
    }

    if args.batch:
        processar_batch(args.batch, **kwargs)
    elif args.url or args.video:
        processar_live(
            url=args.url,
            caminho_video=args.video,
            **kwargs,
        )
    else:
        parser.print_help()
