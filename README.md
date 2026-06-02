# Dark Channel Bot

Bot automatizado para gerar vídeos para canais "dark" (faceless) usando IA.

## Setup

```bash
# 1. Crie e ative o ambiente virtual
python3 -m venv venv
source venv/bin/activate

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Instale o FFmpeg (Ubuntu/Debian)
sudo apt install ffmpeg

# 4. Configure o .env
cp .env.example .env
# Edite o .env com suas API keys
```

## API Keys

| Serviço | Onde conseguir | Obrigatório? |
|---|---|---|
| **OpenAI** | https://platform.openai.com/api-keys | Não (se usar Ollama local) |
| **Pexels** | https://www.pexels.com/api/ | Não (usa placeholder) |

## Ollama (IA Local - Llama 3.2)

O projeto usa Llama 3.2 via Ollama para detectar os melhores momentos das lives. Tudo roda local, sem custo de API.

### Primeira vez - baixar o modelo

```bash
# Se instalou o Ollama via sistema:
ollama pull llama3.2

# Se está usando o bin local do projeto:
./ollama/bin/ollama pull llama3.2
```

### Subir o servidor Ollama

Abra um terminal separado e deixe rodando:

```bash
# Se instalou via sistema:
ollama serve

# Se está usando o bin local do projeto:
./ollama/bin/ollama serve
```

O servidor sobe em `http://localhost:11434` por padrão. Deixe esse terminal aberto enquanto usa o bot.

Para confirmar que está funcionando:

```bash
curl http://localhost:11434/api/tags
# Deve retornar um JSON com "llama3.2" nos modelos
```

### Configuração no .env

```env
# Ollama (padrão já funciona local)
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

# Se quiser usar OpenAI em vez de Ollama:
OPENAI_API_KEY=sk-sua-chave-aqui
```

## Uso - Live Clipper (Cortes de Lives)

```bash
# Cortes automáticos de uma live (usa Ollama local, 100% gratis)
python live_clipper.py --url "https://www.youtube.com/watch?v=VIDEO_ID"

# Cortes com detecção por IA (Ollama + heurísticas)
python live_clipper.py --url "https://www.youtube.com/watch?v=VIDEO_ID" --detectar-por ambos

# Cortes com legendas estilo neon
python live_clipper.py --url "https://www.youtube.com/watch?v=VIDEO_ID" --legendas --estilo-legendas neon

# Gerar só previews (sem encodar, mais rápido)
python live_clipper.py --url "https://www.youtube.com/watch?v=VIDEO_ID" --preview

# Usar vídeo local em vez de URL
python live_clipper.py --video /caminho/para/video.mp4

# Processar várias lives de uma vez (batch)
python live_clipper.py --batch urls.txt -n 8

# Máximo de cortes e modelo Whisper
python live_clipper.py --url "URL" -n 10 --modelo-whisper small
```

### Opções completas

| Flag | Default | Descrição |
|---|---|---|
| `--url` | - | URL da live (YouTube, Twitch, etc) |
| `--video` | - | Caminho para vídeo local |
| `--batch` | - | Arquivo .txt com lista de URLs |
| `-n` | 12 | Número máximo de cortes |
| `--detectar-por` | `ia` | Método: `heuristicas`, `ia`, `audio`, `ambos` |
| `--transcricao` | `local` | `local` (Whisper) ou `api` (OpenAI) |
| `--modelo-whisper` | `base` | `tiny`, `base`, `small`, `medium`, `large` |
| `--legendas` | off | Ativar legendas nos cortes |
| `--estilo-legendas` | `neon` | `neon`, `karaoke`, `box`, `sombra` |
| `--sem-crop` | off | Desativar crop vertical 9:16 |
| `--bg-music` | - | Caminho para música de fundo |
| `--bg-music-volume` | 0.15 | Volume da música (0.0 a 1.0) |
| `--preview` | off | Gerar só thumbnails |
| `--upload` | off | Auto-upload Instagram |
| `--no-cache` | off | Desativar cache/resume |

## Uso - Vídeos Dark (Faceless)

```bash
# Gerar 1 vídeo com roteiro IA
python main.py

# Gerar vários em lote
python batch.py -n 5
```

## Fluxo do Live Clipper

```
1. Download do vídeo (yt-dlp)
2. Extração do áudio (ffmpeg)
3. Transcrição (Whisper local)
4. Análise de picos de energia do áudio
5. Detecção de highlights (Ollama Llama 3.2 + heurísticas)
6. Extração dos cortes em formato Reels (9:16, crop vertical)
```

## Estrutura

```
dark-channel-bot/
├── main.py                     # Pipeline principal (1 vídeo faceless)
├── batch.py                    # Geração em lote (faceless)
├── live_clipper.py             # Cortes automáticos de lives
├── config.py                   # Configurações
├── modules/
│   ├── highlights_detector.py  # Detecção de highlights com IA (Ollama/OpenAI)
│   ├── heuristic_detector.py   # Detecção por heurísticas (offline)
│   ├── audio_analyzer.py       # Análise de picos de energia
│   ├── transcriber.py          # Transcrição Whisper
│   ├── clip_extractor.py       # Extração de cortes via ffmpeg
│   ├── subtitle_generator.py   # Legendas estilizadas
│   ├── live_downloader.py      # Download de lives (yt-dlp)
│   ├── cache.py                # Cache/resume de etapas
│   ├── script_generator.py     # Geração de roteiro (OpenAI)
│   ├── tts_engine.py           # Narração com voz IA (edge-tts)
│   ├── image_fetcher.py        # Busca de imagens (Pexels)
│   └── video_assembler.py      # Montagem do vídeo (MoviePy)
├── ollama/                     # Ollama local (bin + modelos)
├── momentos.json               # Palavras-chave por categoria
├── output/                     # Vídeos + metadados gerados
├── temp/                       # Arquivos temporários
└── assets/                     # Recursos estáticos
```
