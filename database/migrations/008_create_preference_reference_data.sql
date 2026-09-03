CREATE TABLE IF NOT EXISTS preference_currencies (
    code VARCHAR(3) PRIMARY KEY CHECK (code ~ '^[A-Z]{3}$'),
    display_name VARCHAR(80) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    sort_order SMALLINT NOT NULL
);

CREATE TABLE IF NOT EXISTS preference_languages (
    code VARCHAR(10) PRIMARY KEY CHECK (length(trim(code)) BETWEEN 2 AND 10),
    display_name VARCHAR(80) NOT NULL,
    sort_order SMALLINT NOT NULL
);

INSERT INTO preference_currencies (code, display_name, symbol, sort_order)
VALUES
    ('USD', 'US Dollar', '$', 10),
    ('INR', 'Indian Rupee', 'Rs.', 20),
    ('EUR', 'Euro', 'EUR', 30),
    ('JPY', 'Japanese Yen', 'JPY', 40),
    ('GBP', 'British Pound', 'GBP', 50),
    ('CAD', 'Canadian Dollar', 'CAD', 60),
    ('AUD', 'Australian Dollar', 'AUD', 70),
    ('CNY', 'Chinese Yuan', 'CNY', 80)
ON CONFLICT (code) DO NOTHING;

INSERT INTO preference_languages (code, display_name, sort_order)
VALUES
    ('en', 'English', 10),
    ('hi', 'Hindi', 20),
    ('ja', 'Japanese', 30),
    ('de', 'German', 40),
    ('fr', 'French', 50),
    ('es', 'Spanish', 60)
ON CONFLICT (code) DO NOTHING;
