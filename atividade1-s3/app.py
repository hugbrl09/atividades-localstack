"""
Atividade #1 - Upload / listagem / download de imagens no Amazon S3 (LocalStack)

Como rodar (com o LocalStack já ligado e o .venv ativado):
    python atividade1-s3/app.py
Depois abra http://localhost:5001 no navegador.
"""
import io
import os

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from flask import Flask, flash, redirect, render_template, send_file, url_for
from flask import request
from werkzeug.utils import secure_filename

# ------------------------------------------------------------------
# Configuração: em vez da AWS real, apontamos para o LocalStack.
# É SÓ ISSO que muda em relação a um código que usaria a AWS de verdade.
# ------------------------------------------------------------------
ENDPOINT = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
REGIAO = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
BUCKET = os.getenv("BUCKET_NAME", "atividade1-imagens")
EXTENSOES_PERMITIDAS = {"png", "jpg", "jpeg", "gif", "webp"}

s3 = boto3.client(
    "s3",
    endpoint_url=ENDPOINT,
    region_name=REGIAO,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),        # o LocalStack aceita
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),  # qualquer credencial
    config=Config(s3={"addressing_style": "path"}),  # URL no formato localhost:4566/bucket/arquivo
)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "troque-esta-chave")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # limite de 10 MB por upload


@app.before_request
def garantir_bucket():
    """Cria o bucket se ele ainda não existir (equivale a: aws s3 mb s3://BUCKET).

    Roda antes de cada requisição: se o LocalStack for reiniciado (e o bucket
    sumir), o app recria sozinho em vez de dar erro.
    """
    try:
        s3.head_bucket(Bucket=BUCKET)
    except ClientError:
        s3.create_bucket(Bucket=BUCKET)
        print(f"Bucket '{BUCKET}' criado.")


def extensao_valida(nome):
    return "." in nome and nome.rsplit(".", 1)[1].lower() in EXTENSOES_PERMITIDAS


@app.route("/")
def index():
    """LISTAR: pede ao S3 a lista de objetos (arquivos) do bucket."""
    resposta = s3.list_objects_v2(Bucket=BUCKET)
    arquivos = [
        {
            "nome": obj["Key"],
            "tamanho_kb": round(obj["Size"] / 1024, 1),
            "data": obj["LastModified"].strftime("%d/%m/%Y %H:%M:%S"),
        }
        for obj in resposta.get("Contents", [])
    ]
    return render_template("index.html", arquivos=arquivos, bucket=BUCKET)


@app.route("/upload", methods=["POST"])
def upload():
    """UPLOAD: recebe o arquivo do formulário e grava no bucket com put_object."""
    arquivo = request.files.get("arquivo")
    if not arquivo or arquivo.filename == "":
        flash("Selecione um arquivo.", "erro")
        return redirect(url_for("index"))
    if not extensao_valida(arquivo.filename):
        flash("Envie apenas imagens (png, jpg, jpeg, gif, webp).", "erro")
        return redirect(url_for("index"))

    nome = secure_filename(arquivo.filename)  # remove caracteres perigosos do nome
    s3.put_object(
        Bucket=BUCKET,
        Key=nome,                     # "Key" = nome do objeto dentro do bucket
        Body=arquivo.read(),          # conteúdo (bytes) da imagem
        ContentType=arquivo.mimetype, # ex.: image/png
    )
    flash(f"'{nome}' enviado para o bucket '{BUCKET}'.", "ok")
    return redirect(url_for("index"))


def _buscar_objeto(nome, como_anexo):
    """Lê o objeto do S3 (get_object) e devolve para o navegador."""
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=nome)
    except ClientError:
        flash(f"Arquivo '{nome}' não encontrado.", "erro")
        return redirect(url_for("index"))
    return send_file(
        io.BytesIO(obj["Body"].read()),
        mimetype=obj.get("ContentType", "application/octet-stream"),
        as_attachment=como_anexo,
        download_name=nome,
    )


@app.route("/download/<path:nome>")
def download(nome):
    """DOWNLOAD: o navegador baixa o arquivo."""
    return _buscar_objeto(nome, como_anexo=True)


@app.route("/ver/<path:nome>")
def ver(nome):
    """Mostra a imagem na página (usado para a miniatura)."""
    return _buscar_objeto(nome, como_anexo=False)


@app.errorhandler(413)
def arquivo_grande(_erro):
    flash("Arquivo maior que 10 MB.", "erro")
    return redirect(url_for("index"))


if __name__ == "__main__":
    garantir_bucket()
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5001")), debug=True)
