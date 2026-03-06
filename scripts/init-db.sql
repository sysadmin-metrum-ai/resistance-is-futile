-- Database schema for Drone Swarm Agent Integration
-- Target: PostgreSQL with PostgREST

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- FLEETS TABLE - Drone fleet/group management
-- ============================================
CREATE TABLE IF NOT EXISTS fleets (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL UNIQUE,          -- e.g., "inventory", "security", "cable-monitoring"
    description TEXT,                       -- Description of fleet purpose
    category VARCHAR DEFAULT 'general' CHECK (category IN ('inventory', 'security', 'cable-monitoring', 'inspection', 'emergency', 'general')),
    color VARCHAR DEFAULT '#3b82f6',       -- UI color for fleet identification
    max_drones INTEGER DEFAULT 10,         -- Maximum drones allowed in fleet
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

-- ============================================
-- LOCO ANCHOR NODES TABLE - UWB Positioning
-- ============================================
CREATE TABLE IF NOT EXISTS anchors (
    id SERIAL PRIMARY KEY,
    anchor_id INTEGER NOT NULL UNIQUE,     -- Hardware ID (0-7 for TWR mode)
    name VARCHAR NOT NULL,                  -- e.g., "anchor-0", "anchor-northwest"
    x FLOAT NOT NULL,                       -- X coordinate in meters
    y FLOAT NOT NULL,                       -- Y coordinate in meters
    z FLOAT NOT NULL,                       -- Z coordinate in meters (height)
    mode VARCHAR DEFAULT 'TWR' CHECK (mode IN ('TWR', 'TDoA2', 'TDoA3')),  -- Positioning mode
    status VARCHAR DEFAULT 'offline' CHECK (status IN ('online', 'offline', 'calibrating', 'error')),
    last_seen TIMESTAMP,                    -- Last communication timestamp
    battery_level INTEGER CHECK (battery_level >= 0 AND battery_level <= 100),
    firmware_version VARCHAR,
    notes TEXT,                             -- Installation notes
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

-- ============================================
-- DRONES TABLE - Updated with fleet support
-- ============================================
CREATE TABLE IF NOT EXISTS drones (
    id SERIAL PRIMARY KEY,
    uri VARCHAR NOT NULL UNIQUE,           -- radio URI like "radio://0/80/1M/100M"
    name VARCHAR NOT NULL,                  -- like "drone-1"
    fleet_id INTEGER REFERENCES fleets(id) ON DELETE SET NULL,  -- Fleet assignment
    state VARCHAR DEFAULT 'offline' CHECK (state IN ('idle', 'busy', 'offline', 'error')),
    battery INTEGER DEFAULT 0 CHECK (battery >= 0 AND battery <= 100),
    connection_quality INTEGER DEFAULT 0 CHECK (connection_quality >= 0 AND connection_quality <= 100),
    position_x FLOAT,                       -- Last known X position
    position_y FLOAT,                       -- Last known Y position
    position_z FLOAT,                       -- Last known Z position
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

-- ============================================
-- MISSIONS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS missions (
    id SERIAL PRIMARY KEY,
    drone_id INTEGER REFERENCES drones(id) ON DELETE SET NULL,
    fleet_id INTEGER REFERENCES fleets(id) ON DELETE SET NULL,  -- Optional fleet target
    waypoints JSONB NOT NULL,
    duration_seconds INTEGER NOT NULL,
    status VARCHAR DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    mission_type VARCHAR DEFAULT 'inspection' CHECK (mission_type IN ('inspection', 'patrol', 'security', 'cable-check', 'emergency', 'custom')),
    callback_url VARCHAR,
    result JSONB,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

-- ============================================
-- FLEET ASSIGNMENTS TABLE - Many-to-many tracking
-- ============================================
CREATE TABLE IF NOT EXISTS fleet_assignments (
    id SERIAL PRIMARY KEY,
    fleet_id INTEGER REFERENCES fleets(id) ON DELETE CASCADE,
    drone_id INTEGER REFERENCES drones(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP DEFAULT now(),
    assigned_by VARCHAR,                    -- User or system that assigned
    notes TEXT,
    UNIQUE(fleet_id, drone_id)              -- Prevent duplicate assignments
);

-- ============================================
-- INDEXES FOR PERFORMANCE
-- ============================================
CREATE INDEX IF NOT EXISTS idx_missions_drone_id ON missions(drone_id);
CREATE INDEX IF NOT EXISTS idx_missions_fleet_id ON missions(fleet_id);
CREATE INDEX IF NOT EXISTS idx_missions_status ON missions(status);
CREATE INDEX IF NOT EXISTS idx_drones_state ON drones(state);
CREATE INDEX IF NOT EXISTS idx_drones_fleet_id ON drones(fleet_id);
CREATE INDEX IF NOT EXISTS idx_fleets_category ON fleets(category);
CREATE INDEX IF NOT EXISTS idx_fleets_enabled ON fleets(enabled);
CREATE INDEX IF NOT EXISTS idx_anchors_status ON anchors(status);
CREATE INDEX IF NOT EXISTS idx_anchors_anchor_id ON anchors(anchor_id);
CREATE INDEX IF NOT EXISTS idx_fleet_assignments_fleet_id ON fleet_assignments(fleet_id);
CREATE INDEX IF NOT EXISTS idx_fleet_assignments_drone_id ON fleet_assignments(drone_id);

-- ============================================
-- TRIGGER FUNCTIONS - Auto-update timestamps
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers to all tables
CREATE TRIGGER update_fleets_updated_at
    BEFORE UPDATE ON fleets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_anchors_updated_at
    BEFORE UPDATE ON anchors
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_drones_updated_at
    BEFORE UPDATE ON drones
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_missions_updated_at
    BEFORE UPDATE ON missions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- PERMISSIONS FOR POSTGREST (anon role)
-- ============================================
DO $$ BEGIN
    CREATE ROLE anon WITH LOGIN;
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Grant permissions on all tables
GRANT SELECT, INSERT, UPDATE, DELETE ON drones TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON missions TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON fleets TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON anchors TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON fleet_assignments TO anon;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO anon;

-- ============================================
-- DEFAULT FLEETS - Pre-populate common fleets
-- ============================================
INSERT INTO fleets (name, description, category, color, max_drones) VALUES
    ('inventory', 'Inventory inspection and stock counting fleet', 'inventory', '#22c55e', 20),
    ('security', 'Security patrol and breach verification fleet', 'security', '#ef4444', 10),
    ('cable-monitoring', 'Network cable and connector inspection fleet', 'cable-monitoring', '#3b82f6', 15),
    ('inspection', 'General infrastructure inspection fleet', 'inspection', '#f59e0b', 10),
    ('emergency', 'Emergency response and incident documentation fleet', 'emergency', '#dc2626', 5)
ON CONFLICT (name) DO NOTHING;

-- ============================================
-- ROW LEVEL SECURITY (optional - enable if needed)
-- ============================================
-- ALTER TABLE drones ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE missions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE fleets ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE anchors ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "Enable read access for all users" ON drones FOR SELECT USING (true);
-- CREATE POLICY "Enable read access for all users" ON missions FOR SELECT USING (true);
