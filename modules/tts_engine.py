import asyncio
import os
import edge_tts
from config import VOZ, PASTA_TEMP

TIMEOUT_POR_PARTE = 30

async def _gerar_audio_async(texto, caminho_saida, timeout=TIMEOUT_POR_PARTE):
    try:
        communicate = edge_tts.Communicate(texto, VOZ)
        await asyncio.wait_for(communicate.save(caminho_saida), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        print(f"    [TIMEOUT] Geração excedeu {timeout}s, tentando salvar parcial...")
        try:
            communicate = edge_tts.Communicate(texto, VOZ)
            await asyncio.wait_for(communicate.save(caminho_saida), timeout=timeout * 2)
            return True
        except Exception:
            return False
    except Exception as e:
        print(f"    [ERRO] {e}")
        return False

def gerar_narracao_partes(partes_roterio):
    caminhos = []
    total = len(partes_roterio)

    async def _gerar_todas():
        resultados = []
        for i, parte in enumerate(partes_roterio):
            caminho = f"{PASTA_TEMP}/parte_{i}.mp3"
            print(f"    [{i+1}/{total}] Gerando áudio... ", end="", flush=True)

            ok = await _gerar_audio_async(parte, caminho)

            if ok and os.path.exists(caminho) and os.path.getsize(caminho) > 0:
                tamanho_kb = os.path.getsize(caminho) / 1024
                print(f"OK ({tamanho_kb:.0f} KB)")
                resultados.append(caminho)
            else:
                print("FALHOU - tentando com voz alternativa...")
                try:
                    communicate = edge_tts.Communicate(parte, "pt-BR-FranciscaNeural")
                    await asyncio.wait_for(communicate.save(caminho), timeout=TIMEOUT_POR_PARTE)
                    if os.path.exists(caminho) and os.path.getsize(caminho) > 0:
                        print(f"    [{i+1}/{total}] OK com voz alternativa")
                        resultados.append(caminho)
                except Exception as e:
                    print(f"    [{i+1}/{total}] ERRO FINAL: {e}")

        return resultados

    caminhos = asyncio.run(_gerar_todas())
    return caminhos

def gerar_narracao(texto, caminho_saida=None):
    if caminho_saida is None:
        caminho_saida = f"{PASTA_TEMP}/narracao.mp3"
    asyncio.run(_gerar_audio_async(texto, caminho_saida))
    return caminho_saida
