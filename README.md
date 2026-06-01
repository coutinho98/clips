# Dark Channel Bot

Bot automatizado para gerar vídeos para canais "dark" (faceless) usando IA.

## Setup

```bash
# 1. Instale as dependências
pip install -r requirements.txt

# 2. Instale o FFmpeg (Ubuntu/Debian)
sudo apt install ffmpeg

# 3. Configure o .env
cp .env.example .env
# Edite o .env com suas API keys
```

## API Keys necessárias

| Serviço | Onde conseguir | Obrigatório? |
|---|---|---|
| **OpenAI** | https://platform.openai.com/api-keys | Sim |
| **Pexels** | https://www.pexels.com/api/ | Não (usa placeholder) |

## Uso

```bash
# Gerar 1 vídeo
python main.py

# Gerar vários vídeos em lote
python batch.py -n 5
```

## Estrutura

```
dark-channel-bot/
├── main.py                  # Pipeline principal (1 vídeo)
├── batch.py                 # Geração em lote
├── config.py                # Configurações
├── modules/
│   ├── script_generator.py  # Geração de roteiro (OpenAI)
│   ├── tts_engine.py        # Narração com voz IA (edge-tts)
│   ├── image_fetcher.py     # Busca de imagens (Pexels)
│   └── video_assembler.py   # Montagem do vídeo (MoviePy)
├── output/                  # Vídeos + metadados gerados
├── temp/                    # Arquivos temporários
└── assets/                  # Recursos estáticos
```

## Fluxo

1. Gera roteiro via OpenAI (GPT-4o-mini)
2. Converte texto em áudio com voz IA (edge-tts, gratuito)
3. Busca imagens no Pexels (ou gera placeholders)
4. Monta vídeo com efeito Ken Burns + áudio
5. Salva vídeo + metadados (título, descrição, tags) prontos para upload
