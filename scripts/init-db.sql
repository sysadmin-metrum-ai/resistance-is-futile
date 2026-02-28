-- Database schema for Drone Swarm Agent Integration
-- Target: PostgreSQL with PostgREST

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drones table
CREATE TABLE IF NOT EXISTS drones (
    id SERIAL PRIMARY KEY,
    uri VARCHAR NOT NULL UNIQUE,  -- radio URI like "radio-0-80-1M-0"
    name VARCHAR NOT NULL,          -- like "drone-1"
    state VARCHAR DEFAULT 'offline' CHECK (state IN ('idle', 'busy', 'offline', 'error')),
    battery INTEGER DEFAULT 0 CHECK (battery >= 0 AND battery <= 100),
    connection_quality INTEGER DEFAULT 0 CHECK (connection_quality >= 0 AND connection_quality <= 100),
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

-- Missions table
CREATE TABLE IF NOT EXISTS missions (
    id SERIAL PRIMARY KEY,
    drone_id INTEGER REFERENCES drones(id) ON DELETE SET NULL,
    waypoints JSONB NOT NULL,
    duration_seconds INTEGER NOT NULL,
    status VARCHAR DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    callback_url VARCHAR,
    result JSONB,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_missions_drone_id ON missions(drone_id);
CREATE INDEX IF NOT EXISTS idx_missions_status ON missions(status);
CREATE INDEX IF NOT EXISTS idx_drones_state ON drones(state);

-- Trigger to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_drones_updated_at
    BEFORE UPDATE ON drones
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_missions_updated_at
    BEFORE UPDATE ON missions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions for PostgREST (anon role)
-- Note: Adjust role name based on your PostgREST configuration
GRANT SELECT, INSERT, UPDATE, DELETE ON drones TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON missions TO anon;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO anon;

-- Row Level Security (optional - enable if needed)
-- ALTER TABLE drones ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE missions ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "Enable read access for all users" ON drones FOR SELECT USING (true);
-- CREATE POLICY "Enable read access for all users" ON missions FOR SELECT USING (true);
