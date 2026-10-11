-- Banco de Dados para App de Planejamento Financeiro Multi-Usuário
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recurring_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    item_type TEXT NOT NULL CHECK(item_type IN ('income', 'expense')),
    category TEXT, -- 'Serviço', 'Venda', 'Custos fixos'
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    recurrence_day INTEGER NOT NULL CHECK(recurrence_day BETWEEN 1 AND 31),
    last_processed_month TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('receita', 'gasto')),
    category TEXT NOT NULL,
    sub_type TEXT,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    tx_date DATE NOT NULL,
    is_auto INTEGER DEFAULT 0,
    is_settled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY,
    initial_balance REAL DEFAULT 0.0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
