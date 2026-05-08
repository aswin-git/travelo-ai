CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS places (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    city VARCHAR(255),
    category VARCHAR(255),
    description TEXT,
    latitude FLOAT,
    longitude FLOAT,
    source VARCHAR(50) DEFAULT 'system',
    wikipedia_url VARCHAR(500),
    osm_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
