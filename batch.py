import sys
import os
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from config import PASTA_OUTPUT
from modules.script_generator import gerar_roteiro
from modules.tts_engine import gerar_narracao_partes
from modules.image_fetcher import buscar_imagens_para_roteiro
from modules.video_assembler import montar_video


def gerar_multiplos(quantidade=5):
    print(f"Gerando {quantidade} vídeos em lote...\n")

    resultados = []
    for i in range(quantidade):
        print(f"\n--- Vídeo {i+1}/{quantidade} ---")
        try:
            dados = gerar_roteiro()
            audios = gerar_narracao_partes(dados["roteiro"])
            imagens = buscar_imagens_para_roteiro(dados["termos_busca_imagem"])

            titulo_arquivo = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{dados['titulo'][:30]}"
            video_path = montar_video(imagens, audios, titulo_arquivo)

            meta_path = os.path.join(PASTA_OUTPUT, f"{titulo_arquivo}_meta.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({
                    "titulo": dados["titulo"],
                    "descricao": dados["descricao"],
                    "tags": dados["tags"],
                    "video": video_path,
                }, f, ensure_ascii=False, indent=2)

            resultados.append({"titulo": dados["titulo"], "video": video_path, "status": "ok"})
            print(f"  OK: {dados['titulo']}")
        except Exception as e:
            resultados.append({"status": "erro", "erro": str(e)})
            print(f"  ERRO: {e}")

    print("\n" + "=" * 50)
    print("RESUMO DO LOTE:")
    for r in resultados:
        status = r.get("status")
        if status == "ok":
            print(f"  [OK] {r['titulo']}")
        else:
            print(f"  [ERRO] {r['erro']}")
    print("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dark Channel Bot - Geração em lote")
    parser.add_argument("-n", "--quantidade", type=int, default=5, help="Quantidade de vídeos")
    args = parser.parse_args()

    gerar_multiplos(args.quantidade)
