# Servidor Backend do App de Planejamento Financeiro

Este pacote contém o código de backend completo para transformar o app de planejamento financeiro em um serviço multi-usuário profissional com banco de dados centralizado e autenticação segura de login e senha.

## Estrutura dos Arquivos:
- `app.py`: Servidor REST em Python/Flask com rotas de autenticação (hash de senhas), registro, lançamentos e cálculo de saldo.
- `schema.sql`: Estrutura do banco de dados relacional (SQLite/PostgreSQL) com tabelas de usuários, transações, custos fixos e rendas recorrentes.
- `requirements.txt`: Dependências necessárias.

## Como Executar Localmente:
1. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
2. Inicie o servidor:
   ```bash
   python app.py
   ```
3. O servidor estará ativo em `http://localhost:5000`.

## Como Hospedar Gratuitamente na Nuvem:
Você pode subir esse projeto para ter um link online permanente onde você, sua namorada e seu pai podem acessar de qualquer lugar:
- **Render.com** ou **Railway.app**: Crie uma conta gratuita, conecte seu repositório GitHub com estes arquivos e clique em Deploy.
- As senhas são criptografadas com hash PBKDF2/SHA256 para total privacidade entre as contas.
