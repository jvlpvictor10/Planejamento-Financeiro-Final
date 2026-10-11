# App de Planejamento Financeiro (multi-usuário)

Backend em Flask + SQLite que guarda contas e lançamentos na nuvem. Entrando com o mesmo
usuário e senha em qualquer celular ou computador, você vê os mesmos dados.

## Como funciona
- `index.html`: o app. Fala com o servidor pelas rotas `/api/...` (mesmo endereço que serve a página).
- `app.py`: servidor. Login por token (válido por 30 dias), senhas criptografadas (hash do Werkzeug),
  cada usuário só acessa os próprios dados.
- `schema.sql`: tabelas do banco (usuários, lançamentos, custos fixos, rendas recorrentes).
- `manifest.webmanifest`, `sw.js` e a pasta `icons/`: fazem o app poder ser instalado no celular.

**Importante:** o app só funciona aberto pelo endereço do servidor (ex.: `http://localhost:5000`
ou o link da hospedagem). Abrir o `index.html` direto do computador não funciona.

## Instalar no celular (ícone na tela inicial)
O app é um PWA. **Só aparece a opção de instalar quando aberto por `https://`** (o link da
hospedagem) ou por `localhost`. Por `http://IP-DO-PC:5000` na rede local o navegador não oferece instalar.

- **Android (Chrome):** abra o link do app, toque no menu ⋮ e em **Instalar app** (ou **Adicionar à tela inicial**).
- **iPhone (Safari):** abra o link, toque em **Compartilhar** e em **Adicionar à Tela de Início**.
  Precisa ser o Safari.

Sem internet, a tela do app abre, mas as contas e os lançamentos só carregam com conexão,
porque ficam guardados no servidor. Atualizações do app chegam sozinhas na próxima vez que você abrir com internet.

## Rodar localmente
```bash
pip install -r requirements.txt
python app.py
```
Acesse `http://localhost:5000`. Para testar em outro aparelho da mesma rede Wi-Fi, use
`http://IP-DO-SEU-PC:5000`.

## Variáveis de ambiente
| Variável | Para que serve |
|---|---|
| `SECRET_KEY` | Chave que assina os logins. Defina um texto longo e aleatório em produção. Se mudar, todos precisam entrar de novo. |
| `DB_PATH` | Caminho do arquivo do banco (ex.: `/data/database.db`). Aponte para um disco persistente. |
| `TRUST_PROXY` | Use `1` em hospedagens com proxy (Render, Railway...) para o limite de tentativas de login ver o IP real. |
| `PORT` | Porta do servidor (a hospedagem costuma definir sozinha). |

## Hospedar online
Comando de início: `gunicorn app:app`. Comando de build: `pip install -r requirements.txt`.

Atenção ao **disco**: o banco é um arquivo SQLite. Se a hospedagem apaga os arquivos a cada
deploy ou reinício, todas as contas somem. Confira se o plano tem disco/volume persistente e
aponte `DB_PATH` para ele (ou use um serviço de hospedagem que mantenha os arquivos).
Faça backup copiando o arquivo do banco de vez em quando.

## Vários aparelhos na mesma conta
- Os dados são salvos automaticamente a cada alteração.
- Ao voltar para o app, ele busca o que foi alterado em outro aparelho.
- Se dois aparelhos alterarem ao mesmo tempo, o servidor não sobrescreve: o aparelho mais
  atrasado recebe um aviso e carrega a versão mais nova.

## Dados da versão antiga
Se o navegador ainda tiver dados da versão antiga (salvos só no aparelho), ao entrar com a mesma
conta o app oferece enviá-los para a nuvem uma única vez.
