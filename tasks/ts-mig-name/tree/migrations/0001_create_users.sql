CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);
