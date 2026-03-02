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
} from '@/types';

/**
 * Create axios instance with API key interceptor.
 */
function createApiClient(): AxiosInstance {
  const client = axios.create({
    baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
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
// Re-export API client for advanced usage
// ============================================================================

export { apiClient };
