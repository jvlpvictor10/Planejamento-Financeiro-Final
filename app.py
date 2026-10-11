from flask import Flask, request, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.db')
SCHEMA_PATH = os.path.join(BASE_DIR, 'schema.sql')

app = Flask(__name__, static_folder=BASE_DIR)
app.config['SECRET_KEY'] = 'chave_secreta_finapp_2026'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    if os.path.exists(SCHEMA_PATH):
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            conn.executescript(f.read())
        conn.commit()
    conn.close()

# Inicializa o banco de dados imediatamente na inicialização
if not os.path.exists(DB_PATH):
    init_db()

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    name = data.get('name')
    username = (data.get('username') or '').strip().lower()
    password = data.get('password')
    initial_balance = float(data.get('initial_balance', 0.0))

    if not name or not username or not password:
        return jsonify({'error': 'Preencha todos os campos obrigatórios'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
    if cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Nome de usuário já cadastrado'}), 409

    pwd_hash = generate_password_hash(password)
    cursor.execute('INSERT INTO users (name, username, password_hash) VALUES (?, ?, ?)',
                   (name, username, pwd_hash))
    user_id = cursor.lastrowid

    cursor.execute('INSERT OR REPLACE INTO user_settings (user_id, initial_balance) VALUES (?, ?)',
                   (user_id, initial_balance))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Cadastrado com sucesso', 'user': {'id': user_id, 'name': name, 'username': username}}), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip().lower()
    password = data.get('password')

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, username, password_hash FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()

    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Usuário ou senha incorretos'}), 401

    return jsonify({
        'message': 'Login com sucesso',
        'user': {'id': user['id'], 'name': user['name'], 'username': user['username']}
    })

@app.route('/api/auth/change-password', methods=['POST'])
def change_password():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    new_password = data.get('new_password')
    if not user_id or not new_password or len(new_password) < 4:
        return jsonify({'error': 'A nova senha deve ter no mínimo 4 caracteres'}), 400

    pwd_hash = generate_password_hash(new_password)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (pwd_hash, user_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Senha alterada com sucesso!'})

@app.route('/api/data/<int:user_id>', methods=['GET'])
def get_user_data(user_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT initial_balance FROM user_settings WHERE user_id = ?', (user_id,))
    settings = cursor.fetchone()
    initial_balance = settings['initial_balance'] if settings else 0.0

    cursor.execute('SELECT * FROM transactions WHERE user_id = ? ORDER BY tx_date DESC', (user_id,))
    tx_rows = cursor.fetchall()
    transactions = []
    balance = initial_balance

    for r in tx_rows:
        is_settled = bool(r['is_settled']) if 'is_settled' in r.keys() else True
        t = {
            'id': r['id'],
            'type': r['type'],
            'category': r['category'],
            'subType': r['sub_type'],
            'description': r['description'],
            'amount': r['amount'],
            'date': r['tx_date'],
            'isAuto': bool(r['is_auto']),
            'isSettled': is_settled
        }
        transactions.append(t)
        if is_settled:
            if t['type'] == 'receita':
                balance += t['amount']
            else:
                balance -= t['amount']

    cursor.execute('SELECT * FROM recurring_items WHERE user_id = ?', (user_id,))
    rec_rows = cursor.fetchall()
    recurring_incomes = []
    fixed_costs = []

    for r in rec_rows:
        item = {
            'id': r['id'],
            'description': r['description'],
            'amount': r['amount'],
            'recurrenceDay': r['recurrence_day'],
            'lastDebitedMonth': r['last_processed_month'],
            'lastCreditedMonth': r['last_processed_month'],
            'subType': r['sub_type'],
            'category': r['category']
        }
        if r['item_type'] == 'income':
            recurring_incomes.append(item)
        else:
            fixed_costs.append(item)

    conn.close()
    return jsonify({
        'balance': balance,
        'initial_balance': initial_balance,
        'transactions': transactions,
        'recurringIncomes': recurring_incomes,
        'fixedCosts': fixed_costs
    })

@app.route('/api/sync/<int:user_id>', methods=['POST'])
def sync_user_data(user_id):
    data = request.get_json() or {}
    conn = get_db()
    cursor = conn.cursor()

    if 'initial_balance' in data:
        cursor.execute('INSERT OR REPLACE INTO user_settings (user_id, initial_balance) VALUES (?, ?)',
                       (user_id, float(data['initial_balance'])))

    if 'transactions' in data:
        cursor.execute('DELETE FROM transactions WHERE user_id = ?', (user_id,))
        for t in data['transactions']:
            is_settled_val = 1 if t.get('isSettled', True) else 0
            cursor.execute('INSERT INTO transactions (id, user_id, type, category, sub_type, description, amount, tx_date, is_auto, is_settled) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                           (str(t['id']), user_id, t['type'], t.get('category', ''), t.get('subType', ''),
                            t['description'], float(t['amount']), t['date'], 1 if t.get('isAuto') else 0, is_settled_val))

    if 'recurringIncomes' in data:
        cursor.execute("DELETE FROM recurring_items WHERE user_id = ? AND item_type = 'income'", (user_id,))
        for inc in data['recurringIncomes']:
            cursor.execute("INSERT INTO recurring_items (id, user_id, item_type, category, sub_type, description, amount, recurrence_day, last_processed_month) VALUES (?, ?, 'income', 'Receita', ?, ?, ?, ?, ?)",
                           (str(inc['id']), user_id, inc.get('subType', 'Serviço'), inc['description'], float(inc['amount']),
                            int(inc['recurrenceDay']), inc.get('lastCreditedMonth', '')))

    if 'fixedCosts' in data:
        cursor.execute("DELETE FROM recurring_items WHERE user_id = ? AND item_type = 'expense'", (user_id,))
        for fc in data['fixedCosts']:
            cursor.execute("INSERT INTO recurring_items (id, user_id, item_type, category, sub_type, description, amount, recurrence_day, last_processed_month) VALUES (?, ?, 'expense', 'Custos fixos', NULL, ?, ?, ?, ?)",
                           (str(fc['id']), user_id, fc['description'], float(fc['amount']),
                            int(fc['recurrenceDay']), fc.get('lastDebitedMonth', '')))

    conn.commit()
    conn.close()
    return jsonify({'status': 'synced'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
