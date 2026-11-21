"""
Atividade #3 - Função Lambda acionada por upload no S3 (LocalStack)

Fluxo:
  1. Alguém faz upload de uma imagem no bucket "imagens-originais".
  2. O S3 dispara um EVENTO (s3:ObjectCreated) que chama esta função.
  3. A função baixa a imagem, deixa em preto e branco e reduz para no máximo 300x300.
  4. O resultado é salvo no bucket "imagens-processadas" (outro bucket!).

Esta função NÃO roda no seu terminal: o LocalStack executa ela dentro de um
container Docker, igual a AWS faz com o Lambda de verdade.
"""
import io
import os
import urllib.parse

import boto3
from botocore.config import Config
from PIL import Image, ImageOps, UnidentifiedImageError

BUCKET_DESTINO = os.environ.get("BUCKET_DESTINO", "imagens-processadas")
TAMANHO_MAXIMO = (300, 300)
FORMATOS_SUPORTADOS = {"JPEG", "PNG", "GIF", "WEBP"}

# Dentro do LocalStack a variável AWS_ENDPOINT_URL já vem preenchida,
# então o boto3 conversa com o S3 simulado. Na AWS real ela não existe
# e o boto3 usa o S3 de verdade - o MESMO código funciona nos dois.
s3 = boto3.client(
    "s3",
    endpoint_url=os.environ.get("AWS_ENDPOINT_URL"),
    config=Config(s3={"addressing_style": "path"}),
)


def processar_imagem(conteudo):
    """Recebe os bytes da imagem e devolve (bytes_processados, formato)."""
    imagem = Image.open(io.BytesIO(conteudo))
    formato = imagem.format if imagem.format in FORMATOS_SUPORTADOS else "PNG"
    if imagem.format == "MPO":  # foto de celular com várias "camadas" -> JPEG
        formato = "JPEG"

    imagem = ImageOps.exif_transpose(imagem)  # corrige rotação de fotos de celular
    imagem = ImageOps.grayscale(imagem)       # 1) preto e branco
    imagem.thumbnail(TAMANHO_MAXIMO)          # 2) reduz mantendo a proporção

    saida = io.BytesIO()
    imagem.save(saida, format=formato)
    return saida.getvalue(), formato


def lambda_handler(event, context):
    """Ponto de entrada: o Lambda chama esta função passando o evento do S3."""
    processadas = []

    # Um evento pode trazer vários registros (vários arquivos)
    for registro in event.get("Records", []):
        bucket_origem = registro["s3"]["bucket"]["name"]
        # O nome vem "codificado" (espaço vira +), por isso o unquote_plus
        chave = urllib.parse.unquote_plus(registro["s3"]["object"]["key"])
        print(f"Recebido evento: s3://{bucket_origem}/{chave}")

        original = s3.get_object(Bucket=bucket_origem, Key=chave)["Body"].read()
        try:
            resultado, formato = processar_imagem(original)
        except UnidentifiedImageError:
            print(f"'{chave}' não é uma imagem válida - ignorado.")
            continue

        s3.put_object(
            Bucket=BUCKET_DESTINO,
            Key=chave,
            Body=resultado,
            ContentType=Image.MIME.get(formato, "application/octet-stream"),
            Metadata={"origem": f"{bucket_origem}/{chave}", "processamento": "cinza-300px"},
        )
        print(f"Salvo: s3://{BUCKET_DESTINO}/{chave} "
              f"({len(original)} bytes -> {len(resultado)} bytes)")
        processadas.append(chave)

    return {"statusCode": 200, "processadas": processadas}
