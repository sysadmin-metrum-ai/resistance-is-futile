/**
 * TypeScript types mirroring the backend API.
 * These types correspond to the Pydantic models in src/api/routes/.
 */

// ============================================================================
// Drone Types
// ============================================================================

export interface Drone {
  id: number;
  uri: string;
  name: string;
  state: string;
  battery: number | null;
  connection_quality: number | null;
  enabled: boolean;
  fleet_id?: number;
  /** Optional position for map display */
  x?: number;
  y?: number;
}

export interface DroneCreateRequest {
  uri: string;
  name: string;
  fleet_id?: number;
}

export interface DroneUpdateRequest {
  enabled?: boolean;
}

export interface DiscoverResponse {
  uris: string[];
}

// ============================================================================
// Mission Types
// ============================================================================

export interface Waypoint {
  x: number;
  y: number;
  z?: number;
}

export interface MissionRequest {
  waypoints: Waypoint[];
  duration_seconds: number;
  target_drone_id?: number;
  callback_url?: string;
}

export interface MissionResponse {
  mission_id: string;
  assigned_drone: number | null;
  status: string;
  estimated_wait?: number;
}

export interface MissionDetailResponse {
  id: number;
  mission_id: string;
  drone_id: number | null;
  waypoints: Waypoint[];
  duration_seconds: number;
  status: string;
  callback_url: string | null;
  result: Record<string, unknown> | null;
}

export interface CancelResponse {
  mission_id: string;
  status: string;
}

// ============================================================================
// Safety Types
// ============================================================================

export interface KillSwitchResponse {
  status: string;
}

export interface HealthCheckResponse {
  ready: boolean;
  battery: number | null;
  connection_quality: number | null;
  reason: string | null;
}

export interface BulkHealthCheckResponse {
  results: HealthCheckResponse[];
}

export interface PreFlightCheckResponse {
  ready: boolean;
  checks: Record<string, unknown>;
}

export interface MissionAbortResponse {
  mission_id: string;
  status: string;
}

export interface MissionValidationRequest {
  drone_id: number;
  waypoints: Waypoint[];
  duration_seconds: number;
}

export interface MissionValidationResponse {
  valid: boolean;
  checks: {
    drone_ready: boolean;
    drone_state?: string;
    battery_sufficient: boolean;
    battery: number | null;
    battery_required?: number;
    waypoints_in_range: boolean;
  };
  warnings: string[];
}

// ============================================================================
// SSE (Server-Sent Events) Types
// ============================================================================

export type SSEEventType =
  | 'drone_update'
  | 'mission_started'
  | 'mission_completed'
  | 'mission_failed'
  | 'mission_cancelled'
  | 'drone_state_change'
  | 'health_alert';

export interface SSEMessage {
  event: SSEEventType;
  data: DroneUpdateData | MissionUpdateData | HealthAlertData;
  timestamp: string;
}

export interface DroneUpdateData {
  drone_id: number;
  state?: string;
  battery?: number;
  connection_quality?: number;
  x?: number;
  y?: number;
}

export interface MissionUpdateData {
  mission_id: string;
  drone_id: number;
  status: 'pending' | 'running' | 'completed' | 'cancelled' | 'failed';
  result?: Record<string, unknown>;
}

export interface HealthAlertData {
  drone_id: number;
  type: 'battery_low' | 'connection_lost' | 'preflight_failed';
  message: string;
}

// ============================================================================
// Image Types
// ============================================================================

export interface CaptureResponse {
  image_id: string;
  filepath: string;
  mission_id: string;
}

export interface ImageListResponse {
  mission_id: string;
  images: string[];
  count: number;
}

export interface DeleteImageResponse {
  success: boolean;
  image_id: string;
}

// ============================================================================
// LED Types
// ============================================================================

export interface LEDSetRequest {
  color: string;
}

export interface LEDBlinkRequest {
  color: string;
  duration: number;
}

export interface LEDResponse {
  success: boolean;
  drone_id: number;
  action: string;
  message: string;
}

// ============================================================================
// Fleet Types
// ============================================================================

export interface Fleet {
  id: number;
  name: string;
  description: string | null;
  category: string;
  color: string;
  max_drones: number;
  enabled: boolean;
  drone_count?: number;
  created_at: string;
  updated_at: string;
}

export interface FleetCreateRequest {
  name: string;
  description?: string;
  category: string;
  color?: string;
  max_drones?: number;
}

export interface FleetUpdateRequest {
  name?: string;
  description?: string;
  category?: string;
  color?: string;
  max_drones?: number;
  enabled?: boolean;
}

export interface DroneFleetAssignmentRequest {
  drone_id: number;
  notes?: string;
}

export interface DroneFleetAssignmentResponse {
  success: boolean;
  fleet_id: number;
  drone_id: number;
  message: string;
}

export interface BulkFleetAssignmentRequest {
  drone_ids: number[];
  notes?: string;
}

// ============================================================================
// Anchor Types
// ============================================================================

export interface Anchor {
  id: number;
  anchor_id: number;
  name: string;
  x: number;
  y: number;
  z: number;
  mode: string;
  status: string;
  last_seen: string | null;
  battery_level: number | null;
  firmware_version: string | null;
  notes: string | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface AnchorCreateRequest {
  anchor_id: number;
  name: string;
  x: number;
  y: number;
  z: number;
  mode: string;
  firmware_version?: string;
  notes?: string;
}

export interface AnchorUpdateRequest {
  name?: string;
  x?: number;
  y?: number;
  z?: number;
  mode?: string;
  status?: string;
  battery_level?: number;
  firmware_version?: string;
  notes?: string;
  enabled?: boolean;
}

export interface AnchorPositionUpdateRequest {
  x: number;
  y: number;
  z: number;
}

export interface AnchorSystemStatus {
  total_anchors: number;
  online_anchors: number;
  offline_anchors: number;
  calibrating_anchors: number;
  error_anchors: number;
  positioning_mode: string;
  system_ready: boolean;
  coverage_area?: {
    x_min: number;
    x_max: number;
    y_min: number;
    y_max: number;
    z_min: number;
    z_max: number;
  };
}

export interface BulkAnchorCreateRequest {
  anchors: AnchorCreateRequest[];
}
