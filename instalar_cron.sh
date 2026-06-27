#!/usr/bin/env bash
#
# Instala (ou atualiza) os horários de postagem no crontab.
# Idempotente: roda quantas vezes quiser. Preserva seus outros jobs do cron.
#
# YouTube Shorts:
#   Seg-Sex: 15h, 16h, 17h, 18h
#   Sáb-Dom: 09h, 10h, 11h
#
# TikTok:
#   Seg: 07h, 11h, 22h
#   Ter: 14h, 16h, 21h
#   Qua: 07h, 09h, 23h
#   Qui: 09h, 12h, 19h
#   Sex: 06h, 13h, 15h
#   Sáb: 11h, 20h, 21h
#   Dom: 08h, 09h, 17h
#
set -euo pipefail

DIR="/media/shadys/darkchannel/dark-channel-bot"
PY="$DIR/venv/bin/python"
LOG="$DIR/logs/cron.log"
CMD="$PY $DIR/postar.py --um"
MARK_BEGIN="# BEGIN dark-channel-bot (auto)"
MARK_END="# END dark-channel-bot (auto)"

existing="$(crontab -l 2>/dev/null || true)"
# remove bloco anterior deste projeto (se houver), mantém o resto
rest="$(printf '%s\n' "$existing" | sed "/$MARK_BEGIN/,/$MARK_END/d")"

{
  printf '%s\n' "$rest"
  echo "$MARK_BEGIN"
  echo "# --- YouTube Shorts ---"
  echo "0 15,16,17,18 * * 1-5 $CMD --plataformas youtube >> $LOG 2>&1"
  echo "0 9,10,11    * * 6,0 $CMD --plataformas youtube >> $LOG 2>&1"
  echo "# --- TikTok ---"
  echo "0 7,11,22  * * 1 $CMD --plataformas tiktok >> $LOG 2>&1"
  echo "0 14,16,21 * * 2 $CMD --plataformas tiktok >> $LOG 2>&1"
  echo "0 7,9,23   * * 3 $CMD --plataformas tiktok >> $LOG 2>&1"
  echo "0 9,12,19  * * 4 $CMD --plataformas tiktok >> $LOG 2>&1"
  echo "0 6,13,15  * * 5 $CMD --plataformas tiktok >> $LOG 2>&1"
  echo "0 11,20,21 * * 6 $CMD --plataformas tiktok >> $LOG 2>&1"
  echo "0 8,9,17   * * 0 $CMD --plataformas tiktok >> $LOG 2>&1"
  echo "$MARK_END"
} | crontab -

echo "✔ Cron instalado/atualizado."
echo "  Veja com: crontab -l"
echo "  Logs:     tail -f $LOG"
