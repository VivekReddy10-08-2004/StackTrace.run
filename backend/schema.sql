-- DEV-SIM / StackTrace.run — auth + progression schema (MEMO 1.2 §1)
-- Relational layout with native-JSON badge storage. Works on both
-- Turso (libSQL) and local SQLite.

-- Core user identity table
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,               -- UUID or GitHub unique ID
    username TEXT UNIQUE NOT NULL,          -- Display handle
    email TEXT UNIQUE,                      -- Optional for native registration, standard for OAuth
    password_hash TEXT,                     -- NULL if user signed up exclusively via GitHub
    auth_provider TEXT DEFAULT 'native',    -- 'native' or 'github'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Player progression, metrics, and state tracking
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT PRIMARY KEY,
    current_ranking INTEGER DEFAULT 1200,   -- Elo-style metric for leaderboards
    tickets_solved INTEGER DEFAULT 0,
    earned_badges TEXT DEFAULT '[]',        -- JSON array string containing milestone tags
    current_streak INTEGER DEFAULT 0,
    last_solved_at DATETIME,                -- supports streak calculation
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Index optimizations for rapid dashboard rendering
CREATE INDEX IF NOT EXISTS idx_leaderboard ON user_profiles(current_ranking DESC);
