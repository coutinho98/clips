import json
import os
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import OPENAI_API_KEY

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_BIN = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ollama", "bin", "ollama")

_ollama_cache = {"result": None, "checked": False}

CATEGORIAS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "momentos.json")


def _carregar_categorias():
    default = {
        "engraçado": {"palavras": ["kkk", "haha", "rindo", "engraçado", "hilar", "piada", "zuado", "morri"], "peso": 3},
        "sério": {"palavras": ["sério", "importante", "grave", "preocupante", "urgente", "atenção"], "peso": 3},
        "emocionante": {"palavras": ["chorar", "emocionante", "saudade", "emoção", "comovido", "tocou"], "peso": 3},
        "confronto": {"palavras": ["briga", "confronto", "discussão", "discutindo", "irado", "absurdo", "mentira", "mentiroso", "covarde", "ladrão"], "peso": 4},
        "revelação": {"palavras": ["descobri", "revelar", "segredo", "ninguém sabe", "escondido", "verdade", "surpresa"], "peso": 4},
        "dinheiro": {"palavras": ["dinheiro", "milhão", "milhões", "salário", "preço", "caro", "barato", "lucro", "prejuízo", "grana", "rico", "pobre"], "peso": 2},
        "polêmica": {"palavras": ["polêmica", "controverso", "cancelado", "escândalo", "opinião", "discordo", "errado", "certo"], "peso": 3},
        "escândalo": {"palavras": ["escândalo", "exposto", "provou", "flagrante", "denúncia", "comprometedor", "vazou", "vazamento", "evidência", "prova", "gravou", "flagrado"], "peso": 5},
        "política": {"palavras": ["governo", "presidente", "político", "eleição", "voto", "corrupção", "congresso", "ministro", "senador", "deputado"], "peso": 2},
        "forte": {"palavras": ["insano", "absurdo", "loucura", "nunca vi", "impressionante", "inacreditável", "bizarro", "chocante"], "peso": 3},
        "motivacional": {"palavras": ["conseguir", "vitória", "superar", "lutando", "força", "nunca desista", "sonho", "focado", "disciplina"], "peso": 2},
    }
    if os.path.exists(CATEGORIAS_PATH):
        try:
            with open(CATEGORIAS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


CATEGORIAS = _carregar_categorias()

PROMPT_AVALIAR = """You are a viral content strategist specializing in Brazilian Portuguese podcasts and livestreams. Your job is to find moments that will make people STOP SCROLLING and SHARE.

The transcript below is from a Brazilian podcast/livestream. The "[BEFORE]" section is what leads into the moment, "[SEGMENT]" is the actual clip, and "[AFTER]" is what follows.

CRITICAL: The clip must start where the CONVERSATION TOPIC begins, not in the middle. A viewer should understand what's being discussed from the very first second.

Respond ONLY with valid JSON:
{"bom": true, "categoria": "type", "score_viral": 8, "titulo": "short title in Portuguese", "hook_text": "ACTUAL QUOTE from the segment in Portuguese", "motivo": "brief reason in English", "tema": "main topic in 3 words max", "inicio_sugerido": "first relevant sentence from BEFORE or SEGMENT that starts the topic"}

SCORE GUIDE (be honest and precise):
- 9-10: Nuclear moment. Something shocking, a huge revelation, an explosive confrontation, someone crying/breaking down, a confession, a massive plot twist.
- 7-8: Very strong moment. A bold controversial opinion, a funny unexpected reaction, a heated argument, a surprising story, a quotable hot take.
- 5-6: Decent moment. Interesting opinion, mild humor, somewhat engaging story.
- 3-4: Below average. Normal conversation, nothing remarkable.
- 1-2: Boring filler.

WHAT MAKES CONTENT VIRAL:
1. EMOTIONAL INTENSITY - Anger, shock, genuine laughter, tears, fear.
2. UNEXPECTED - Something the audience didn't see coming.
3. CONTROVERSY - Hot takes, disagreements, calling someone out.
4. RELATABLE STORIES - Personal stories that viewers connect with.
5. QUOTABLE - A single sentence so impactful people will quote it.
6. CONFRONTATION - Tension between speakers, uncomfortable moments.

RULES:
- hook_text: The MOST IMPACTFUL actual sentence from the transcript. Not invented.
- titulo: Short, punchy, creates CURIOSITY in Portuguese.
- tema: Specific topic in 3 words max
- inicio_sugerido: The first sentence of the clip that makes sense as a START POINT. Must be an actual sentence from [BEFORE] or [SEGMENT].
- Each clip must be about a DIFFERENT topic. Duplicates waste slots.
- If boring: {"bom": false, "categoria": "", "score_viral": 0, "titulo": "", "hook_text": "", "motivo": "", "tema": "", "inicio_sugerido": ""}
- DO NOT be overly generous. Most podcast content is 3-5. Only exceptional moments get 7+."""


def _usar_ollama():
    global _ollama_cache
    if _ollama_cache["checked"]:
        return _ollama_cache["result"]
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        if r.status_code != 200:
            _ollama_cache["result"] = False
        else:
            modelos = [m.get("name", "").lower() for m in r.json().get("models", [])]
            _ollama_cache["result"] = any(OLLAMA_MODEL.lower() in m for m in modelos)
    except Exception:
        _ollama_cache["result"] = False
    _ollama_cache["checked"] = True
    return _ollama_cache["result"]


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
            "num_predict": 400,
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
        temperature=0.2,
        max_tokens=800,
    )
    return resposta.choices[0].message.content.strip()


def detectar_highlights(transcricao, picos_audio=None, max_cortes=5):
    segmentos = transcricao.get("segmentos", [])
    if not segmentos:
        print("  [ERRO] Nenhum segmento na transcrição")
        return []

    ollama_disponivel = _usar_ollama()
    if ollama_disponivel:
        print(f"  Usando Ollama local ({OLLAMA_MODEL})...")
    elif OPENAI_API_KEY:
        print(f"  Usando OpenAI GPT-4o-mini...")
    else:
        print(f"  [ERRO] Nem Ollama nem OpenAI disponíveis")
        return []

    candidatos = _gerar_candidatos(segmentos, picos_audio, max_cortes * 5)
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
    avaliados = _avaliar_candidatos_paralelo(candidatos, ollama_disponivel, segmentos)

    avaliados.sort(key=lambda x: x.get("score_viral") or 0, reverse=True)
    avaliados = _validar_e_corrigir(avaliados, segmentos)
    avaliados = _remover_temas_duplicados(avaliados)
    avaliados = avaliados[:max_cortes]

    print(f"\n  {len(avaliados)} cortes aprovados:")
    for c in avaliados:
        cat = c.get("tipo", "?")
        score = c.get("score_viral", "?")
        titulo = c.get("titulo", "?")
        print(f"    [{cat}] {score}/10 - {titulo}")

    return avaliados


def _avaliar_candidatos_paralelo(candidatos, ollama_disponivel, segmentos, max_workers=4):
    avaliados = []
    total = len(candidatos)

    def _avaliar_um(i, cand):
        texto = cand["texto"]
        min_i = int(cand["inicio_seg"] // 60)
        seg_i = int(cand["inicio_seg"] % 60)
        cat_preliminar = cand.get("categoria", "?")
        label = f"[{i + 1}/{total}] {min_i:02d}:{seg_i:02d} ({cat_preliminar})"

        try:
            contexto = _construir_contexto(segmentos, cand["inicio_seg"], cand["fim_seg"])
            conteudo = _chamar_ia(PROMPT_AVALIAR, contexto, ollama_disponivel)
            resultado = _parsear_resposta_bruta(conteudo)
            if isinstance(resultado, list):
                resultado = resultado[0] if resultado else {}
            if not isinstance(resultado, dict):
                resultado = {}

            resultado["inicio_seg"] = cand["inicio_seg"]
            resultado["fim_seg"] = cand["fim_seg"]

            inicio_sugerido = resultado.get("inicio_sugerido", "")
            if inicio_sugerido:
                novo_inicio = _encontrar_inicio_sugerido(inicio_sugerido, segmentos, cand["inicio_seg"] - 45, cand["inicio_seg"])
                if novo_inicio is not None:
                    resultado["inicio_seg"] = novo_inicio

            score = resultado.get("score_viral") or 0
            if resultado.get("bom", False) or score >= 5:
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

    blocos_tematicos = _segmentar_por_topico(segmentos)

    for bloco in blocos_tematicos:
        texto = bloco["texto"]
        if len(texto.split()) < 8:
            continue

        cat, peso = _classificar_por_palavras(texto)
        peso += _pontuar_padrao_conversa(texto) * 3

        energia = 0
        centro = (bloco["inicio_seg"] + bloco["fim_seg"]) / 2.0
        if picos_audio:
            for pico in picos_audio:
                if pico["inicio_seg"] <= centro <= pico["fim_seg"]:
                    energia = max(energia, pico.get("energia_relacionada", 0))
        peso += energia * 1.5

        candidatos.append({
            "inicio_seg": bloco["inicio_seg"],
            "fim_seg": bloco["fim_seg"],
            "texto": texto,
            "categoria": cat or "momento",
            "peso": peso,
        })

    candidatos_audio = _candidatos_por_pico_audio(segmentos, picos_audio, candidatos)
    candidatos.extend(candidatos_audio)

    candidatos.sort(key=lambda x: x["peso"], reverse=True)
    top = candidatos[:max_candidatos]

    todos_indices = set(range(len(blocos_tematicos)))
    top_indices = set()
    for i, bloco in enumerate(blocos_tematicos):
        for c in top:
            if abs(bloco["inicio_seg"] - c["inicio_seg"]) < 5:
                top_indices.add(i)
                break

    restantes = [i for i in todos_indices - top_indices
                 if len(blocos_tematicos[i]["texto"].split()) >= 8]

    import random as _random
    _random.seed(42)
    step = max(1, len(restantes) // max(max_candidatos // 2, 3))
    amostrados = restantes[::step][:max_candidatos // 2]

    for idx in amostrados:
        bloco = blocos_tematicos[idx]
        texto = bloco["texto"]
        cat, peso = _classificar_por_palavras(texto)
        peso += _pontuar_padrao_conversa(texto) * 3
        energia = 0
        centro = (bloco["inicio_seg"] + bloco["fim_seg"]) / 2.0
        if picos_audio:
            for pico in picos_audio:
                if pico["inicio_seg"] <= centro <= pico["fim_seg"]:
                    energia = max(energia, pico.get("energia_relacionada", 0))
        peso += energia * 1.5

        sobreposto = False
        for c in top:
            overlap = min(c["fim_seg"], bloco["fim_seg"]) - max(c["inicio_seg"], bloco["inicio_seg"])
            if overlap > 10:
                sobreposto = True
                break
        if sobreposto:
            continue

        top.append({
            "inicio_seg": bloco["inicio_seg"],
            "fim_seg": bloco["fim_seg"],
            "texto": texto,
            "categoria": cat or "amostra",
            "peso": peso,
        })

    return top


_PADROES_VIRAIS = [
    (re.compile(r'\b(eu (nunca|sempre|juro|vi|descobri|percebi|notei))\b', re.I), 4),
    (re.compile(r'\b(nunca (falei|contei|disse|imaginei))\b', re.I), 5),
    (re.compile(r'\b(você (sabia|conhece|tem ideia|imagina))\b', re.I), 3),
    (re.compile(r'\b(graças a deus|meu deus|caramba|velho|mano|caraca|putz|nossa)\b', re.I), 2),
    (re.compile(r'[!?]{2,}'), 3),
    (re.compile(r'\b(mas (na verdade|o problema|o pior|a verdade|calma))\b', re.I), 4),
    (re.compile(r'\b(isso (é|e) (absurdo|insano|louco|incrível|bizarro|ridículo|errado|perigoso))\b', re.I), 5),
    (re.compile(r'\b(não (acredito|esperava|sabia|concordo|acho|suporto|tolero|deixo))\b', re.I), 4),
    (re.compile(r'\b(o que (você|vocês|a galera) (acha|pensa|faria|diria))\b', re.I), 3),
    (re.compile(r'\b(presta atenção|escuta (isso|aqui)|olha (só|isso|aqui))\b', re.I), 4),
    (re.compile(r'\b(eu (acho|penso|acredito) que (isso|ele|ela|isso (não )?é))\b', re.I), 3),
    (re.compile(r'\b(se eu (fosse|tivesse|pudesse|contasse|dissesse))\b', re.I), 3),
    (re.compile(r'\b(vingança|traição|segredo|vergonha|medo|ódio|ciúme|inveja)\b', re.I), 4),
]


def _pontuar_padrao_conversa(texto):
    score = 0
    for padrao, peso in _PADROES_VIRAIS:
        if padrao.search(texto):
            score += peso
    return score


def _candidatos_por_pico_audio(segmentos, picos_audio, candidatos_existentes):
    novos = []
    for pico in (picos_audio or []):
        centro = (pico["inicio_seg"] + pico["fim_seg"]) / 2.0
        pico_dur = pico["fim_seg"] - pico["inicio_seg"]
        janela = min(max(pico_dur * 3, 30), 90)
        inicio = max(0, centro - janela / 2)
        fim = inicio + janela

        sobreposto = False
        for c in candidatos_existentes:
            overlap = min(c["fim_seg"], fim) - max(c["inicio_seg"], inicio)
            if overlap > 15:
                sobreposto = True
                break
        for c in novos:
            overlap = min(c["fim_seg"], fim) - max(c["inicio_seg"], inicio)
            if overlap > 15:
                sobreposto = True
                break
        if sobreposto:
            continue

        texto = _texto_no_intervalo(segmentos, inicio, fim)
        if len(texto.split()) < 8:
            continue
        cat, peso = _classificar_por_palavras(texto)
        peso += _pontuar_padrao_conversa(texto) * 3
        novos.append({
            "inicio_seg": inicio,
            "fim_seg": fim,
            "texto": texto,
            "categoria": cat or "audio_peak",
            "peso": peso + 5,
        })
    return novos


def _segmentar_por_topico(segmentos, silencio_gap=3.0, max_dur=90, min_dur=20):
    if not segmentos:
        return []

    blocos = []
    bloco_inicio = segmentos[0]["inicio"]
    bloco_fim = segmentos[0]["fim"]
    bloco_textos = [segmentos[0]["texto"].strip()]

    for i in range(1, len(segmentos)):
        seg = segmentos[i]
        gap = seg["inicio"] - segmentos[i - 1]["fim"]
        duracao_atual = seg["fim"] - bloco_inicio

        if gap >= silencio_gap or duracao_atual >= max_dur:
            texto = " ".join(t for t in bloco_textos if t)
            if len(texto.split()) >= 5:
                blocos.append({
                    "inicio_seg": bloco_inicio,
                    "fim_seg": bloco_fim,
                    "texto": texto,
                })

            bloco_inicio = seg["inicio"]
            bloco_fim = seg["fim"]
            bloco_textos = [seg["texto"].strip()]
        else:
            bloco_fim = seg["fim"]
            bloco_textos.append(seg["texto"].strip())

    texto = " ".join(t for t in bloco_textos if t)
    if len(texto.split()) >= 5:
        blocos.append({
            "inicio_seg": bloco_inicio,
            "fim_seg": bloco_fim,
            "texto": texto,
        })

    resultado = []
    for bloco in blocos:
        duracao = bloco["fim_seg"] - bloco["inicio_seg"]
        if duracao > max_dur:
            sub_blocos = _dividir_bloco(bloco, segmentos, max_dur)
            resultado.extend(sub_blocos)
        else:
            resultado.append(bloco)

    return resultado


def _dividir_bloco(bloco, segmentos, max_dur):
    inicio = bloco["inicio_seg"]
    fim = bloco["fim_seg"]
    sub_blocos = []

    segs_no_bloco = [s for s in segmentos
                     if s["fim"] >= inicio and s["inicio"] <= fim]

    if not segs_no_bloco:
        return [bloco]

    corte_atual = segs_no_bloco[0]["inicio"]
    textos_atual = []
    ultimo_fim = segs_no_bloco[0]["inicio"]

    for seg in segs_no_bloco:
        if seg["fim"] - corte_atual >= max_dur:
            gap = seg["inicio"] - ultimo_fim
            if gap >= 1.5:
                texto = " ".join(t for t in textos_atual if t)
                if texto:
                    sub_blocos.append({
                        "inicio_seg": corte_atual,
                        "fim_seg": ultimo_fim,
                        "texto": texto,
                    })
                corte_atual = seg["inicio"]
                textos_atual = [seg["texto"].strip()]
            else:
                textos_atual.append(seg["texto"].strip())
        else:
            textos_atual.append(seg["texto"].strip())
        ultimo_fim = seg["fim"]

    if textos_atual:
        texto = " ".join(t for t in textos_atual if t)
        if texto:
            sub_blocos.append({
                "inicio_seg": corte_atual,
                "fim_seg": ultimo_fim,
                "texto": texto,
            })

    return sub_blocos


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


def _remover_temas_duplicados(cortes, similaridade_min=0.4):
    if not cortes:
        return cortes

    selecionados = []
    temas_base = []

    for c in cortes:
        tema_c = c.get("tema", "").lower().strip()
        texto_c = c.get("texto", "") or _hook_do_texto(c.get("hook_text", ""))
        palavras_c = set(re.sub(r'[^\w\s]', '', texto_c.lower()).split())
        palavras_c = {p for p in palavras_c if len(p) > 3}

        duplicado = False
        for tema_base, texto_base in temas_base:
            if tema_c and tema_base and tema_c == tema_base:
                duplicado = True
                break

            palavras_base = set(re.sub(r'[^\w\s]', '', texto_base.lower()).split())
            palavras_base = {p for p in palavras_base if len(p) > 3}
            intersecao = palavras_c & palavras_base
            uniao = palavras_c | palavras_base
            if uniao and len(intersecao) / len(uniao) > similaridade_min:
                duplicado = True
                break

        if not duplicado:
            selecionados.append(c)
            temas_base.append((tema_c, texto_c))

    removidos = len(cortes) - len(selecionados)
    if removidos > 0:
        print(f"  {removidos} cortes removidos por contexto duplicado")

    return selecionados


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


def _encontrar_inicio_sugerido(frase_sugerida, segmentos, busca_inicio, busca_fim):
    frase_clean = re.sub(r'[^\w\s]', '', frase_sugerida.lower().strip())
    palavras_sugeridas = set(frase_clean.split())
    if len(palavras_sugeridas) < 2:
        return None

    melhor_seg = None
    melhor_overlap = 0
    for seg in segmentos:
        if seg["inicio"] < busca_inicio or seg["inicio"] > busca_fim:
            continue
        seg_clean = re.sub(r'[^\w\s]', '', seg["texto"].lower())
        palavras_seg = set(seg_clean.split())
        overlap = len(palavras_sugeridas & palavras_seg)
        if overlap > melhor_overlap:
            melhor_overlap = overlap
            melhor_seg = seg

    if melhor_seg and melhor_overlap >= len(palavras_sugeridas) * 0.4:
        return melhor_seg["inicio"]
    return None


def _texto_no_intervalo(segmentos, inicio, fim):
    trechos = []
    for seg in segmentos:
        if seg["fim"] >= inicio and seg["inicio"] <= fim:
            trechos.append(seg["texto"].strip())
    return " ".join(trechos)


def _construir_contexto(segmentos, inicio_seg, fim_seg, contexto_antes=45, contexto_depois=10):
    antes_inicio = max(0, inicio_seg - contexto_antes)
    antes_fim = inicio_seg
    depois_inicio = fim_seg
    depois_fim = fim_seg + contexto_depois

    texto_antes = _texto_no_intervalo(segmentos, antes_inicio, antes_fim)
    texto_seg = _texto_no_intervalo(segmentos, inicio_seg, fim_seg)
    texto_depois = _texto_no_intervalo(segmentos, depois_inicio, depois_fim)

    partes = []
    if texto_antes.strip():
        partes.append(f"[BEFORE - what leads into the moment]:\n{texto_antes.strip()}")
    partes.append(f"[SEGMENT - the actual clip]:\n{texto_seg.strip()}")
    if texto_depois.strip():
        partes.append(f"[AFTER - what follows]:\n{texto_depois.strip()}")

    return "\n\n".join(partes)


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

    print(f"  {len(cortes)} cortes gerados por análise de áudio")
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
