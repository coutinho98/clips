import json
from openai import OpenAI
from config import OPENAI_API_KEY, NICHO

client = OpenAI(api_key=OPENAI_API_KEY)

PROMPT_SISTEMA = f"""Você é um roteirista de vídeos curtos (YouTube Shorts / TikTok) sobre {NICHO}.
Gere conteúdo no seguinte formato JSON:
{{
    "titulo": "título chamativo para o vídeo",
    "descricao": "descrição do vídeo para YouTube (com hashtags)",
    "tags": ["tag1", "tag2", ...],
    "roteiro": "texto completo da narração, em português do Brasil, tom misterioso e envolvente. Duracao aproximada de 60 a 90 segundos quando lido em voz alta.",
    "termos_busca_imagem": ["termo1", "termo2", ...]
}}
Regras:
- O roteiro deve ter ganchos fortes no início
- Use linguagem informal e envolvente
- Termos de busca devem ser em inglês para melhores resultados
- Retorne APENAS o JSON, sem markdown"""

def gerar_roteiro():
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": PROMPT_SISTEMA},
            {"role": "user", "content": f"Gere um roteiro sobre {NICHO}. Seja criativo e surpreendente."}
        ],
        temperature=0.9,
        max_tokens=1000
    )

    conteudo = response.choices[0].message.content.strip()
    conteudo = conteudo.replace("```json", "").replace("```", "").strip()
    dados = json.loads(conteudo)

    dados["roteiro"] = _dividir_roteiro(dados["roteiro"])
    return dados

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
