import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from config import PASTA_OUTPUT, PASTA_TEMP
from modules.tts_engine import gerar_narracao_partes
from modules.image_fetcher import buscar_imagens_para_roteiro
from modules.video_assembler import montar_video


def _dividir_roteiro(texto):
    partes = []
    sentencas = texto.replace(". ", ".|").replace("! ", "!|").replace("? ", "?|").split("|")
    grupo = []
    for s in sentencas:
        s = s.strip()
        if not s:
            continue
        grupo.append(s)
        if len(grupo) >= 2:
            partes.append(" ".join(grupo))
            grupo = []
    if grupo:
        partes.append(" ".join(grupo))
    return partes


def main():
    roteiro_path = os.path.join(PASTA_TEMP, "roteiro.txt")

    if not os.path.exists(roteiro_path):
        print("=" * 50)
        print("  DARK CHANNEL BOT - Pipeline Automatizado")
        print("=" * 50)
        print(f"\n  Cole seu roteiro no arquivo: {roteiro_path}")
        print("  Depois rode este script novamente.\n")
        with open(roteiro_path, "w", encoding="utf-8") as f:
            f.write("TITULO: \n")
            f.write("DESCRICAO: \n")
            f.write("TAGS: \n")
            f.write("IMAGENS: \n")
            f.write("---\n")
            f.write("Cole o texto da narracao aqui...\n")
        return

    with open(roteiro_path, "r", encoding="utf-8") as f:
        conteudo = f.read()

    linhas = conteudo.strip().split("\n")
    titulo = ""
    descricao = ""
    tags = []
    termos_busca = []
    texto_roterio = []
    secao_roterio = False

    for linha in linhas:
        if linha.startswith("TITULO:"):
            titulo = linha.replace("TITULO:", "").strip()
        elif linha.startswith("DESCRICAO:"):
            descricao = linha.replace("DESCRICAO:", "").strip() or titulo
        elif linha.startswith("TAGS:"):
            tags_raw = linha.replace("TAGS:", "").strip()
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        elif linha.startswith("IMAGENS:"):
            imgs_raw = linha.replace("IMAGENS:", "").strip()
            termos_busca = [t.strip() for t in imgs_raw.split(",") if t.strip()]
        elif linha.strip() == "---":
            secao_roterio = True
        elif secao_roterio:
            texto_roterio.append(linha)

    roteiro_completo = " ".join(texto_roterio).strip()

    if not titulo or not roteiro_completo:
        print("[ERRO] Preencha o TITULO e o roteiro (depois do ---) no arquivo roteiro.txt")
        return

    if not termos_busca:
        termos_busca = [titulo]

    partes = _dividir_roteiro(roteiro_completo)

    print("=" * 50)
    print("  DARK CHANNEL BOT - Pipeline Automatizado")
    print("=" * 50)
    print(f"\n  Titulo: {titulo}")
    print(f"  Partes do roteiro: {len(partes)}")

    print(f"\n[1/3] Gerando narracao (TTS)... ({len(partes)} partes)")
    print("  Isso pode levar alguns minutos...")
    audios = gerar_narracao_partes(partes)
    print(f"  {len(audios)} arquivos de audio gerados com sucesso")

    if not audios:
        print("\n[ERRO] Nenhum audio foi gerado. Verifique sua conexao com a internet.")
        return

    print("\n[2/3] Buscando imagens...")
    imagens = buscar_imagens_para_roteiro(termos_busca)
    print(f"  {len(imagens)} imagens obtidas")

    print("\n[3/3] Montando video (isso demora um pouco)...")
    titulo_arquivo = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{titulo[:30]}"
    video_path = montar_video(imagens, audios, titulo_arquivo)

    meta_path = os.path.join(PASTA_OUTPUT, f"{titulo_arquivo}_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({
            "titulo": titulo,
            "descricao": descricao,
            "tags": tags,
            "roteiro": roteiro_completo,
            "video": video_path,
        }, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 50)
    print(f"  VIDEO GERADO: {video_path}")
    print(f"  METADADOS: {meta_path}")
    print("=" * 50)


if __name__ == "__main__":
    main()
