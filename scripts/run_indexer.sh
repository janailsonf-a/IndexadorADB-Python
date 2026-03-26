#!/bin/sh

set -e

echo "Iniciando serviço de indexação..."

while true
do
  echo "Executando indexação em $(date)"
  python -m app.indexer || true
  echo "Aguardando 300 segundos para próxima execução..."
  sleep 300
done