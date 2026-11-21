#!/usr/bin/env bash
# Atividade #3 - Cria os buckets, publica a função Lambda e liga o gatilho do S3.
# Uso (com o LocalStack ligado e o .venv ativado):  ./atividade3-lambda/deploy.sh
set -euo pipefail
cd "$(dirname "$0")"

ENDPOINT="${AWS_ENDPOINT_URL:-http://localhost:4566}"
REGIAO="${AWS_DEFAULT_REGION:-us-east-1}"
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
export AWS_PAGER=""   # não abrir o "less" nas saídas do aws cli
awsl() { aws --endpoint-url="$ENDPOINT" --region "$REGIAO" "$@"; }

ORIGEM="imagens-originais"
DESTINO="imagens-processadas"
FUNCAO="processa-imagem"
CONTA="000000000000"   # ID de conta fixo usado pelo LocalStack
PY_LAMBDA="3.12"       # versão do Python que a Lambda vai usar

echo "==> 1/6 Criando os buckets '$ORIGEM' e '$DESTINO'"
for bucket in "$ORIGEM" "$DESTINO"; do
  awsl s3api head-bucket --bucket "$bucket" >/dev/null 2>&1 || awsl s3 mb "s3://$bucket"
done

echo "==> 2/6 Criando o papel (IAM role) da função"
awsl iam get-role --role-name lambda-role >/dev/null 2>&1 || awsl iam create-role \
  --role-name lambda-role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
  >/dev/null

echo "==> 3/6 Empacotando código + biblioteca Pillow em function.zip"
case "$(uname -m)" in
  aarch64|arm64) ARQ="arm64";  PLAT="aarch64" ;;
  *)             ARQ="x86_64"; PLAT="x86_64"  ;;
esac
rm -rf build function.zip
# Baixa o Pillow já compilado para o Linux da Lambda (não para o seu PC)
python3 -m pip install --quiet --target build \
  --implementation cp --python-version "$PY_LAMBDA" --only-binary=:all: \
  --platform "manylinux2014_$PLAT" --platform "manylinux_2_28_$PLAT" \
  pillow
cp lambda_function.py build/
(cd build && python3 -m zipfile -c ../function.zip .)
echo "    function.zip: $(du -h function.zip | cut -f1)"

echo "==> 4/6 Publicando a função Lambda '$FUNCAO'"
if awsl lambda get-function --function-name "$FUNCAO" >/dev/null 2>&1; then
  awsl lambda update-function-code --function-name "$FUNCAO" --zip-file fileb://function.zip >/dev/null
else
  awsl lambda create-function \
    --function-name "$FUNCAO" \
    --runtime "python$PY_LAMBDA" \
    --architectures "$ARQ" \
    --handler lambda_function.lambda_handler \
    --zip-file fileb://function.zip \
    --role "arn:aws:iam::$CONTA:role/lambda-role" \
    --timeout 30 \
    --memory-size 256 \
    --environment "Variables={BUCKET_DESTINO=$DESTINO}" \
    >/dev/null
fi
echo "    aguardando a função ficar pronta (na 1ª vez baixa a imagem do Python, pode levar 1-2 min)..."
awsl lambda wait function-active-v2 --function-name "$FUNCAO"
awsl lambda wait function-updated-v2 --function-name "$FUNCAO"

echo "==> 5/6 Permitindo que o S3 invoque a função"
awsl lambda add-permission \
  --function-name "$FUNCAO" \
  --statement-id s3-invoca-lambda \
  --action lambda:InvokeFunction \
  --principal s3.amazonaws.com \
  --source-arn "arn:aws:s3:::$ORIGEM" >/dev/null 2>&1 || true   # já existe = ok

echo "==> 6/6 Ligando o gatilho: todo upload em s3://$ORIGEM chama a função"
awsl s3api put-bucket-notification-configuration \
  --bucket "$ORIGEM" \
  --notification-configuration "{
    \"LambdaFunctionConfigurations\": [{
      \"LambdaFunctionArn\": \"arn:aws:lambda:$REGIAO:$CONTA:function:$FUNCAO\",
      \"Events\": [\"s3:ObjectCreated:*\"]
    }]
  }"

echo
echo "Pronto! Agora teste com:  ./atividade3-lambda/testar.sh"
