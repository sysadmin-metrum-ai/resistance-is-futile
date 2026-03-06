/**
 * API client wrapper for the Drone Swarm backend.
 * Uses axios with typed functions for type safety.
 */

import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import type {
  Drone,
  DroneCreateRequest,
  DroneUpdateRequest,
  DiscoverResponse,
  Waypoint,
  MissionRequest,
  MissionResponse,
  MissionDetailResponse,
  CancelResponse,
  KillSwitchResponse,
  HealthCheckResponse,
  BulkHealthCheckResponse,
  PreFlightCheckResponse,
  MissionAbortResponse,
  MissionValidationRequest,
  MissionValidationResponse,
  CaptureResponse,
  ImageListResponse,
  DeleteImageResponse,
  LEDSetRequest,
  LEDBlinkRequest,
  LEDResponse,
  Fleet,
  FleetCreateRequest,
  FleetUpdateRequest,
  DroneFleetAssignmentRequest,
  DroneFleetAssignmentResponse,
  BulkFleetAssignmentRequest,
  Anchor,
  AnchorCreateRequest,
  AnchorUpdateRequest,
  AnchorPositionUpdateRequest,
  AnchorSystemStatus,
  BulkAnchorCreateRequest,
} from '@/types';

/**
 * Create axios instance with API key interceptor.
 */
function createApiClient(): AxiosInstance {
  // Use relative URL '/api' when running behind reverse proxy (Caddy)
  // This allows the browser to use the same host:port as the dashboard
  const baseURL = '/api';

  const client = axios.create({
    baseURL,
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  // Add API key to all requests
  client.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
      const apiKey = process.env.NEXT_PUBLIC_API_KEY;
      if (apiKey) {
        config.headers['X-API-Key'] = apiKey;
      }
      return config;
    },
    (error) => Promise.reject(error)
  );

  return client;
}

const apiClient = createApiClient();

// ============================================================================
// Drone API
// ============================================================================

/**
 * List all drones in the fleet.
 */
export async function getDrones(): Promise<Drone[]> {
  const response = await apiClient.get<Drone[]>('/drones');
  return response.data;
}

/**
 * Get details for a specific drone.
 */
export async function getDrone(droneId: number): Promise<Drone> {
  const response = await apiClient.get<Drone>(`/drones/${droneId}`);
  return response.data;
}

/**
 * Discover available Crazyflie drones on the network.
 */
export async function discoverDrones(): Promise<DiscoverResponse> {
  const response = await apiClient.post<DiscoverResponse>('/drones/discover');
  return response.data;
}

/**
 * Register a new drone in the fleet.
 */
export async function registerDrone(request: DroneCreateRequest): Promise<Drone> {
  const response = await apiClient.post<Drone>('/drones', request);
  return response.data;
}

/**
 * Unregister a drone from the fleet.
 */
export async function unregisterDrone(droneId: number): Promise<void> {
  await apiClient.delete(`/drones/${droneId}`);
}

/**
 * Update drone properties.
 */
export async function updateDrone(
  droneId: number,
  request: DroneUpdateRequest
): Promise<Drone> {
  const response = await apiClient.patch<Drone>(`/drones/${droneId}`, request);
  return response.data;
}

// ============================================================================
// Mission API
// ============================================================================

/**
 * Submit a new mission for execution.
 */
export async function createMission(request: MissionRequest): Promise<MissionResponse> {
  const response = await apiClient.post<MissionResponse>('/missions', request);
  return response.data;
}

/**
 * Get mission details and status.
 */
export async function getMission(missionId: string): Promise<MissionDetailResponse> {
  const response = await apiClient.get<MissionDetailResponse>(`/missions/${missionId}`);
  return response.data;
}

/**
 * List all missions.
 */
export async function getMissions(): Promise<MissionDetailResponse[]> {
  const response = await apiClient.get<MissionDetailResponse[]>('/missions');
  return response.data;
}

/**
 * Cancel a pending or running mission.
 */
export async function cancelMission(missionId: string): Promise<CancelResponse> {
  const response = await apiClient.post<CancelResponse>(`/missions/${missionId}/cancel`);
  return response.data;
}

// ============================================================================
// Safety API
// ============================================================================

/**
 * Trigger emergency kill switch - immediately land all drones.
 */
export async function triggerKillSwitch(): Promise<KillSwitchResponse> {
  const response = await apiClient.post<KillSwitchResponse>('/safety/kill-switch');
  return response.data;
}

/**
 * Check health status of a specific drone.
 */
export async function healthCheckDrone(droneId: number): Promise<HealthCheckResponse> {
  const response = await apiClient.get<HealthCheckResponse>(`/safety/health-check/${droneId}`);
  return response.data;
}

/**
 * Run health check on all registered drones.
 */
export async function healthCheckAllDrones(): Promise<BulkHealthCheckResponse> {
  const response = await apiClient.post<BulkHealthCheckResponse>('/safety/health-check');
  return response.data;
}

/**
 * Run full pre-flight validation on a drone.
 */
export async function preFlightCheck(droneId: number): Promise<PreFlightCheckResponse> {
  const response = await apiClient.get<PreFlightCheckResponse>(`/safety/pre-flight/${droneId}`);
  return response.data;
}

/**
 * Abort a running mission.
 */
export async function abortMission(missionId: string): Promise<MissionAbortResponse> {
  const response = await apiClient.post<MissionAbortResponse>(`/safety/missions/${missionId}/abort`);
  return response.data;
}

/**
 * Validate if a planned mission can be executed.
 */
export async function validateMission(
  droneId: number,
  waypoints: Waypoint[],
  durationSeconds: number
): Promise<MissionValidationResponse> {
  const request: MissionValidationRequest = {
    drone_id: droneId,
    waypoints,
    duration_seconds: durationSeconds,
  };
  const response = await apiClient.post<MissionValidationResponse>('/safety/validate-mission', request);
  return response.data;
}

// ============================================================================
// Camera/Image API
// ============================================================================

/**
 * Get the base URL for image retrieval.
 */
export function getImageUrl(imageId: string): string {
  const baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  return `${baseURL}/images/${imageId}`;
}

/**
 * List all images captured during a mission.
 */
export async function getMissionImages(missionId: string): Promise<ImageListResponse> {
  const response = await apiClient.get<ImageListResponse>(`/images/mission/${missionId}`);
  return response.data;
}

/**
 * Capture a new image for a mission.
 */
export async function captureImage(
  missionId: string,
  droneId?: number,
  captureInterval?: number
): Promise<CaptureResponse> {
  const params = new URLSearchParams();
  params.append('mission_id', missionId);
  if (droneId !== undefined) {
    params.append('drone_id', droneId.toString());
  }
  if (captureInterval !== undefined) {
    params.append('capture_interval', captureInterval.toString());
  }

  const response = await apiClient.post<CaptureResponse>(`/images/capture?${params.toString()}`);
  return response.data;
}

/**
 * Delete an image by ID.
 */
export async function deleteImage(imageId: string): Promise<DeleteImageResponse> {
  const response = await apiClient.delete<DeleteImageResponse>(`/images/${imageId}`);
  return response.data;
}

// ============================================================================
// LED Control API
// ============================================================================

/**
 * Set LED to a solid color on a drone.
 */
export async function setLEDColor(droneId: number, color: string): Promise<LEDResponse> {
  const response = await apiClient.post<LEDResponse>(`/led/${droneId}/set`, { color } as LEDSetRequest);
  return response.data;
}

/**
 * Blink LED with a color for specified duration.
 */
export async function blinkLED(droneId: number, color: string, duration: number = 3.0): Promise<LEDResponse> {
  const response = await apiClient.post<LEDResponse>(`/led/${droneId}/blink`, { color, duration } as LEDBlinkRequest);
  return response.data;
}

/**
 * Turn off LED on a drone.
 */
export async function turnOffLED(droneId: number): Promise<LEDResponse> {
  const response = await apiClient.post<LEDResponse>(`/led/${droneId}/off`);
  return response.data;
}

// ============================================================================
// Fleet API
// ============================================================================

/**
 * List all fleets with optional category filter.
 */
export async function getFleets(category?: string): Promise<Fleet[]> {
  const params = category ? `?category=${category}` : '';
  const response = await apiClient.get<{ fleets: Fleet[] }>(`/fleets${params}`);
  return response.data.fleets;
}

/**
 * Get details for a specific fleet.
 */
export async function getFleet(fleetId: number): Promise<Fleet> {
  const response = await apiClient.get<Fleet>(`/fleets/${fleetId}`);
  return response.data;
}

/**
 * Create a new fleet.
 */
export async function createFleet(request: FleetCreateRequest): Promise<Fleet> {
  const response = await apiClient.post<Fleet>('/fleets', request);
  return response.data;
}

/**
 * Update fleet properties.
 */
export async function updateFleet(fleetId: number, request: FleetUpdateRequest): Promise<Fleet> {
  const response = await apiClient.patch<Fleet>(`/fleets/${fleetId}`, request);
  return response.data;
}

/**
 * Delete a fleet.
 */
export async function deleteFleet(fleetId: number): Promise<void> {
  await apiClient.delete(`/fleets/${fleetId}`);
}

/**
 * Get all drones assigned to a fleet.
 */
export async function getFleetDrones(fleetId: number): Promise<{ fleet_id: number; fleet_name: string; drones: Drone[] }> {
  const response = await apiClient.get(`/fleets/${fleetId}/drones`);
  return response.data;
}

/**
 * Assign a drone to a fleet.
 */
export async function assignDroneToFleet(fleetId: number, request: DroneFleetAssignmentRequest): Promise<DroneFleetAssignmentResponse> {
  const response = await apiClient.post<DroneFleetAssignmentResponse>(`/fleets/${fleetId}/assign`, request);
  return response.data;
}

/**
 * Assign multiple drones to a fleet.
 */
export async function bulkAssignDronesToFleet(fleetId: number, request: BulkFleetAssignmentRequest): Promise<{ fleet_id: number; fleet_name: string; successful: number[]; failed: { drone_id: number; reason: string }[]; total_assigned: number; total_failed: number }> {
  const response = await apiClient.post(`/fleets/${fleetId}/assign-bulk`, request);
  return response.data;
}

/**
 * Remove a drone from a fleet.
 */
export async function unassignDroneFromFleet(fleetId: number, droneId: number): Promise<DroneFleetAssignmentResponse> {
  const response = await apiClient.post<DroneFleetAssignmentResponse>(`/fleets/${fleetId}/unassign/${droneId}`);
  return response.data;
}

// ============================================================================
// Anchor API
// ============================================================================

/**
 * List all Loco Positioning anchors.
 */
export async function getAnchors(status?: string, mode?: string): Promise<{ anchors: Anchor[]; total_count: number; online_count: number; offline_count: number }> {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  if (mode) params.append('mode', mode);
  const response = await apiClient.get(`/anchors?${params.toString()}`);
  return response.data;
}

/**
 * Get overall anchor system status.
 */
export async function getAnchorSystemStatus(): Promise<AnchorSystemStatus> {
  const response = await apiClient.get<AnchorSystemStatus>('/anchors/system-status');
  return response.data;
}

/**
 * Get details for a specific anchor.
 */
export async function getAnchor(anchorId: number): Promise<Anchor> {
  const response = await apiClient.get<Anchor>(`/anchors/${anchorId}`);
  return response.data;
}

/**
 * Register a new Loco Positioning anchor.
 */
export async function createAnchor(request: AnchorCreateRequest): Promise<Anchor> {
  const response = await apiClient.post<Anchor>('/anchors', request);
  return response.data;
}

/**
 * Register multiple anchors at once.
 */
export async function createAnchorsBulk(request: BulkAnchorCreateRequest): Promise<{ successful: Anchor[]; failed: { anchor_id: number; reason: string }[] }> {
  const response = await apiClient.post('/anchors/bulk', request);
  return response.data;
}

/**
 * Update anchor properties.
 */
export async function updateAnchor(anchorId: number, request: AnchorUpdateRequest): Promise<Anchor> {
  const response = await apiClient.patch<Anchor>(`/anchors/${anchorId}`, request);
  return response.data;
}

/**
 * Update only anchor position.
 */
export async function updateAnchorPosition(anchorId: number, request: AnchorPositionUpdateRequest): Promise<Anchor> {
  const response = await apiClient.patch<Anchor>(`/anchors/${anchorId}/position`, request);
  return response.data;
}

/**
 * Send heartbeat to mark anchor as online.
 */
export async function anchorHeartbeat(anchorId: number, batteryLevel?: number): Promise<{ anchor_id: number; status: string; last_seen: string; message: string }> {
  const response = await apiClient.post(`/anchors/${anchorId}/heartbeat`, { battery_level: batteryLevel });
  return response.data;
}

/**
 * Delete an anchor.
 */
export async function deleteAnchor(anchorId: number): Promise<void> {
  await apiClient.delete(`/anchors/${anchorId}`);
}

/**
 * Get neighboring anchors.
 */
export async function getAnchorNeighbors(anchorId: number): Promise<{ anchor_id: number; position: { x: number; y: number; z: number }; neighbors: { anchor_id: number; name: string; distance_meters: number; status: string }[] }> {
  const response = await apiClient.get(`/anchors/${anchorId}/neighbors`);
  return response.data;
}

// ============================================================================
// Re-export API client for advanced usage
// ============================================================================

export { apiClient };
