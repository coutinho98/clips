import json
import os
import requests
from config import OPENAI_API_KEY

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_BIN = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ollama", "bin", "ollama")

CATEGORIAS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "momentos.json")


def _carregar_categorias():
    default = {
        "engraçado": {"palavras": ["kkk", "haha", "rindo", "engraçado"], "peso": 3},
        "sério": {"palavras": ["sério", "importante", "grave"], "peso": 3},
        "emocionante": {"palavras": ["chorar", "emocionante", "saudade"], "peso": 3},
    }
    if os.path.exists(CATEGORIAS_PATH):
        try:
            with open(CATEGORIAS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


CATEGORIAS = _carregar_categorias()

PROMPT_AVALIAR = """Voce e um editor de video viral. Analise o trecho abaixo e classifique que tipo de momento e.

Categorias: engracado, serio, emocionante, revelacao, polemico, opiniao_forte, surreal

Responda APENAS com JSON:
{"bom": true/false, "categoria": "tipo", "score_viral": 1-10, "titulo": "titulo curto", "hook_text": "FRASE REAL DO TRECHO", "motivo": "por que e bom"}

Se nao for interessante: {"bom": false, "categoria": "", "score_viral": 0, "titulo": "", "hook_text": "", "motivo": ""}"""


def _usar_ollama():
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _chamar_ollama(system_prompt, user_content):
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 500,
        }
    }
    resp = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=300)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _chamar_openai(system_prompt, user_content):
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    resposta = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.3,
        max_tokens=500,
    )
    return resposta.choices[0].message.content.strip()


def detectar_highlights(transcricao, picos_audio=None, max_cortes=5):
    segmentos = transcricao.get("segmentos", [])
    if not segmentos:
        print("  [ERRO] Nenhum segmento na transcricao")
        return []

    ollama_disponivel = _usar_ollama()
    if ollama_disponivel:
        print(f"  Usando Ollama local ({OLLAMA_MODEL})...")
    elif OPENAI_API_KEY:
        print(f"  Usando OpenAI GPT-4o-mini...")
    else:
        print(f"  [ERRO] Nem Ollama nem OpenAI disponiveis")
        return []

    candidatos = _gerar_candidatos(segmentos, picos_audio, max_cortes * 4)
    if not candidatos:
        print("  [ERRO] Nenhum candidato gerado")
        return []

    print(f"  {len(candidatos)} candidatos encontrados:")
    cats_count = {}
    for c in candidatos:
        cat = c.get("categoria", "?")
        cats_count[cat] = cats_count.get(cat, 0) + 1
    for cat, count in sorted(cats_count.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {count}")
    print(f"  Avaliando com IA...")

    avaliados = []
    for i, cand in enumerate(candidatos):
        texto = cand["texto"]
        min_i = int(cand["inicio_seg"] // 60)
        seg_i = int(cand["inicio_seg"] % 60)
        cat_preliminar = cand.get("categoria", "?")
        print(f"    [{i + 1}/{len(candidatos)}] {min_i:02d}:{seg_i:02d} ({cat_preliminar})...", end="", flush=True)

        try:
            conteudo = _chamar_ia(PROMPT_AVALIAR, texto, ollama_disponivel)
            resultado = _parsear_resposta_bruta(conteudo)
            if isinstance(resultado, list):
                resultado = resultado[0] if resultado else {}
            if not isinstance(resultado, dict):
                resultado = {}

            resultado["inicio_seg"] = cand["inicio_seg"]
            resultado["fim_seg"] = cand["fim_seg"]

            score = resultado.get("score_viral") or 0
            if resultado.get("bom", False) or score >= 5:
                resultado["tipo"] = resultado.get("categoria", cat_preliminar)
                resultado["tags"] = ["reels", "viral", "fyp", "shorts", "trending"]
                resultado["descricao"] = "#reels #viral #fyp #shorts #trending"
                if not resultado.get("hook_text"):
                    resultado["hook_text"] = _hook_do_texto(texto)
                if not resultado.get("titulo"):
                    resultado["titulo"] = texto[:40].strip() + "..."
                avaliados.append(resultado)
                print(f" OK ({score}/10)")
            else:
                print(f" descartado ({score}/10)")
        except Exception as e:
            print(f" ERRO: {e}")
            continue

    avaliados.sort(key=lambda x: x.get("score_viral") or 0, reverse=True)
    avaliados = _validar_e_corrigir(avaliados, segmentos)
    avaliados = avaliados[:max_cortes]

    print(f"\n  {len(avaliados)} cortes aprovados:")
    for c in avaliados:
        cat = c.get("tipo", "?")
        score = c.get("score_viral", "?")
        titulo = c.get("titulo", "?")
        print(f"    [{cat}] {score}/10 - {titulo}")

    return avaliados


def _gerar_candidatos(segmentos, picos_audio, max_candidatos):
    duracao_total = segmentos[-1]["fim"] - segmentos[0]["inicio"]
    candidatos = []
    usados = set()

    if picos_audio:
        for pico in picos_audio:
            centro = (pico["inicio_seg"] + pico["fim_seg"]) / 2.0
            inicio = max(0, centro - 45)
            fim = inicio + 60
            chave = int(inicio // 30)
            if chave in usados:
                continue
            usados.add(chave)
            texto = _texto_no_intervalo(segmentos, inicio, fim)
            if len(texto.split()) < 8:
                continue
            cat, peso = _classificar_por_palavras(texto)
            candidatos.append({
                "inicio_seg": inicio,
                "fim_seg": fim,
                "texto": texto,
                "categoria": cat or "audio_peak",
                "peso": peso + 5,
            })

    passo = 60
    for t in range(0, int(duracao_total), passo):
        chave = int(t // 30)
        if chave in usados:
            continue
        inicio = float(t)
        fim = inicio + 60
        texto = _texto_no_intervalo(segmentos, inicio, fim)
        if len(texto.split()) < 8:
            continue
        cat, peso = _classificar_por_palavras(texto)
        if peso < 1:
            continue
        usados.add(chave)
        candidatos.append({
            "inicio_seg": inicio,
            "fim_seg": fim,
            "texto": texto,
            "categoria": cat,
            "peso": peso,
        })

    candidatos.sort(key=lambda x: x["peso"], reverse=True)
    return candidatos[:max_candidatos]


def _classificar_por_palavras(texto):
    texto_lower = texto.lower()
    melhor_cat = None
    melhor_peso = 0
    for cat, config in CATEGORIAS.items():
        hits = sum(1 for p in config["palavras"] if p in texto_lower)
        peso = hits * config["peso"]
        if peso > melhor_peso:
            melhor_peso = peso
            melhor_cat = cat
    return melhor_cat, melhor_peso


def _chamar_ia(system_prompt, user_content, usar_ollama):
    if usar_ollama:
        return _chamar_ollama(system_prompt, user_content)
    else:
        return _chamar_openai(system_prompt, user_content)


def _parsear_resposta_bruta(conteudo):
    conteudo = conteudo.replace("```json", "").replace("```", "").strip()

    inicio = conteudo.find("{")
    if inicio == -1:
        return []
    conteudo = conteudo[inicio:]

    try:
        dados = json.loads(conteudo)
    except json.JSONDecodeError:
        fim_obj = conteudo.rfind("}")
        if fim_obj > inicio:
            try:
                dados = json.loads(conteudo[:fim_obj + 1])
            except json.JSONDecodeError:
                return []
        else:
            return []

    return dados.get("cortes", [dados] if isinstance(dados, dict) and dados.get("titulo") else [])


def _validar_e_corrigir(cortes, segmentos):
    validados = []
    for c in cortes:
        inicio = c.get("inicio_seg", 0)
        fim = c.get("fim_seg", 0)
        duracao = fim - inicio

        if duracao < 15:
            fim = inicio + 60
        if duracao > 120:
            fim = inicio + 60

        c["inicio_seg"] = inicio
        c["fim_seg"] = fim

        texto_seg = _texto_no_intervalo(segmentos, inicio, fim)
        if len(texto_seg.split()) < 8:
            inicio, fim, texto_seg = _buscar_mais_proximo(inicio, segmentos)
            if not texto_seg:
                continue
            c["inicio_seg"] = inicio
            c["fim_seg"] = fim

        if "hook_text" not in c or not c["hook_text"]:
            c["hook_text"] = _hook_do_texto(texto_seg)
        else:
            genericos = [
                "ASSISTA ATE O FIM", "VOCE PRECISA VER", "ISSO E INSANO",
                "PRESTA ATENCAO", "OLHA SO ISSO", "BORA VER ISSO",
                "FRASE DO VIDEO",
            ]
            if c["hook_text"].upper().strip().rstrip(":") in [g.upper() for g in genericos]:
                c["hook_text"] = _hook_do_texto(texto_seg)

        if "tipo" not in c:
            c["tipo"] = "ia"

        if not c.get("score_viral"):
            c["score_viral"] = 5.0

        if not c.get("titulo"):
            c["titulo"] = texto_seg[:40].strip() + "..."

        validados.append(c)

    return validados


def _hook_do_texto(texto):
    sentencas = [s.strip() for s in texto.replace("!", "!|").replace("?", "?|").replace(".", ".|").split("|") if len(s.strip()) > 5]
    if sentencas:
        return sentencas[0].upper()[:40]
    return "ASSISTA"


def _normalizar_timestamp(val):
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val = val.strip()
        if ":" in val:
            partes = val.split(":")
            try:
                if len(partes) == 2:
                    return float(partes[0]) * 60 + float(partes[1])
                elif len(partes) == 3:
                    return float(partes[0]) * 3600 + float(partes[1]) * 60 + float(partes[2])
            except ValueError:
                pass
        try:
            return float(val)
        except (ValueError, TypeError):
            pass
    return 0.0


def _buscar_mais_proximo(inicio_alvo, segmentos, janela=60):
    melhor_seg = None
    melhor_dist = float("inf")
    for seg in segmentos:
        meio = (seg["inicio"] + seg["fim"]) / 2
        dist = abs(meio - inicio_alvo)
        if dist < melhor_dist:
            melhor_dist = dist
            melhor_seg = seg
    if melhor_seg is None:
        return inicio_alvo, inicio_alvo + 60, ""
    novo_inicio = melhor_seg["inicio"]
    novo_fim = novo_inicio + janela
    texto = _texto_no_intervalo(segmentos, novo_inicio, novo_fim)
    return novo_inicio, novo_fim, texto


def _texto_no_intervalo(segmentos, inicio, fim):
    trechos = []
    for seg in segmentos:
        if seg["fim"] >= inicio and seg["inicio"] <= fim:
            trechos.append(seg["texto"].strip())
    return " ".join(trechos)


def detectar_highlights_por_audio(picos_audio, transcricao, max_cortes=5,
                                    duracao_min=15, duracao_max=90):
    if not picos_audio:
        return []

    segmentos = transcricao.get("segmentos", [])
    cortes = []

    for idx, pico in enumerate(picos_audio[:max_cortes * 2]):
        centro = (pico["inicio_seg"] + pico["fim_seg"]) / 2.0
        inicio = max(0, centro - duracao_max / 2.0)
        fim = centro + duracao_max / 2.0

        if fim - inicio > 90:
            fim = inicio + 90

        texto_segmento = _texto_no_intervalo(segmentos, inicio, fim)
        if not texto_segmento:
            continue

        cortes.append({
            "inicio_seg": inicio,
            "fim_seg": fim,
            "score_viral": min(pico.get("energia_relacionada", 1) * 2, 10),
            "texto": texto_segmento,
            "tipo": "audio_peak",
            "titulo": texto_segmento[:40].strip() + "...",
            "hook_text": _hook_do_texto(texto_segmento),
            "tags": ["reels", "viral", "fyp", "shorts", "trending"],
            "descricao": f"#reels #viral #fyp #shorts #trending",
        })

    cortes = _remover_sobreposicao_temporal(cortes, distancia_minima=duracao_min)
    cortes = cortes[:max_cortes]

    print(f"  {len(cortes)} cortes gerados por analise de audio")
    return cortes


REELS_MAX_DURACAO = 90


def _remover_sobreposicao_temporal(cortes, distancia_minima=30):
    if not cortes:
        return cortes

    cortes.sort(key=lambda x: x["inicio_seg"])
    resultado = [cortes[0]]
    for c in cortes[1:]:
        if c["inicio_seg"] - resultado[-1]["inicio_seg"] >= distancia_minima:
            resultado.append(c)
    return resultado
