#!/usr/bin/env bash
# Atividade #3 - Faz upload de uma imagem no bucket de origem e espera a Lambda
# gerar a versão processada no bucket de destino.
# Uso:  ./atividade3-lambda/testar.sh                (usa a exemplo.png)
#       ./atividade3-lambda/testar.sh ~/foto.jpg     (usa a sua imagem)
set -euo pipefail

IMAGEM="$(realpath "${1:-$(dirname "$0")/exemplo.png}")"
cd "$(dirname "$0")"

ENDPOINT="${AWS_ENDPOINT_URL:-http://localhost:4566}"
REGIAO="${AWS_DEFAULT_REGION:-us-east-1}"
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
export AWS_PAGER=""
awsl() { aws --endpoint-url="$ENDPOINT" --region "$REGIAO" "$@"; }

ORIGEM="imagens-originais"
DESTINO="imagens-processadas"
NOME="$(basename "$IMAGEM")"

echo "==> Enviando '$NOME' para s3://$ORIGEM/"
awsl s3 cp "$IMAGEM" "s3://$ORIGEM/$NOME"

echo "==> Esperando a Lambda processar (a 1ª execução é mais lenta)..."
for _ in $(seq 1 45); do
  if awsl s3api head-object --bucket "$DESTINO" --key "$NOME" >/dev/null 2>&1; then
    mkdir -p resultado
    awsl s3 cp "s3://$DESTINO/$NOME" "resultado/$NOME" >/dev/null
    echo
    echo "OK! A Lambda gerou a imagem processada:"
    awsl s3 ls "s3://$DESTINO/"
    echo "Cópia local: atividade3-lambda/resultado/$NOME"
    exit 0
  fi
  sleep 2
done

echo "A imagem processada não apareceu em 90s."
echo "Veja os logs:  aws --endpoint-url=$ENDPOINT logs tail /aws/lambda/processa-imagem"
echo "          ou:  docker logs localstack --tail 50"
exit 1
