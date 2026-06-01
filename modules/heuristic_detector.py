import re
import os
import numpy as np
from pydub import AudioSegment


PALAVROES = [
    "porra", "caralho", "merda", "foda", "puta", "cacete", "desgraça",
    "desgraca", "inferno", "diabo", "caramba", "mano",
    "shit", "fuck", "damn", "omg", "wtf",
]

RISADAS = [
    "haha", "kkkk", "kkk", "hehe", "rsrs", "loool", "lol", "rofl",
    "kkkkk", "ahuahu", "hauhau",
]

SUPERLATIVOS = [
    "incrível", "incrive", "absurdo", "absurda", "insano", "insana",
    "genial", "perfeito", "perfeita", "mágico", "magico", "lenda",
    "lendário", "lendario", "histórico", "historico", "nunca vi",
    "primeira vez", "inédito", "inedito", "absurdamente",
    "mega", "ultra", "hiper", "incrivel",
]

PALAVRAS_REACAO = [
    "não acredito", "nao acredito", "não pode ser", "nao pode ser",
    "é mentira", "e mentira", "tá brincando", "ta brincando",
    "sério", "serio", "como assim", "caramba",
    "cê é", "ce é", "wow", "uau", "meu deus", "meu god",
    "pqp", "vish", "rapaz", "pow", "nossa",
]

PALAVRAS_REVELACAO = [
    "na verdade", "descobri", "descobrimos", "revela", "revelou",
    "segredo", "mistério", "misterio", "spoiler", "surpresa",
    "plot twist", "virada", "mudou tudo", "tava errado",
    "enganado", "não sabia", "nao sabia", "ninguém sabia",
    "ninguem sabia", "escondido", "por baixo dos panos",
]


def detectar_highlights_heuristico(transcricao, picos_audio=None, max_cortes=5,
                                    duracao_min=30, duracao_max=90):
    segmentos = transcricao.get("segmentos", [])
    if not segmentos:
        return []

    print(f"  Analisando {len(segmentos)} segmentos...")
    print(f"  [1/3] Mapeando energia do audio por segmento...")

    energia_seg = _energia_por_segmento(segmentos, picos_audio)

    print(f"  [2/3] Encontrando momentos de contraste (audio + fala)...")

    momentos_quentes = _encontrar_momentos_quentes(segmentos, energia_seg)

    print(f"  {len(momentos_quentes)} momentos quentes identificados")

    print(f"  [3/3] Construindo cortes com contexto...")

    cortes = []
    for momento in momentos_quentes:
        corte = _construir_corte_completo(
            momento, segmentos, energia_seg, duracao_min, duracao_max
        )
        if corte:
            cortes.append(corte)

    cortes = _remover_sobrepostos(cortes)
    cortes.sort(key=lambda x: x["score_viral"], reverse=True)
    cortes = cortes[:max_cortes]

    print(f"  {len(cortes)} cortes selecionados")
    return cortes


def _energia_por_segmento(segmentos, picos_audio):
    energias = []

    if picos_audio:
        for seg in segmentos:
            centro = (seg["inicio"] + seg["fim"]) / 2.0
            energia = 0
            for pico in picos_audio:
                if pico["inicio_seg"] <= centro <= pico["fim_seg"]:
                    energia = max(energia, pico.get("energia_relacionada", 0))
                elif abs(centro - (pico["inicio_seg"] + pico["fim_seg"]) / 2) < 10:
                    energia = max(energia, pico.get("energia_relacionada", 0) * 0.5)
            energias.append(energia)
    else:
        for seg in segmentos:
            energias.append(0)

    return energias


def _encontrar_momentos_quentes(segmentos, energia_seg):
    if not segmentos:
        return []

    media_energia = sum(energia_seg) / len(energia_seg) if energia_seg else 0

    scores_segmentos = []
    for i, seg in enumerate(segmentos):
        score = 0.0
        texto = seg["texto"].strip()
        texto_lower = texto.lower()

        e = energia_seg[i]
        if e >= 2.5:
            score += 5.0
        elif e >= 1.5:
            score += 3.0
        elif e >= 0.8:
            score += 1.0

        if i > 0:
            contraste_audio = abs(energia_seg[i] - energia_seg[i - 1])
            if contraste_audio >= 2.0:
                score += 4.0
            elif contraste_audio >= 1.0:
                score += 2.0

        if any(p in texto_lower for p in PALAVROES):
            score += 2.0
        if any(r in texto_lower for r in PALAVRAS_REACAO):
            score += 2.0
        if any(r in texto_lower for r in PALAVRAS_REVELACAO):
            score += 2.0
        if any(s in texto_lower for s in SUPERLATIVOS):
            score += 1.5
        if any(r in texto_lower for r in RISADAS):
            score += 1.5

        score += min(texto.count("!") * 0.5, 2.0)

        caps = sum(1 for c in texto if c.isupper())
        caps_ratio = caps / max(len(texto), 1)
        if caps_ratio > 0.5 and len(texto) > 5:
            score += 2.0
        elif caps_ratio > 0.35 and len(texto) > 5:
            score += 1.0

        palavras = texto.split()
        if len(palavras) > 3:
            velocidade = len(palavras) / max(seg["fim"] - seg["inicio"], 0.1)
            if velocidade > 5:
                score += 1.0

        scores_segmentos.append(score)

    media_score = sum(scores_segmentos) / len(scores_segmentos)
    limite = max(media_score * 1.8, 3.0)

    momentos = []
    i = 0
    while i < len(segmentos):
        if scores_segmentos[i] >= limite:
            grupo_inicio = i
            grupo_fim = i
            melhor_score = scores_segmentos[i]
            i += 1
            while i < len(segmentos) and scores_segmentos[i] >= limite * 0.4:
                grupo_fim = i
                melhor_score = max(melhor_score, scores_segmentos[i])
                i += 1

            momentos.append({
                "idx_inicio": grupo_inicio,
                "idx_fim": grupo_fim,
                "score": melhor_score,
            })
        else:
            i += 1

    momentos.sort(key=lambda x: x["score"], reverse=True)
    return momentos


def _construir_corte_completo(momento, segmentos, energia_seg, duracao_min, duracao_max):
    idx_pico_inicio = momento["idx_inicio"]
    idx_pico_fim = momento["idx_fim"]

    idx_inicio = _expandir_inicio(idx_pico_inicio, segmentos, energia_seg, duracao_max)
    idx_fim = _expandir_fim(idx_pico_fim, segmentos, energia_seg, duracao_max)

    duracao = segmentos[idx_fim]["fim"] - segmentos[idx_inicio]["inicio"]

    if duracao > duracao_max:
        idx_fim = _reduzir_fim(idx_fim, idx_pico_fim, segmentos, duracao_max)

    if duracao > duracao_max:
        idx_inicio = _reduzir_inicio(idx_inicio, idx_pico_inicio, segmentos, duracao_max)

    duracao = segmentos[idx_fim]["fim"] - segmentos[idx_inicio]["inicio"]

    if duracao < duracao_min:
        idx_inicio, idx_fim = _tentar_expandir(
            idx_inicio, idx_fim, segmentos, duracao_min, duracao_max
        )
        duracao = segmentos[idx_fim]["fim"] - segmentos[idx_inicio]["inicio"]

    if duracao < duracao_min * 0.6:
        return None

    inicio_seg = segmentos[idx_inicio]["inicio"]
    fim_seg = segmentos[idx_fim]["fim"]
    texto = " ".join(
        segmentos[j]["texto"].strip()
        for j in range(idx_inicio, idx_fim + 1)
        if segmentos[j]["texto"].strip()
    )

    if len(texto.split()) < 10:
        return None

    score = _score_final(texto, duracao, idx_inicio, idx_fim, idx_pico_inicio, idx_pico_fim,
                         segmentos, energia_seg, momento["score"])
    if score < 2.0:
        return None

    hook = _extrair_hook(texto, idx_inicio, idx_fim, idx_pico_inicio, segmentos)
    titulo = _extrair_titulo(texto, segmentos, idx_inicio, idx_fim)

    return {
        "inicio_seg": inicio_seg,
        "fim_seg": fim_seg,
        "score_viral": min(score, 10),
        "titulo": titulo,
        "hook_text": hook,
        "texto": texto,
        "tipo": _classificar(texto),
        "tags": ["reels", "viral", "fyp", "shorts", "trending"],
        "descricao": f"#reels #viral #fyp #shorts #trending",
    }


def _expandir_inicio(idx_pico, segmentos, energia_seg, duracao_max):
    idx = idx_pico
    limite = idx_pico

    for i in range(idx_pico - 1, -1, -1):
        if segmentos[idx_pico]["inicio"] - segmentos[i]["inicio"] > duracao_max:
            break

        gap = segmentos[i + 1]["inicio"] - segmentos[i]["fim"]
        if gap >= 3.0:
            idx = i + 1
            break

        idx = i

        if gap >= 1.5 and _termina_frase(segmentos[i]):
            break

    return idx


def _expandir_fim(idx_pico, segmentos, energia_seg, duracao_max):
    idx = idx_pico

    for i in range(idx_pico + 1, len(segmentos)):
        if segmentos[i]["fim"] - segmentos[idx_pico]["fim"] > duracao_max * 0.5:
            break

        gap = segmentos[i]["inicio"] - segmentos[i - 1]["fim"]
        if gap >= 3.0:
            break

        idx = i

        if gap >= 1.5 and _termina_frase(segmentos[i]):
            break

    return idx


def _reduzir_fim(idx_fim, idx_pico_fim, segmentos, duracao_max):
    target = segmentos[idx_fim]["inicio"] + duracao_max
    for i in range(idx_fim, idx_pico_fim, -1):
        if segmentos[i]["fim"] <= target:
            return i
    return idx_pico_fim


def _reduzir_inicio(idx_inicio, idx_pico_inicio, segmentos, duracao_max):
    target = segmentos[idx_inicio]["fim"] - duracao_max
    for i in range(idx_inicio, idx_pico_inicio):
        if segmentos[i]["inicio"] >= target:
            return i
    return idx_pico_inicio


def _tentar_expandir(idx_inicio, idx_fim, segmentos, duracao_min, duracao_max):
    duracao = segmentos[idx_fim]["fim"] - segmentos[idx_inicio]["inicio"]

    for i in range(idx_inicio - 1, -1, -1):
        gap = segmentos[i + 1]["inicio"] - segmentos[i]["fim"]
        if gap >= 4.0:
            break
        idx_inicio = i
        duracao = segmentos[idx_fim]["fim"] - segmentos[idx_inicio]["inicio"]
        if duracao >= duracao_min:
            break

    if duracao < duracao_min:
        for i in range(idx_fim + 1, len(segmentos)):
            gap = segmentos[i]["inicio"] - segmentos[i - 1]["fim"]
            if gap >= 4.0:
                break
            idx_fim = i
            duracao = segmentos[idx_fim]["fim"] - segmentos[idx_inicio]["inicio"]
            if duracao >= duracao_min:
                break

    return idx_inicio, idx_fim


def _score_final(texto, duracao, idx_inicio, idx_fim, idx_pico_i, idx_pico_f,
                 segmentos, energia_seg, score_pico):
    score = 0.0
    texto_lower = texto.lower()

    score += min(score_pico * 0.4, 4.0)

    n_segmentos_contexto_antes = idx_pico_i - idx_inicio
    n_segmentos_payoff = idx_fim - idx_pico_f

    if n_segmentos_contexto_antes >= 3:
        score += 2.0
    elif n_segmentos_contexto_antes >= 1:
        score += 1.0

    if n_segmentos_payoff >= 2:
        score += 1.0

    if 30 <= duracao <= 60:
        score += 2.0
    elif 25 <= duracao < 30:
        score += 1.0
    elif 60 < duracao <= 90:
        score += 0.5
    elif duracao < 20:
        score -= 1.0

    energia_pico_media = sum(energia_seg[idx_pico_i:idx_pico_f + 1]) / max(idx_pico_f - idx_pico_i + 1, 1)
    energia_inicio_media = sum(energia_seg[idx_inicio:idx_pico_i]) / max(idx_pico_i - idx_inicio, 1)
    contraste = energia_pico_media - energia_inicio_media

    if contraste >= 2.0:
        score += 3.0
    elif contraste >= 1.0:
        score += 1.5
    elif contraste >= 0.5:
        score += 0.5

    palavras = texto.split()
    densidade = len(palavras) / max(duracao, 1)
    if 1.5 <= densidade <= 5.0:
        score += 1.0

    if any(p in texto_lower for p in PALAVROES):
        score += 0.5
    if any(r in texto_lower for r in PALAVRAS_REACAO):
        score += 0.5
    if any(r in texto_lower for r in PALAVRAS_REVELACAO):
        score += 0.5
    if any(s in texto_lower for s in SUPERLATIVOS):
        score += 0.5

    return max(round(score, 2), 0)


def _classificar(texto):
    texto_lower = texto.lower()
    if any(r in texto_lower for r in PALAVRAS_REVELACAO):
        return "revelacao"
    if any(p in texto_lower for p in PALAVROES):
        return "reacao"
    if any(r in texto_lower for r in PALAVRAS_REACAO):
        return "reacao"
    if any(r in texto_lower for r in RISADAS):
        return "humor"
    return "momento"


def _extrair_hook(texto, idx_inicio, idx_fim, idx_pico_inicio, segmentos):
    segs_antes = segmentos[idx_inicio:idx_pico_inicio]
    segs_pico = segmentos[idx_pico_inicio:idx_fim + 1]

    if segs_antes:
        for seg in reversed(segs_antes[-3:]):
            t = seg["texto"].strip()
            if len(t) >= 8:
                return _formatar_hook(t)

    if segs_pico:
        melhor_seg = max(segs_pico, key=lambda s: _impacto_frase(s["texto"]))
        t = melhor_seg["texto"].strip()
        if len(t) >= 5:
            return _formatar_hook(t)

    return _formatar_hook(texto[:45].strip()) if texto.strip() else "ASSISTA ATE O FIM"


def _extrair_titulo(texto, segmentos, idx_inicio, idx_fim):
    segs = segmentos[idx_inicio:idx_fim + 1]
    melhor = None
    melhor_score = -1

    for seg in segs:
        t = seg["texto"].strip()
        s = _impacto_frase(t)
        if s > melhor_score and len(t) >= 8:
            melhor_score = s
            melhor = t

    if melhor:
        titulo = melhor[0].upper() + melhor[1:]
        if len(titulo) > 50:
            titulo = titulo[:47] + "..."
        if not titulo.endswith(("!", "?", ".", "...")):
            titulo += "..."
        return titulo

    sentencas = _dividir_sentencas(texto)
    if sentencas:
        t = sentencas[0].strip()
        titulo = t[0].upper() + t[1:]
        if len(titulo) > 50:
            titulo = titulo[:47] + "..."
        if not titulo.endswith(("!", "?", ".", "...")):
            titulo += "..."
        return titulo

    return "Destaque"


def _impacto_frase(texto):
    score = 0
    t = texto.lower()
    if any(p in t for p in PALAVROES):
        score += 3
    if any(r in t for r in PALAVRAS_REACAO):
        score += 3
    if any(r in t for r in PALAVRAS_REVELACAO):
        score += 3
    if any(r in t for r in RISADAS):
        score += 2
    if any(s in t for s in SUPERLATIVOS):
        score += 2
    score += texto.count("!") * 1.0
    caps = sum(1 for c in texto if c.isupper())
    if caps / max(len(texto), 1) > 0.4 and len(texto) > 3:
        score += 2
    return score


def _termina_frase(seg):
    t = seg["texto"].strip()
    return t.endswith((".", "!", "?", "...")) if t else True


def _dividir_sentencas(texto):
    sentencas = []
    for s in re.split(r'(?<=[.!?])\s+', texto):
        s = s.strip()
        if s:
            sentencas.append(s)
    if not sentencas:
        sentencas = [texto.strip()] if texto.strip() else []
    return sentencas


def _formatar_hook(frase):
    hook = frase.strip().upper()
    hook = re.sub(r'\s+', ' ', hook)
    if len(hook) > 45:
        cortado = hook[:42].rsplit(' ', 1)[0]
        hook = cortado + "..."
    return hook


def _remover_sobrepostos(cortes):
    if not cortes:
        return cortes

    cortes.sort(key=lambda x: x["score_viral"], reverse=True)

    selecionados = []
    for c in cortes:
        sobreposto = False
        for s in selecionados:
            overlap = min(c["fim_seg"], s["fim_seg"]) - max(c["inicio_seg"], s["inicio_seg"])
            if overlap > 10:
                sobreposto = True
                break
        if not sobreposto:
            selecionados.append(c)

    return selecionados
