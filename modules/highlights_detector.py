import json
import os
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import OPENAI_API_KEY, OPENAI_CHAT_MODEL, criar_cliente_openai, nome_provedor_openai

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

PROMPT_AVALIAR = """You are a viral video editor specializing in Brazilian Portuguese content. Analyze the transcript segment below (spoken in Portuguese) and classify what type of moment it is.

Categories: funny, serious, emotional, revelation, controversial, strong_opinion, surreal, confrontation, motivational, fear

Respond ONLY with valid JSON, no extra text:
{"bom": true, "categoria": "type", "score_viral": 7, "titulo": "short title in Portuguese", "hook_text": "ACTUAL QUOTE FROM THE SEGMENT IN PORTUGUESE", "motivo": "brief reason in English"}

Rules:
- score_viral: 1-10 (be strict: most content is 1-4, only genuinely engaging moments get 7+)
- hook_text: MUST be a real sentence extracted from the transcript, not invented
- titulo: short catchy title in Portuguese
- If not interesting: {"bom": false, "categoria": "", "score_viral": 0, "titulo": "", "hook_text": "", "motivo": ""}"""


def _usar_ollama():
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        if r.status_code != 200:
            return False
        modelos = [m.get("name", "").lower() for m in r.json().get("models", [])]
        return any(OLLAMA_MODEL.lower() in m for m in modelos)
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
            "temperature": 0.2,
            "num_predict": 800,
        }
    }
    resp = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=300)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _chamar_openai(system_prompt, user_content):
    client = criar_cliente_openai()
    resposta = client.chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
        max_tokens=800,
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
        print(f"  Usando {nome_provedor_openai()} ({OPENAI_CHAT_MODEL})...")
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
    print(f"  Avaliando com IA (paralelo)...")

    avaliados = _avaliar_candidatos_paralelo(candidatos, ollama_disponivel)

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


def _avaliar_candidatos_paralelo(candidatos, ollama_disponivel, max_workers=4):
    avaliados = []
    total = len(candidatos)

    def _avaliar_um(i, cand):
        texto = cand["texto"]
        min_i = int(cand["inicio_seg"] // 60)
        seg_i = int(cand["inicio_seg"] % 60)
        cat_preliminar = cand.get("categoria", "?")
        label = f"[{i + 1}/{total}] {min_i:02d}:{seg_i:02d} ({cat_preliminar})"

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
            if resultado.get("bom", False) or score >= 6:
                resultado["tipo"] = resultado.get("categoria", cat_preliminar)
                resultado["tags"] = ["reels", "viral", "fyp", "shorts", "trending"]
                resultado["descricao"] = "#reels #viral #fyp #shorts #trending"
                if not resultado.get("hook_text"):
                    resultado["hook_text"] = _hook_do_texto(texto)
                if not resultado.get("titulo"):
                    resultado["titulo"] = texto[:40].strip() + "..."
                return (label, resultado, f" OK ({score}/10)")
            else:
                return (label, None, f" descartado ({score}/10)")
        except Exception as e:
            return (label, None, f" ERRO: {e}")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_avaliar_um, i, cand): i for i, cand in enumerate(candidatos)}
        for future in as_completed(futures):
            label, resultado, status = future.result()
            print(f"    {label}...{status}")
            if resultado is not None:
                avaliados.append(resultado)

    return avaliados


def _gerar_candidatos(segmentos, picos_audio, max_candidatos):
    duracao_total = segmentos[-1]["fim"] - segmentos[0]["inicio"]
    candidatos = []
    usados = set()

    if picos_audio:
        for pico in picos_audio:
            centro = (pico["inicio_seg"] + pico["fim_seg"]) / 2.0
            pico_dur = pico["fim_seg"] - pico["inicio_seg"]
            janela = min(max(pico_dur * 3, 30), 90)
            inicio = max(0, centro - janela / 2)
            fim = inicio + janela
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

    passo = 45
    for t in range(0, int(duracao_total), passo):
        chave = int(t // 30)
        if chave in usados:
            continue
        inicio = float(t)
        texto_curto = _texto_no_intervalo(segmentos, inicio, inicio + 30)
        texto_longo = _texto_no_intervalo(segmentos, inicio, inicio + 60)
        cat_c, peso_c = _classificar_por_palavras(texto_curto)
        cat_l, peso_l = _classificar_por_palavras(texto_longo)

        if peso_c >= peso_l and peso_c >= 1:
            texto, cat, peso = texto_curto, cat_c, peso_c
            fim = inicio + 30
        elif peso_l >= 1:
            texto, cat, peso = texto_longo, cat_l, peso_l
            fim = inicio + 60
        else:
            continue

        if len(texto.split()) < 8:
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
    texto_lower = re.sub(r'[^\w\s]', ' ', texto_lower)
    palavras_texto = set(texto_lower.split())
    melhor_cat = None
    melhor_peso = 0
    for cat, config in CATEGORIAS.items():
        hits = 0
        for p in config["palavras"]:
            p_clean = re.sub(r'[^\w\s]', ' ', p.lower()).strip()
            if not p_clean:
                continue
            if ' ' in p_clean:
                if p_clean in texto_lower:
                    hits += 1
            else:
                if p_clean in palavras_texto:
                    hits += 1
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

    brace_count = 0
    json_start = -1
    for i, c in enumerate(conteudo):
        if c == '{':
            if brace_count == 0:
                json_start = i
            brace_count += 1
        elif c == '}':
            brace_count -= 1
            if brace_count == 0 and json_start >= 0:
                candidate = conteudo[json_start:i + 1]
                try:
                    dados = json.loads(candidate)
                    if isinstance(dados, dict):
                        return dados.get("cortes", [dados] if dados.get("titulo") or dados.get("bom") is not None else [])
                except json.JSONDecodeError:
                    continue

    return []


HOOKS_GENERICOS = {
    "ASSISTA ATE O FIM", "VOCE PRECISA VER", "ISSO E INSANO",
    "PRESTA ATENCAO", "OLHA SO ISSO", "BORA VER ISSO",
    "FRASE DO VIDEO", "ASSISTA", "WATCH THIS", "MUST SEE",
    "ASSISTA ATE O FINAL", "NAO ACREDITE", "ISSO E BIZARRO",
    "OLHA ISSO", "PRESTA ATENCAO NESSA",
}


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
            hook_normalizado = re.sub(r'[:.!?…\s]+', '', c["hook_text"].upper().strip())
            if any(hook_normalizado == re.sub(r'[:.!?…\s]+', '', g) for g in HOOKS_GENERICOS):
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
    sentencas = [s.strip() for s in re.split(r'[.!?]', texto) if len(s.strip()) > 5]
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

    cortes.sort(key=lambda x: x.get("score_viral") or 0, reverse=True)

    resultado = []
    for c in cortes:
        sobreposto = False
        for s in resultado:
            overlap = min(c["fim_seg"], s["fim_seg"]) - max(c["inicio_seg"], s["inicio_seg"])
            if overlap > distancia_minima * 0.5:
                sobreposto = True
                break
        if not sobreposto:
            resultado.append(c)
    return resultado
