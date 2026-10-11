-- Banco de dados do App de Planejamento Financeiro (multi-usuário)

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- revision: contador que sobe a cada gravação. Evita que um aparelho com
-- dados antigos sobrescreva, sem querer, alterações feitas em outro aparelho.
CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY,
    initial_balance REAL NOT NULL DEFAULT 0.0,
    revision INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Os ids dos lançamentos são gerados pelo navegador (ex.: 'tx-1760000000000'),
-- por isso são TEXT e únicos apenas dentro de cada usuário.
CREATE TABLE IF NOT EXISTS transactions (
    user_id INTEGER NOT NULL,
    id TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('receita', 'gasto')),
    category TEXT NOT NULL DEFAULT '',
    sub_type TEXT,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    tx_date TEXT NOT NULL,
    is_auto INTEGER NOT NULL DEFAULT 0,
    is_settled INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_transactions_user_order
    ON transactions (user_id, sort_order);

CREATE TABLE IF NOT EXISTS recurring_items (
    user_id INTEGER NOT NULL,
    id TEXT NOT NULL,
    item_type TEXT NOT NULL CHECK(item_type IN ('income', 'expense')),
    category TEXT,
    sub_type TEXT,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    recurrence_day INTEGER NOT NULL CHECK(recurrence_day BETWEEN 1 AND 31),
    last_processed_month TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, item_type, id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
