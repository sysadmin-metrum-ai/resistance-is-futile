'use client';

import { useMemo } from 'react';
import { ComposableMap, Geographies, Geography, Marker } from 'react-simple-maps';
import type { Drone } from '@/types';

const geoUrl = 'https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json';

/**
 * DroneMap - 2D visualization of drone positions using react-simple-maps.
 */
interface DroneMapProps {
  drones: Drone[];
  /** Map center coordinates [longitude, latitude] */
  center?: [number, number];
  /** Map zoom level */
  zoom?: number;
}

/**
 * Get marker color based on drone state.
 */
function getMarkerColor(state: string): string {
  switch (state) {
    case 'flying':
      return '#22c55e'; // green
    case 'idle':
      return '#3b82f6'; // blue
    case 'offline':
      return '#ef4444'; // red
    default:
      return '#6b7280'; // gray
  }
}

/**
 * Convert drone coordinates to map coordinates.
 * This is a simple scaling - real implementation might need proper projection.
 */
function scaleCoordinates(x: number, y: number): [number, number] {
  // Simple scaling for demo purposes
  // In production, you'd use proper coordinate transformation
  const scale = 0.01;
  return [x * scale, y * scale];
}

export function DroneMap({
  drones,
  center = [0, 20],
  zoom = 1,
}: DroneMapProps) {
  // Filter drones with position data
  const positionedDrones = useMemo(
    () => drones.filter((d) => d.x !== undefined && d.y !== undefined),
    [drones]
  );

  return (
    <div className="relative h-full w-full overflow-hidden rounded-lg border bg-slate-50">
      <ComposableMap
        projection="geoMercator"
        projectionConfig={{
          scale: 100,
          center: center,
        }}
        style={{ width: '100%', height: '100%' }}
        zoom={zoom}
      >
        <Geographies geography={geoUrl}>
          {({ geographies }) =>
            geographies.map((geo) => (
              <Geography
                key={geo.rsmKey}
                geography={geo}
                fill="#e2e8f0"
                stroke="#cbd5e1"
                strokeWidth={0.5}
                style={{
                  default: { outline: 'none' },
                  hover: { fill: '#cbd5e1', outline: 'none' },
                  pressed: { fill: '#94a3b8', outline: 'none' },
                }}
              />
            ))
          }
        </Geographies>

        {positionedDrones.map((drone) => {
          const [cx, cy] = scaleCoordinates(drone.x!, drone.y!);
          return (
            <Marker key={drone.id} coordinates={cx as [number, number]}>
              <circle
                r={6}
                fill={getMarkerColor(drone.state)}
                stroke="#fff"
                strokeWidth={2}
                className="cursor-pointer transition-transform hover:scale-125"
              />
              <title>
                {drone.name} - {drone.state}
              </title>
            </Marker>
          );
        })}
      </ComposableMap>

      {/* Legend */}
      <div className="absolute bottom-2 left-2 rounded-md bg-white/90 p-2 text-xs shadow-sm">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-green-500" />
          <span>Flying</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-blue-500" />
          <span>Idle</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-red-500" />
          <span>Offline</span>
        </div>
      </div>

      {positionedDrones.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center">
          <p className="text-muted-foreground">No drone position data available</p>
        </div>
      )}
    </div>
  );
}
