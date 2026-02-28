'use client';

import { Battery, Signal, AlertTriangle, WifiOff } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { Drone } from '@/types';

/**
 * DroneCard - Displays individual drone status with visual indicators.
 */
interface DroneCardProps {
  drone: Drone;
  onClick?: () => void;
}

/**
 * Get color for battery level.
 */
function getBatteryColor(level: number | null): string {
  if (level === null) return 'text-muted-foreground';
  if (level >= 80) return 'text-green-500';
  if (level >= 50) return 'text-yellow-500';
  if (level >= 20) return 'text-orange-500';
  return 'text-red-500';
}

/**
 * Get color for connection quality.
 */
function getConnectionColor(quality: number | null): string {
  if (quality === null) return 'text-muted-foreground';
  if (quality >= 80) return 'text-green-500';
  if (quality >= 50) return 'text-yellow-500';
  return 'text-red-500';
}

/**
 * Get badge variant for drone state.
 */
function getStateVariant(state: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (state) {
    case 'flying':
      return 'default';
    case 'idle':
      return 'secondary';
    case 'offline':
      return 'destructive';
    default:
      return 'outline';
  }
}

export function DroneCard({ drone, onClick }: DroneCardProps) {
  const hasError = drone.state === 'offline' || drone.connection_quality === null;

  return (
    <Card
      className={`transition-shadow hover:shadow-md ${onClick ? 'cursor-pointer' : ''}`}
      onClick={onClick}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">{drone.name}</CardTitle>
          {hasError && (
            <AlertTriangle className="h-5 w-5 text-yellow-500" />
          )}
        </div>
        <Badge variant={getStateVariant(drone.state)}>
          {drone.state}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Battery */}
        <div className="flex items-center gap-2">
          <Battery className={`h-4 w-4 ${getBatteryColor(drone.battery)}`} />
          <span className="text-sm">
            Battery:{' '}
            <span className={getBatteryColor(drone.battery)}>
              {drone.battery !== null ? `${drone.battery}%` : '-'}
            </span>
          </span>
        </div>

        {/* Connection Quality */}
        <div className="flex items-center gap-2">
          {drone.connection_quality === null ? (
            <WifiOff className="h-4 w-4 text-muted-foreground" />
          ) : (
            <Signal className={`h-4 w-4 ${getConnectionColor(drone.connection_quality)}`} />
          )}
          <span className="text-sm">
            Signal:{' '}
            <span className={getConnectionColor(drone.connection_quality)}>
              {drone.connection_quality !== null ? `${drone.connection_quality}%` : 'No signal'}
            </span>
          </span>
        </div>

        {/* Position (if available) */}
        {drone.x !== undefined && drone.y !== undefined && (
          <div className="text-sm text-muted-foreground">
            Position: ({drone.x.toFixed(1)}, {drone.y.toFixed(1)})
          </div>
        )}
      </CardContent>
    </Card>
  );
}
