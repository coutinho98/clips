import re


def refinar_cortes(cortes, transcricao, duracao_min=20, duracao_max=60):
    segmentos = transcricao.get("segmentos", [])
    if not segmentos or not cortes:
        return cortes

    refinars = []
    for corte in cortes:
        rc = dict(corte)
        inicio = rc.get("inicio_seg", 0)
        fim = rc.get("fim_seg", inicio + 60)

        inicio, fim = _snap_para_sentenca(inicio, fim, segmentos)
        rc["inicio_seg"] = inicio
        rc["fim_seg"] = fim

        inicio, fim = _trim_silencio(inicio, fim, segmentos)
        rc["inicio_seg"] = inicio
        rc["fim_seg"] = fim

        duracao = fim - inicio
        if duracao < duracao_min:
            inicio, fim = _expandir_corte(inicio, fim, segmentos, duracao_min)
            rc["inicio_seg"] = inicio
            rc["fim_seg"] = fim
        elif duracao > duracao_max:
            fim = inicio + duracao_max
            inicio, fim = _snap_para_sentenca(inicio, fim, segmentos)
            rc["inicio_seg"] = inicio
            rc["fim_seg"] = fim

        rc["texto"] = _texto_no_intervalo(segmentos, inicio, fim)
        rc["duracao"] = rc["fim_seg"] - rc["inicio_seg"]
        refinars.append(rc)

    refinars = _remover_sobreposicao(refinars)

    return refinars


def _snap_para_sentenca(inicio, fim, segmentos):
    primeiro = None
    ultimo = None
    for seg in segmentos:
        if seg["fim"] >= inicio and seg["inicio"] <= fim:
            if primeiro is None or seg["inicio"] < primeiro["inicio"]:
                primeiro = seg
            if ultimo is None or seg["fim"] > ultimo["fim"]:
                ultimo = seg

    if primeiro:
        novo_inicio = primeiro["inicio"]
        if _fim_de_sentenca(_sentenca_antes(primeiro, segmentos)):
            pass
        else:
            prev = _segmento_antes(primeiro, segmentos)
            if prev and (primeiro["inicio"] - prev["fim"]) < 1.5:
                if _fim_de_sentenca(prev):
                    novo_inicio = prev["fim"]
        inicio = novo_inicio

    if ultimo:
        novo_fim = ultimo["fim"]
        if not _fim_de_sentenca(ultimo):
            prox = _segmento_depois(ultimo, segmentos)
            if prox and (prox["inicio"] - ultimo["fim"]) < 1.5:
                novo_fim = prox["fim"]
        fim = novo_fim

    return inicio, fim


def _trim_silencio(inicio, fim, segmentos):
    segs_no_corte = [s for s in segmentos if s["fim"] >= inicio and s["inicio"] <= fim]

    if not segs_no_corte:
        return inicio, fim

    segs_no_corte.sort(key=lambda s: s["inicio"])

    primeiro = segs_no_corte[0]
    gap_inicio = primeiro["inicio"] - inicio
    if gap_inicio > 2.0:
        inicio = primeiro["inicio"] - 0.3
        if inicio < 0:
            inicio = 0

    ultimo = segs_no_corte[-1]
    gap_fim = fim - ultimo["fim"]
    if gap_fim > 2.0:
        fim = ultimo["fim"] + 0.3

    return inicio, fim


def _expandir_corte(inicio, fim, segmentos, duracao_min):
    segs_no_corte = [s for s in segmentos if s["fim"] >= inicio and s["inicio"] <= fim]

    if not segs_no_corte:
        return inicio, inicio + duracao_min

    segs_no_corte.sort(key=lambda s: s["inicio"])

    expandir_frente = True
    while (fim - inicio) < duracao_min:
        if expandir_frente:
            prox = None
            for s in segmentos:
                if s["inicio"] >= fim and s["inicio"] - fim < 3.0:
                    prox = s
                    break
            if prox:
                fim = prox["fim"]
            else:
                expandir_frente = False
        else:
            ant = None
            for s in reversed(segmentos):
                if s["fim"] <= inicio and inicio - s["fim"] < 3.0:
                    ant = s
                    break
            if ant:
                inicio = ant["inicio"]
            else:
                break

        if not expandir_frente:
            break

    return inicio, fim


def _remover_sobreposicao(cortes, distancia_min=15):
    if len(cortes) <= 1:
        return cortes

    cortes.sort(key=lambda c: c.get("score_viral") or 0, reverse=True)

    resultado = []
    for c in cortes:
        ci = c.get("inicio_seg", 0)
        cf = c.get("fim_seg", 60)
        sobreposto = False
        for r in resultado:
            ri = r.get("inicio_seg", 0)
            rf = r.get("fim_seg", 60)
            overlap = min(cf, rf) - max(ci, ri)
            if overlap > distancia_min:
                sobreposto = True
                break
        if not sobreposto:
            resultado.append(c)

    removidos = len(cortes) - len(resultado)
    if removidos > 0:
        print(f"  {removidos} cortes removidos por sobreposição após refinamento")

    return resultado


def _fim_de_sentenca(seg):
    texto = seg.get("texto", "").strip()
    if not texto:
        return False
    return bool(re.search(r'[.!?]$', texto))


def _sentenca_antes(seg, segmentos):
    idx = None
    for i, s in enumerate(segmentos):
        if s is seg or (s["inicio"] == seg["inicio"] and s["fim"] == seg["fim"]):
            idx = i
            break
    if idx is not None and idx > 0:
        return segmentos[idx - 1]
    return None


def _segmento_antes(seg, segmentos):
    melhor = None
    melhor_dist = float("inf")
    for s in segmentos:
        if s["fim"] <= seg["inicio"]:
            dist = seg["inicio"] - s["fim"]
            if dist < melhor_dist:
                melhor_dist = dist
                melhor = s
    return melhor


def _segmento_depois(seg, segmentos):
    melhor = None
    melhor_dist = float("inf")
    for s in segmentos:
        if s["inicio"] >= seg["fim"]:
            dist = s["inicio"] - seg["fim"]
            if dist < melhor_dist:
                melhor_dist = dist
                melhor = s
    return melhor


def _texto_no_intervalo(segmentos, inicio, fim):
    trechos = []
    for seg in segmentos:
        if seg["fim"] >= inicio and seg["inicio"] <= fim:
            trechos.append(seg["texto"].strip())
    return " ".join(trechos)
