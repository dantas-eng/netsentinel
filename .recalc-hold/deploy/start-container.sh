#!/bin/sh
# Uma instância/worker: fonte sintética e EventBus vivem no mesmo processo.
set -eu
if [ "${APP_MODE:-}" != cloud ]; then
  echo 'Inicialização padrão do container exige APP_MODE=cloud (dados sintéticos).' >&2
  exit 1
fi
# Falha de migração impede iniciar o servidor com schema incompleto.
python -m netsentinel.api migrate
exec gunicorn --bind "0.0.0.0:${PORT:-8080}" --workers 1 --threads 8 \
  --timeout 60 --worker-tmp-dir /tmp --access-logfile - --error-logfile - \
  'netsentinel.api.wsgi:create_service()'
