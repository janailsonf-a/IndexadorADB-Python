#!/bin/sh

set -e

echo "Iniciando serviço de indexação (agendado 1x/dia)..."

# Hora do dia (0-23) para rodar a indexação. Fica fora do expediente para não
# disputar I/O do mount ntfs3 com a API durante o uso — era isso que derrubava
# o servidor (busca travava enquanto o worker varria o acervo). Ajuste no .env.
# ATENÇÃO ao timezone do container: se ele está em UTC e o galpão é UTC-3
# (Ceará), use 5 para cair ~02:00 no horário local.
TARGET_HOUR="${INDEXER_HOUR:-5}"

while true
do
  echo "Executando indexação em $(date)"
  python -m app.indexer || true

  now=$(date +%s)
  next=$(date -d "today ${TARGET_HOUR}:00" +%s 2>/dev/null || echo 0)
  if [ "$next" = "0" ]; then
    # date sem -d (busybox): cai para intervalo fixo de ~24h.
    sleep_sec=86400
  else
    [ "$next" -le "$now" ] && next=$(date -d "tomorrow ${TARGET_HOUR}:00" +%s)
    sleep_sec=$((next - now))
    echo "Próxima indexação em $(date -d "@${next}") (dormindo ${sleep_sec}s)"
  fi

  sleep "$sleep_sec"
done
