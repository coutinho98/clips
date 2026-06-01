import os
import hashlib
import requests
import random
from config import PEXELS_API_KEY, PASTA_TEMP, RESOLUCAO


def buscar_imagens_pexels(termo, quantidade=2, indice_global=0):
    if not PEXELS_API_KEY or PEXELS_API_KEY.startswith("sua"):
        print(f"    [!] Sem PEXELS_API_KEY - usando placeholders")
        return _gerar_imagens_placeholder(termo, quantidade, indice_global)

    headers = {"Authorization": PEXELS_API_KEY}

    try:
        params = {"query": termo, "per_page": quantidade, "orientation": "portrait"}
        response = requests.get(
            "https://api.pexels.com/v1/search",
            headers=headers,
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        fotos = response.json().get("photos", [])

        if not fotos:
            params2 = {"query": termo, "per_page": quantidade}
            response = requests.get(
                "https://api.pexels.com/v1/search",
                headers=headers,
                params=params2,
                timeout=15,
            )
            fotos = response.json().get("photos", [])

        caminhos = []
        for i, foto in enumerate(fotos[:quantidade]):
            url = foto["src"]["portrait"]
            if RESOLUCAO[0] > 1080:
                url = foto["src"]["original"]
            id_hash = hashlib.md5(foto["url"].encode()).hexdigest()[:8]
            caminho = f"{PASTA_TEMP}/img_{id_hash}.jpg"
            _baixar(url, caminho)
            print(f"    Baixado: {caminho} ({os.path.getsize(caminho) // 1024} KB)")
            caminhos.append(caminho)

        return caminhos if caminhos else _gerar_imagens_placeholder(termo, quantidade, indice_global)
    except Exception as e:
        print(f"    [ERRO Pexels] {e}")
        return _gerar_imagens_placeholder(termo, quantidade, indice_global)


def _baixar(url, caminho):
    r = requests.get(url, stream=True, timeout=30)
    with open(caminho, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)


def _gerar_imagens_placeholder(termo, quantidade, indice_global=0):
    from PIL import Image, ImageDraw, ImageFont

    caminhos = []
    cores = [
        (10, 10, 30), (20, 5, 15), (5, 15, 25), (25, 10, 10),
        (10, 20, 10), (15, 5, 25), (5, 20, 20), (25, 15, 5),
    ]

    for i in range(quantidade):
        cor = cores[(indice_global + i) % len(cores)]
        img = Image.new("RGB", RESOLUCAO, color=cor)
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
        except Exception:
            font = ImageFont.load_default()

        texto = termo.upper()
        bbox = draw.textbbox((0, 0), texto, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        cx = (RESOLUCAO[0] - tw) // 2
        cy = (RESOLUCAO[1] - th) // 2
        draw.text((cx + 3, cy + 3), texto, fill=(0, 0, 0), font=font)
        draw.text((cx, cy), texto, fill=(220, 220, 220), font=font)

        caminho = f"{PASTA_TEMP}/img_placeholder_{indice_global + i}_{termo.replace(' ', '_')[:15]}.jpg"
        img.save(caminho, quality=90)
        caminhos.append(caminho)

    return caminhos


def buscar_imagens_para_roteiro(termos_busca, imagens_por_termo=2):
    todas_imagens = []
    for idx, termo in enumerate(termos_busca):
        print(f"    [{idx+1}/{len(termos_busca)}] Buscando: {termo}")
        imgs = buscar_imagens_pexels(termo, imagens_por_termo, idx)
        todas_imagens.extend(imgs)
    print(f"    Total: {len(todas_imagens)} imagens")
    return todas_imagens
