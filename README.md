# Atividades LocalStack — Guia passo a passo

Projeto com as 3 atividades da aula de LocalStack (Computação em Nuvem), feito em
**Python + Flask + boto3** (boto3 é o SDK oficial da AWS para Python).

| Pasta | Atividade | Serviço AWS simulado |
|---|---|---|
| `atividade1-s3/` | #1 Upload, listagem e download de imagens | **S3** |
| `atividade2-dynamodb/` | #2 Cadastro e login de usuários | **DynamoDB** |
| `atividade3-lambda/` | #3 Função acionada por upload que processa a imagem | **Lambda + S3** |

```
Navegador ──► App Flask (Python) ──boto3──► LocalStack (porta 4566) ──► S3 / DynamoDB / Lambda
                                                (container Docker)
```

A ideia central para explicar: **o código é o mesmo que rodaria na AWS de verdade**. A única
diferença é o `endpoint_url="http://localhost:4566"`, que faz o boto3 falar com o LocalStack
em vez da Amazon.

> ✅ Testado do zero num Ubuntu 24.04 limpo (mesmos passos deste guia) com LocalStack 4.12.0:
> as 3 atividades funcionaram, inclusive a Lambda gerando a imagem em tons de cinza 300x200.

---

## ⚠️ Leia antes: versão do LocalStack

Em **março de 2026** o LocalStack mudou: a imagem `localstack/localstack:latest` agora **exige
uma conta e um token** (`LOCALSTACK_AUTH_TOKEN`). O comando do slide
(`docker run ... localstack/localstack`) baixa essa versão nova e **não sobe sem token**.

Por isso o `docker-compose.yml` deste projeto usa a versão **`4.12`**, a última da edição
Community (gratuita) que roda **sem cadastro**. Já foi testado: ela tem S3, DynamoDB e Lambda
funcionando.

<details>
<summary>Plano B (só se a 4.12 der problema): conta gratuita + token</summary>

1. Crie uma conta em <https://app.localstack.cloud> (existe plano gratuito para uso não
   comercial, e um plano de estudante pelo GitHub Student Developer Pack).
2. No painel, vá em **Auth Tokens** e copie o seu token.
3. Suba o LocalStack assim:
   ```bash
   export LOCALSTACK_AUTH_TOKEN="cole-seu-token-aqui"
   LOCALSTACK_TAG=latest docker compose up -d
   ```
Todo o resto do guia continua igual.
</details>

---

## Parte 0 — Preparar o ambiente (cada integrante faz no seu PC)

> **WSL2:** todos os comandos abaixo são digitados **no terminal do Ubuntu (WSL)**, não no
> PowerShell. **Linux nativo:** no terminal normal.

### 0.1 Docker

**WSL2 (com Docker Desktop no Windows):**
1. Abra o Docker Desktop no Windows (ele precisa estar aberto sempre que for usar).
2. Em **Settings → Resources → WSL Integration**, ligue a chave da sua distro (ex.: Ubuntu)
   e clique em **Apply & restart**.
3. No terminal do WSL, teste:
   ```bash
   docker run --rm hello-world
   docker compose version
   ```

**Linux nativo:** instale o Docker Engine seguindo a documentação oficial
(<https://docs.docker.com/engine/install/>) e depois libere seu usuário para usar o Docker
sem `sudo`:
```bash
sudo usermod -aG docker $USER
```
Saia e entre de novo na sessão (ou reinicie) e teste com `docker run --rm hello-world`.
Se `docker compose version` não funcionar, instale o plugin `docker-compose-plugin`
(ou `docker-compose-v2` no Ubuntu).

### 0.2 Pacotes do sistema

Ubuntu/Debian (inclusive no WSL):
```bash
sudo apt update && sudo apt install -y git python3-venv python3-pip unzip curl
```
(Fedora: `sudo dnf install -y git python3 python3-pip unzip curl` · Arch: `sudo pacman -S git python python-pip unzip curl`)

### 0.3 AWS CLI v2

O slide usa `sudo apt install awscli`, mas **no Ubuntu 24.04 esse pacote não existe mais**.
Use o instalador oficial (funciona em qualquer Linux):
```bash
cd /tmp
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip -q awscliv2.zip && sudo ./aws/install
cd ~ && hash -r
aws --version
```
Tem que aparecer `aws-cli/2.x`. Se você já tinha o AWS CLI v1 do apt (comum no Ubuntu 22.04),
não precisa desinstalar: o v2 fica em `/usr/local/bin` e passa na frente. O v1 é antigo demais
para os scripts da atividade 3 (não tem, por exemplo, o `aws logs tail`).
(Em PC com processador ARM troque `x86_64` por `aarch64` no link.)

### 0.4 Atalho `awslocal`

Crie um atalho `awslocal`: é o `aws` apontando para o LocalStack e já com as credenciais
falsas, que o LocalStack aceita. Também desligue o "paginador" do CLI:
```bash
echo 'alias awslocal="AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 aws --endpoint-url=http://localhost:4566"' >> ~/.bashrc
echo 'export AWS_PAGER=""' >> ~/.bashrc
source ~/.bashrc
```
Daqui pra frente, `awslocal s3 ls` é o mesmo que `aws --endpoint-url=http://localhost:4566 s3 ls`
usando as credenciais `test`.

**Não precisa rodar o `aws configure` do slide.** O atalho, os apps e os scripts já passam as
credenciais `test` sozinhos. Assim, se você já tiver um `~/.aws` configurado (de outra
disciplina ou de uma conta real), nada dele é sobrescrito.

### 0.5 Pegar o projeto

Clone o repositório dentro da sua home do Linux:
```bash
git clone https://github.com/hugbrl09/atividades-localstack.git ~/atividades-localstack
cd ~/atividades-localstack
```

**No WSL, rode o clone no terminal do Ubuntu e trabalhe na home do Linux (`~`), não em
`/mnt/c/...`**: é bem mais rápido e evita problemas de permissão e de quebra de linha.

Para pegar atualizações que alguém do grupo enviou depois: `git pull`.

Se o repositório estiver privado, o GitHub pede login no clone. Senha normal não funciona:
use `gh auth login` (GitHub CLI) ou um *personal access token* no lugar da senha.

### 0.6 Ambiente virtual Python (venv)

```bash
cd ~/atividades-localstack
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
O `(.venv)` aparece no começo da linha do terminal. **Em todo terminal novo**, entre na pasta
e rode `source .venv/bin/activate` de novo.

---

## Parte 1 — Subir o LocalStack

Na pasta do projeto:
```bash
docker compose up -d
```
Na primeira vez ele baixa a imagem (~1 GB). Espere uns segundos e confira:
```bash
curl -s localhost:4566/_localstack/health
```
Tem que aparecer `"edition": "community"`, `"version": "4.12.0"` e os serviços `s3`,
`dynamodb` e `lambda` como `"available"` (ou `"running"`).

O que o `docker-compose.yml` faz (para explicar):
- **imagem `localstack/localstack:4.12`** — o simulador da AWS.
- **porta 4566** — endpoint único: todos os serviços (S3, DynamoDB, Lambda…) respondem nela.
- **`SERVICES=s3,dynamodb,lambda,iam,sts,logs`** — liga só o que vamos usar (igual ao slide 13).
- **volume `/var/run/docker.sock`** — dá ao LocalStack acesso ao Docker, porque ele cria um
  container para executar cada função Lambda (atividade 3).

Comandos úteis: `docker compose logs -f` (ver logs) · `docker compose down` (desligar).

> A edição Community **não salva nada** quando o container é desligado: depois de um
> `docker compose down` os buckets e tabelas somem. Os apps recriam o bucket/tabela sozinhos;
> na atividade 3 basta rodar o `deploy.sh` de novo.

---

## Atividade #1 — S3: upload, listagem e download

**Rodar** (LocalStack ligado e `.venv` ativado):
```bash
python atividade1-s3/app.py
```
Abra <http://localhost:5001> no navegador (no WSL pode abrir no navegador do Windows mesmo).

**Testar:** escolha uma imagem → **Enviar para o S3** → ela aparece na tabela com prévia,
tamanho e data → clique em **Baixar**.

**Provar pelo terminal que o arquivo está mesmo no "S3"** (em outro terminal):
```bash
awslocal s3 ls
awslocal s3 ls s3://atividade1-imagens/
```

**Como funciona** (`atividade1-s3/app.py`):

| Ação no site | Chamada no S3 | Equivalente no AWS CLI |
|---|---|---|
| App iniciando (`garantir_bucket`) | `create_bucket` | `awslocal s3 mb s3://atividade1-imagens` |
| Enviar (`/upload`) | `put_object(Bucket, Key, Body, ContentType)` | `awslocal s3 cp foto.png s3://atividade1-imagens/` |
| Listar (`/`) | `list_objects_v2(Bucket)` | `awslocal s3 ls s3://atividade1-imagens/` |
| Baixar (`/download/<nome>`) | `get_object(Bucket, Key)` | `awslocal s3 cp s3://atividade1-imagens/foto.png .` |

Conceitos:
- **Bucket** = "pasta raiz"/contêiner. **Objeto** = o arquivo. **Key** = o nome do objeto no bucket.
- O S3 não é um disco: é uma **API HTTP**. Cada operação acima é uma requisição para
  `localhost:4566`.
- Segurança básica: aceita só extensões de imagem, limita a 10 MB e limpa o nome do arquivo
  com `secure_filename`.

---

## Atividade #2 — DynamoDB: cadastro e login

**Rodar:**
```bash
python atividade2-dynamodb/app.py
```
Abra <http://localhost:5002>. (Na primeira vez o app demora alguns segundos para abrir, porque
o LocalStack liga o motor do DynamoDB só quando recebe a primeira chamada.)

**Testar:** **Cadastre-se** → crie uma conta → faça login com senha **errada** (recusa) →
login com a senha certa (entra na área logada, que mostra os dados lidos do DynamoDB) →
**Sair** → tente cadastrar o **mesmo e-mail** de novo (recusa).

**Provar pelo terminal:**
```bash
awslocal dynamodb list-tables
awslocal dynamodb scan --table-name usuarios
```
Repare que o campo `senha_hash` **não é a senha**, é um hash (`scrypt:...`).

**Como funciona** (`atividade2-dynamodb/app.py`):
- **Tabela `usuarios`** com **chave de partição (partition key) `email`**. Só a chave é
  obrigatória; `nome`, `senha_hash` e `criado_em` são atributos livres (sem esquema fixo →
  NoSQL).
- **Cadastro** → `put_item` com `ConditionExpression="attribute_not_exists(email)"`: o
  DynamoDB só grava se ainda não existir esse e-mail, senão dá `ConditionalCheckFailedException`
  e mostramos "Já existe uma conta".
- **Senha** → nunca é salva pura: `generate_password_hash` (algoritmo scrypt + salt).
- **Login** → `get_item(Key={"email": ...})` busca direto pela chave (rápido, sem varrer a
  tabela) e `check_password_hash` compara a senha digitada com o hash salvo.
- **Sessão** → depois do login o e-mail fica na `session` do Flask (cookie assinado com a
  `secret_key`). A rota `/painel` só abre logado (decorator `login_obrigatorio`).
- Mensagem de erro genérica ("E-mail ou senha inválidos") para não revelar quais e-mails
  existem.

---

## Atividade #3 — Lambda acionada por upload no S3

```
 upload ──► [S3: imagens-originais] ──evento "ObjectCreated"──► [Lambda: processa-imagem]
                                                                        │
                                       preto e branco + máx. 300x300    ▼
                                                            [S3: imagens-processadas]
```

**Rodar** (LocalStack ligado e `.venv` ativado, na pasta do projeto):
```bash
chmod +x atividade3-lambda/*.sh
./atividade3-lambda/deploy.sh
./atividade3-lambda/testar.sh
```
O `testar.sh` envia a `exemplo.png` (colorida, 600x400) para o bucket de origem, espera a
Lambda rodar e baixa o resultado (cinza, 300x200) em `atividade3-lambda/resultado/`.
Para ver a imagem: no WSL `explorer.exe "$(wslpath -w atividade3-lambda/resultado)"` (abre a
pasta no Explorer do Windows) · no Linux `xdg-open atividade3-lambda/resultado/exemplo.png`.

Testar com uma foto sua: `./atividade3-lambda/testar.sh ~/minha-foto.jpg`

**Ver os logs da função** (os `print` do código aparecem aqui):
```bash
awslocal logs tail /aws/lambda/processa-imagem
```

**Demonstração bônus (atividades 1 + 3 juntas):** rode o site da atividade 1 usando o bucket
que tem o gatilho:
```bash
BUCKET_NAME=imagens-originais python atividade1-s3/app.py
```
Cada imagem enviada pelo site dispara a Lambda. Confira com
`awslocal s3 ls s3://imagens-processadas/`.

**Como funciona — o `deploy.sh` faz 6 passos:**
1. **Cria os buckets** `imagens-originais` e `imagens-processadas`.
2. **Cria o papel IAM** `lambda-role`. Na AWS real a Lambda precisa de um papel com
   permissões; o LocalStack não confere permissões, mas criamos para ficar igual à AWS.
3. **Empacota** `lambda_function.py` + a biblioteca **Pillow** num `function.zip`. A Pillow é
   baixada já compilada para o Linux da Lambda (`--platform manylinux...`), porque a função
   não roda no seu PC, roda no ambiente da Lambda.
4. **Cria a função** (`aws lambda create-function`) com runtime `python3.12`, handler
   `lambda_function.lambda_handler` (= arquivo.função) e a variável de ambiente
   `BUCKET_DESTINO`.
5. **Dá permissão** para o serviço S3 invocar a função (`lambda add-permission`).
6. **Liga o gatilho** (`s3api put-bucket-notification-configuration`): todo evento
   `s3:ObjectCreated:*` no bucket de origem chama a função.

**O código da função** (`atividade3-lambda/lambda_function.py`):
- `lambda_handler(event, context)` recebe o **evento do S3**, que traz em `Records` o nome do
  bucket e a key do arquivo enviado.
- Baixa a imagem (`get_object`), converte para tons de cinza e reduz para no máximo 300x300
  com a Pillow, e salva no bucket de destino (`put_object`).
- **Por que outro bucket?** Se salvasse no mesmo bucket, o novo arquivo dispararia a Lambda de
  novo → loop infinito.
- **Onde ela roda?** O LocalStack cria um container Docker com a imagem oficial do Lambda
  Python (`public.ecr.aws/lambda/python:3.12`). Rode `docker ps` logo depois de um upload e
  você vê esse container. Na primeira vez ele baixa a imagem, então demora mais.

---

## Problemas comuns

| Erro / sintoma | Solução |
|---|---|
| `Cannot connect to the Docker daemon` | WSL: abra o Docker Desktop e confira a WSL Integration. Linux: `sudo systemctl start docker` |
| `permission denied ... docker.sock` | Linux: `sudo usermod -aG docker $USER` e saia/entre da sessão |
| LocalStack fecha pedindo token / "license" | Está usando a imagem nova. Confira se o compose está com `4.12` e se não exportou `LOCALSTACK_TAG=latest` |
| `Could not connect to the endpoint URL: "http://localhost:4566/..."` | LocalStack não está rodando: `docker compose ps` e `docker compose logs` |
| `Unable to locate credentials` | Use o `awslocal` em vez de `aws` puro (passo 0.4); ele já leva as credenciais `test` |
| `aws: error: argument operation: Invalid choice` (ex.: no `logs tail`) | Está usando o AWS CLI v1. Instale o v2 (passo 0.3) e rode `hash -r` |
| `ModuleNotFoundError: No module named 'flask'` ou `externally-managed-environment` | Esqueceu de ativar o venv: `source .venv/bin/activate` |
| `/usr/bin/env: 'bash\r': No such file or directory` | O script ganhou quebra de linha do Windows: `sed -i 's/\r$//' atividade3-lambda/*.sh` |
| `Permission denied` ao rodar `./deploy.sh` | `chmod +x atividade3-lambda/*.sh` |
| `Address already in use` (porta 5001/5002 ocupada) | Use outra porta: `PORT=5011 python atividade1-s3/app.py` |
| Navegador do Windows não abre o site do WSL | Rode com `HOST=0.0.0.0 python atividade1-s3/app.py` e tente de novo |
| `testar.sh` diz que a imagem não apareceu em 90s | 1ª execução baixando a imagem do Python. Veja `awslocal logs tail /aws/lambda/processa-imagem` e `docker compose logs --tail 50`, e rode o teste de novo |
| Bucket/tabela sumiram | Foi feito `docker compose down` (Community não persiste). Rode os apps / `deploy.sh` de novo |

---

## Perguntas frequentes

**O que é o LocalStack e por que usar?** Um emulador da AWS que roda num container Docker.
Permite desenvolver e testar sem conta na AWS, sem custo e sem internet. Todos os serviços
respondem num endpoint só, a porta 4566.

**O que mudaria para rodar na AWS de verdade?** Tirar o `endpoint_url` (e o
`--endpoint-url` do CLI) e usar credenciais reais de um usuário/papel IAM. O resto do código
é igual.

**Por que as credenciais são `test`/`test`?** O LocalStack não valida credenciais. Os SDKs
exigem que exista alguma, então usamos valores falsos.

**Diferença entre bucket, objeto e key?** Bucket é o contêiner; objeto é o arquivo (dados +
metadados); key é o nome único do objeto dentro do bucket.

**Por que o DynamoDB é NoSQL? O que é partition key?** Não tem esquema fixo: só a chave
primária é obrigatória, cada item pode ter atributos diferentes. A partition key (aqui o
`email`) identifica o item e define onde ele é armazenado; buscar por ela (`get_item`) é
muito rápido.

**Por que `get_item` e não `scan`?** O `scan` lê a tabela inteira; o `get_item` vai direto no
item pela chave.

**Por que guardar hash e não a senha?** Se o banco vazar, ninguém descobre as senhas. O hash
não pode ser revertido; no login geramos o hash da senha digitada e comparamos.

**O que é serverless / Lambda?** Você só envia o código; a AWS cuida do servidor, executa a
função quando chega um evento e cobra só pelo tempo de execução.

**O que é o handler e o `event`?** O handler é a função que o Lambda chama
(`lambda_handler`). O `event` é um JSON com os dados de quem disparou; no caso do S3, o
bucket e o nome do arquivo.

**Por que a Pillow vai dentro do zip?** A Lambda só tem a biblioteca padrão do Python e o
boto3. Qualquer outra dependência precisa ir no pacote (ou numa *Layer*, que no LocalStack é
recurso pago).

**O slide fala de `DATA_DIR` e `LAMBDA_EXECUTOR`. Por que não usaram?** Essas variáveis são
de versões antigas (1.x). Desde o LocalStack 2.0 o Lambda sempre roda em container Docker
(não existe mais `LAMBDA_EXECUTOR`), e a persistência virou `PERSISTENCE=1`, que é da versão
paga.

---

## Cola rápida

```bash
# todo dia, na pasta do projeto
docker compose up -d
source .venv/bin/activate

python atividade1-s3/app.py          # http://localhost:5001
python atividade2-dynamodb/app.py    # http://localhost:5002
./atividade3-lambda/deploy.sh && ./atividade3-lambda/testar.sh

# conferir pelo terminal
awslocal s3 ls
awslocal dynamodb scan --table-name usuarios
awslocal lambda list-functions
awslocal logs tail /aws/lambda/processa-imagem

# desligar tudo
docker compose down
```
