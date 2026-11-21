"""
Atividade #2 - Cadastro e login de usuários com Amazon DynamoDB (LocalStack)

Como rodar (com o LocalStack já ligado e o .venv ativado):
    python atividade2-dynamodb/app.py
Depois abra http://localhost:5002 no navegador.
"""
import os
from datetime import datetime
from functools import wraps

import boto3
from botocore.exceptions import ClientError
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

# ------------------------------------------------------------------
# Configuração: apontamos o boto3 para o LocalStack em vez da AWS real.
# ------------------------------------------------------------------
ENDPOINT = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
REGIAO = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
TABELA = os.getenv("TABLE_NAME", "usuarios")

dynamodb = boto3.resource(
    "dynamodb",
    endpoint_url=ENDPOINT,
    region_name=REGIAO,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
)
tabela = dynamodb.Table(TABELA)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "troque-esta-chave")  # assina o cookie de sessão


@app.before_request
def garantir_tabela():
    """Cria a tabela 'usuarios' se ela ainda não existir (roda antes de cada requisição).

    No DynamoDB só é obrigatório definir a CHAVE PRIMÁRIA. Aqui ela é o e-mail
    (HASH = partition key). Os outros atributos (nome, senha_hash...) são livres,
    sem esquema fixo - por isso é um banco NoSQL.
    """
    try:
        dynamodb.meta.client.describe_table(TableName=TABELA)
    except ClientError:
        dynamodb.create_table(
            TableName=TABELA,
            KeySchema=[{"AttributeName": "email", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "email", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",  # sem precisar definir capacidade
        )
        dynamodb.meta.client.get_waiter("table_exists").wait(TableName=TABELA)
        print(f"Tabela '{TABELA}' criada.")


def login_obrigatorio(funcao):
    """Decorator: só deixa acessar a rota se o usuário estiver logado."""
    @wraps(funcao)
    def verificar(*args, **kwargs):
        if "email" not in session:
            flash("Faça login para continuar.", "erro")
            return redirect(url_for("login"))
        return funcao(*args, **kwargs)
    return verificar


@app.route("/")
def index():
    return redirect(url_for("painel" if "email" in session else "login"))


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    """CRIAR CONTA: grava um item (linha) novo na tabela com put_item."""
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        confirmacao = request.form.get("confirmacao", "")

        if not nome or not email or not senha:
            flash("Preencha todos os campos.", "erro")
        elif len(senha) < 6:
            flash("A senha precisa ter pelo menos 6 caracteres.", "erro")
        elif senha != confirmacao:
            flash("As senhas não conferem.", "erro")
        else:
            try:
                tabela.put_item(
                    Item={
                        "email": email,
                        "nome": nome,
                        # NUNCA salvar a senha pura: guardamos só o HASH dela.
                        "senha_hash": generate_password_hash(senha),
                        "criado_em": datetime.now().isoformat(timespec="seconds"),
                    },
                    # Só grava se ainda NÃO existir usuário com esse e-mail
                    ConditionExpression="attribute_not_exists(email)",
                )
                flash("Conta criada! Agora faça login.", "ok")
                return redirect(url_for("login"))
            except ClientError as erro:
                if erro.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    flash("Já existe uma conta com esse e-mail.", "erro")
                else:
                    raise
    return render_template("cadastro.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """AUTENTICAR: busca o usuário no DynamoDB (get_item) e confere a senha."""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        resposta = tabela.get_item(Key={"email": email})
        usuario = resposta.get("Item")  # None se o e-mail não existir

        if usuario and check_password_hash(usuario["senha_hash"], senha):
            session["email"] = usuario["email"]
            flash(f"Bem-vindo(a), {usuario['nome']}!", "ok")
            return redirect(url_for("painel"))
        # Mensagem genérica: não contamos se o erro foi no e-mail ou na senha
        flash("E-mail ou senha inválidos.", "erro")
    return render_template("login.html")


@app.route("/painel")
@login_obrigatorio
def painel():
    """Área restrita: mostra os dados do usuário lidos do DynamoDB."""
    usuario = tabela.get_item(Key={"email": session["email"]}).get("Item")
    if not usuario:  # conta apagada enquanto estava logado
        session.clear()
        return redirect(url_for("login"))
    return render_template("painel.html", usuario=usuario, tabela=TABELA)


@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu da conta.", "ok")
    return redirect(url_for("login"))


if __name__ == "__main__":
    garantir_tabela()
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5002")), debug=True)
