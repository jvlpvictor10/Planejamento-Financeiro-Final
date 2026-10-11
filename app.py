import math
import os
import secrets
import sqlite3
import time
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory, g
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Em produção, aponte DB_PATH para um disco/volume persistente (ex.: /data/database.db)
DB_PATH = os.environ.get('DB_PATH', os.path.join(BASE_DIR, 'database.db'))
SCHEMA_PATH = os.path.join(BASE_DIR, 'schema.sql')

TOKEN_MAX_AGE = 60 * 60 * 24 * 30      # sessão dura 30 dias
MIN_PASSWORD_LEN = 4
MAX_LOGIN_ATTEMPTS = 10                # tentativas erradas por IP+usuário
LOGIN_LOCK_WINDOW = 15 * 60            # janela de 15 minutos


def load_secret_key():
    """Usa SECRET_KEY do ambiente; se não existir, cria e guarda uma chave local."""
    key = os.environ.get('SECRET_KEY')
    if key:
        return key
    key_dir = os.path.dirname(DB_PATH)
    os.makedirs(key_dir, exist_ok=True)
    key_path = os.path.join(key_dir, '.secret_key')
    try:
        with open(key_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        key = secrets.token_hex(32)
        with open(key_path, 'w', encoding='utf-8') as f:
            f.write(key)
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            pass
        return key


# static_folder=None: sem isso o Flask publicaria TODOS os arquivos da pasta
# (inclusive database.db e app.py) numa URL pública.
app = Flask(__name__, static_folder=None)
app.config['SECRET_KEY'] = load_secret_key()
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

if os.environ.get('TRUST_PROXY') == '1':
    # Atrás de proxy (Render, Railway...) o IP real vem no cabeçalho X-Forwarded-For
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'], salt='finapp-auth')


# ---------------------------------------------------------------- banco de dados

def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def get_db():
    if 'db' not in g:
        g.db = connect()
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = connect()
    cols = [r['name'] for r in conn.execute('PRAGMA table_info(recurring_items)')]
    if cols and 'sub_type' not in cols:
        # Banco criado pela versão antiga do schema (incompatível): guarda cópia e recria.
        conn.close()
        backup = DB_PATH + '.antigo'
        os.replace(DB_PATH, backup)
        print(f'[finapp] Banco antigo movido para {backup} e um novo foi criado.')
        conn = connect()
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        conn.executescript(f.read())
    conn.execute('PRAGMA journal_mode = WAL')
    conn.commit()
    conn.close()


init_db()


@app.after_request
def no_cache_api(resp):
    if request.path.startswith('/api/'):
        resp.headers['Cache-Control'] = 'no-store'
    return resp


# ---------------------------------------------------------------------- utilidades

def make_token(user_id, password_hash):
    # 'ph' amarra o token à senha atual: trocar a senha invalida os tokens antigos.
    return serializer.dumps({'uid': user_id, 'ph': password_hash[-16:]})


def auth_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        header = request.headers.get('Authorization', '')
        if not header.startswith('Bearer '):
            return jsonify({'error': 'Sessão inválida. Entre novamente.'}), 401
        try:
            payload = serializer.loads(header[7:], max_age=TOKEN_MAX_AGE)
        except (BadSignature, SignatureExpired):
            return jsonify({'error': 'Sessão expirada. Entre novamente.'}), 401
        user = get_db().execute(
            'SELECT id, name, username, password_hash FROM users WHERE id = ?',
            (payload.get('uid'),)
        ).fetchone()
        if not user or user['password_hash'][-16:] != payload.get('ph'):
            return jsonify({'error': 'Sessão expirada. Entre novamente.'}), 401
        g.user = user
        return view(*args, **kwargs)
    return wrapper


def public_user(row):
    return {'id': row['id'], 'name': row['name'], 'username': row['username']}


def to_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError('Valor numérico inválido')
    if not math.isfinite(number):
        raise ValueError('Valor numérico inválido')
    return number


def text(value, default=''):
    return default if value is None else str(value)


_failed_logins = {}


def login_blocked(key):
    now = time.time()
    attempts = [t for t in _failed_logins.get(key, []) if now - t < LOGIN_LOCK_WINDOW]
    if attempts:
        _failed_logins[key] = attempts
    else:
        _failed_logins.pop(key, None)
    return len(attempts) >= MAX_LOGIN_ATTEMPTS


# --------------------------------------------------------------------------- rotas

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')


# Arquivos públicos do app instalável (PWA). Lista fechada: nada além disso é servido.
PWA_FILES = {
    'manifest.webmanifest': 'application/manifest+json',
    'sw.js': 'application/javascript',
}
PWA_ICONS = {'icon-192.png', 'icon-512.png', 'icon-maskable-512.png', 'apple-touch-icon.png'}


@app.route('/manifest.webmanifest')
@app.route('/sw.js')
def pwa_file():
    name = request.path.lstrip('/')
    resp = send_from_directory(BASE_DIR, name, mimetype=PWA_FILES[name])
    # Evita que o navegador fique preso a uma versão velha do service worker
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


@app.route('/icons/<name>')
def pwa_icon(name):
    if name not in PWA_ICONS:
        return jsonify({'error': 'Não encontrado'}), 404
    return send_from_directory(os.path.join(BASE_DIR, 'icons'), name, max_age=86400)


@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    name = text(data.get('name')).strip()
    username = text(data.get('username')).strip().lower()
    password = data.get('password')

    if not name or not username or not isinstance(password, str) or not password:
        return jsonify({'error': 'Preencha todos os campos obrigatórios'}), 400
    if len(password) < MIN_PASSWORD_LEN:
        return jsonify({'error': f'A senha deve ter no mínimo {MIN_PASSWORD_LEN} caracteres'}), 400
    try:
        initial_balance = to_float(data.get('initial_balance', 0.0))
    except ValueError:
        return jsonify({'error': 'Saldo inicial inválido'}), 400

    pwd_hash = generate_password_hash(password)
    db = get_db()
    try:
        cur = db.execute(
            'INSERT INTO users (name, username, password_hash) VALUES (?, ?, ?)',
            (name, username, pwd_hash))
        user_id = cur.lastrowid
        db.execute('INSERT INTO user_settings (user_id, initial_balance) VALUES (?, ?)',
                   (user_id, initial_balance))
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify({'error': 'Nome de usuário já cadastrado'}), 409

    return jsonify({
        'message': 'Cadastrado com sucesso',
        'user': {'id': user_id, 'name': name, 'username': username},
        'token': make_token(user_id, pwd_hash),
    }), 201


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = text(data.get('username')).strip().lower()
    password = data.get('password')

    throttle_key = (request.remote_addr, username)
    if login_blocked(throttle_key):
        return jsonify({'error': 'Muitas tentativas. Aguarde alguns minutos e tente de novo.'}), 429

    user = get_db().execute(
        'SELECT id, name, username, password_hash FROM users WHERE username = ?',
        (username,)).fetchone()

    if not user or not isinstance(password, str) or not check_password_hash(user['password_hash'], password):
        _failed_logins.setdefault(throttle_key, []).append(time.time())
        return jsonify({'error': 'Usuário ou senha incorretos'}), 401

    _failed_logins.pop(throttle_key, None)
    return jsonify({
        'message': 'Login com sucesso',
        'user': public_user(user),
        'token': make_token(user['id'], user['password_hash']),
    })


@app.route('/api/auth/change-password', methods=['POST'])
@auth_required
def change_password():
    data = request.get_json(silent=True) or {}
    current = data.get('current_password')
    new_password = data.get('new_password')

    if not isinstance(current, str) or not isinstance(new_password, str):
        return jsonify({'error': 'Informe a senha atual e a nova senha'}), 400
    if len(new_password) < MIN_PASSWORD_LEN:
        return jsonify({'error': f'A nova senha deve ter no mínimo {MIN_PASSWORD_LEN} caracteres'}), 400
    # 403 (e não 401) para o app não confundir com "sessão expirada"
    if not check_password_hash(g.user['password_hash'], current):
        return jsonify({'error': 'Senha atual incorreta'}), 403

    pwd_hash = generate_password_hash(new_password)
    db = get_db()
    db.execute('UPDATE users SET password_hash = ? WHERE id = ?', (pwd_hash, g.user['id']))
    db.commit()
    return jsonify({'message': 'Senha alterada com sucesso!',
                    'token': make_token(g.user['id'], pwd_hash)})


@app.route('/api/data', methods=['GET'])
@auth_required
def get_user_data():
    db = get_db()
    user_id = g.user['id']

    db.execute('INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)', (user_id,))
    db.commit()
    settings = db.execute(
        'SELECT initial_balance, revision FROM user_settings WHERE user_id = ?',
        (user_id,)).fetchone()

    balance = settings['initial_balance']
    transactions = []
    for r in db.execute('SELECT * FROM transactions WHERE user_id = ? ORDER BY sort_order ASC', (user_id,)):
        t = {
            'id': r['id'],
            'type': r['type'],
            'category': r['category'],
            'subType': r['sub_type'],
            'description': r['description'],
            'amount': r['amount'],
            'date': r['tx_date'],
            'isAuto': bool(r['is_auto']),
            'isSettled': bool(r['is_settled']),
        }
        transactions.append(t)
        if t['isSettled']:
            balance += t['amount'] if t['type'] == 'receita' else -t['amount']

    recurring_incomes, fixed_costs = [], []
    for r in db.execute('SELECT * FROM recurring_items WHERE user_id = ? ORDER BY rowid', (user_id,)):
        item = {
            'id': r['id'],
            'description': r['description'],
            'amount': r['amount'],
            'recurrenceDay': r['recurrence_day'],
        }
        if r['item_type'] == 'income':
            item['subType'] = r['sub_type'] or 'Serviço'
            item['lastCreditedMonth'] = r['last_processed_month']
            recurring_incomes.append(item)
        else:
            item['lastDebitedMonth'] = r['last_processed_month']
            fixed_costs.append(item)

    return jsonify({
        'user': public_user(g.user),
        'balance': round(balance, 2),
        'revision': settings['revision'],
        'transactions': transactions,
        'recurringIncomes': recurring_incomes,
        'fixedCosts': fixed_costs,
    })


def parse_transactions(items):
    rows = []
    for index, t in enumerate(items):
        tx_type = t['type']
        if tx_type not in ('receita', 'gasto'):
            raise ValueError('Tipo de lançamento inválido')
        rows.append((
            text(t['id']), tx_type, text(t.get('category')),
            None if t.get('subType') is None else str(t['subType']),
            text(t['description']), to_float(t['amount']), text(t['date']),
            1 if t.get('isAuto') else 0,
            0 if t.get('isSettled') is False else 1,
            index,
        ))
    return rows


def parse_recurring(items, item_type, month_key):
    rows = []
    for r in items:
        day = int(r['recurrenceDay'])
        if not 1 <= day <= 31:
            raise ValueError('Dia de recorrência inválido')
        if item_type == 'income':
            category, sub_type = 'Receita', text(r.get('subType'), 'Serviço')
        else:
            category, sub_type = 'Custos fixos', None
        rows.append((text(r['id']), item_type, category, sub_type, text(r['description']),
                     to_float(r['amount']), day, text(r.get(month_key))))
    return rows


@app.route('/api/sync', methods=['POST'])
@auth_required
def sync_user_data():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Dados inválidos'}), 400

    user_id = g.user['id']
    try:
        initial_balance = to_float(data['initial_balance'])
        revision = int(data['revision'])
        for key in ('transactions', 'recurringIncomes', 'fixedCosts'):
            if not isinstance(data[key], list):
                raise ValueError(key)
        tx_rows = parse_transactions(data['transactions'])
        income_rows = parse_recurring(data['recurringIncomes'], 'income', 'lastCreditedMonth')
        expense_rows = parse_recurring(data['fixedCosts'], 'expense', 'lastDebitedMonth')
    except (KeyError, TypeError, ValueError, AttributeError):
        return jsonify({'error': 'Dados inválidos'}), 400

    db = get_db()
    try:
        db.execute('INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)', (user_id,))
        # Só grava se o aparelho estiver com a versão mais recente dos dados.
        cur = db.execute(
            'UPDATE user_settings SET initial_balance = ?, revision = revision + 1 '
            'WHERE user_id = ? AND revision = ?',
            (initial_balance, user_id, revision))
        if cur.rowcount != 1:
            db.rollback()
            return jsonify({'error': 'Os dados foram alterados em outro aparelho.'}), 409

        db.execute('DELETE FROM transactions WHERE user_id = ?', (user_id,))
        db.executemany(
            'INSERT OR REPLACE INTO transactions '
            '(user_id, id, type, category, sub_type, description, amount, tx_date, is_auto, is_settled, sort_order) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            [(user_id,) + row for row in tx_rows])

        db.execute('DELETE FROM recurring_items WHERE user_id = ?', (user_id,))
        db.executemany(
            'INSERT OR REPLACE INTO recurring_items '
            '(user_id, id, item_type, category, sub_type, description, amount, recurrence_day, last_processed_month) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            [(user_id,) + row for row in income_rows + expense_rows])
        db.commit()
    except sqlite3.Error:
        db.rollback()
        app.logger.exception('Falha ao sincronizar dados do usuário %s', user_id)
        return jsonify({'error': 'Não foi possível salvar os dados'}), 500

    return jsonify({'status': 'synced', 'revision': revision + 1})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
