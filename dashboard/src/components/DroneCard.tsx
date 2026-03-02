'use client';

import { useState } from 'react';
import { Battery, Signal, AlertTriangle, WifiOff, Lightbulb, Zap } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useMutation } from '@tanstack/react-query';
import { setLEDColor, blinkLED, turnOffLED } from '@/lib/api';
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
  const [ledOpen, setLedOpen] = useState(false);
  const [ledStatus, setLedStatus] = useState<string | null>(null);

  // LED color presets
  const ledColors = [
    { name: 'Green', color: '#00FF00', bg: 'bg-green-500' },
    { name: 'Yellow', color: '#FFFF00', bg: 'bg-yellow-500' },
    { name: 'Red', color: '#FF0000', bg: 'bg-red-500' },
    { name: 'Blue', color: '#0000FF', bg: 'bg-blue-500' },
  ];

  // Set LED color mutation
  const setColorMutation = useMutation({
    mutationFn: (color: string) => setLEDColor(drone.id, color),
    onSuccess: (data) => {
      setLedStatus(data.message || `LED set successfully`);
    },
    onError: (error) => {
      setLedStatus(error instanceof Error ? error.message : 'Failed to set LED');
    },
  });

  // Blink LED mutation
  const blinkMutation = useMutation({
    mutationFn: ({ color, duration }: { color: string; duration: number }) =>
      blinkLED(drone.id, color, duration),
    onSuccess: (data) => {
      setLedStatus(data.message || `LED blinking ${data.action}`);
    },
    onError: (error) => {
      setLedStatus(error instanceof Error ? error.message : 'Failed to blink LED');
    },
  });

  // Turn off LED mutation
  const turnOffMutation = useMutation({
    mutationFn: () => turnOffLED(drone.id),
    onSuccess: (data) => {
      setLedStatus(data.message || 'LED turned off');
    },
    onError: (error) => {
      setLedStatus(error instanceof Error ? error.message : 'Failed to turn off LED');
    },
  });

  const handleSetColor = (color: string) => {
    setLedStatus(null);
    setColorMutation.mutate(color);
  };

  const handleBlink = () => {
    setLedStatus(null);
    blinkMutation.mutate({ color: '#00FF00', duration: 3.0 });
  };

  const handleTurnOff = () => {
    setLedStatus(null);
    turnOffMutation.mutate();
  };

  const isLedPending = setColorMutation.isPending || blinkMutation.isPending || turnOffMutation.isPending;

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

        {/* LED Controls - Collapsible */}
        <div className="pt-2 border-t">
          <button
            type="button"
            className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
            onClick={(e) => {
              e.stopPropagation();
              setLedOpen(!ledOpen);
            }}
          >
            <Lightbulb className="h-4 w-4" />
            LED Controls
          </button>

          {ledOpen && (
            <div className="mt-2 space-y-2">
              {/* Color preset buttons */}
              <div className="flex gap-1">
                {ledColors.map((preset) => (
                  <Button
                    key={preset.name}
                    variant="outline"
                    size="sm"
                    className="flex-1 h-8"
                    disabled={isLedPending}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleSetColor(preset.color);
                    }}
                  >
                    <span
                      className={`w-3 h-3 rounded-full ${preset.bg} mr-1`}
                    />
                    {preset.name}
                  </Button>
                ))}
              </div>

              {/* Blink and Off buttons */}
              <div className="flex gap-1">
                <Button
                  variant="secondary"
                  size="sm"
                  className="flex-1 h-8"
                  disabled={isLedPending}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleBlink();
                  }}
                >
                  <Zap className="h-3 w-3 mr-1" />
                  Blink
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1 h-8"
                  disabled={isLedPending}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleTurnOff();
                  }}
                >
                  Off
                </Button>
              </div>

              {/* Status message */}
              {ledStatus && (
                <p className={`text-xs ${setColorMutation.isError || blinkMutation.isError || turnOffMutation.isError ? 'text-destructive' : 'text-muted-foreground'}`}>
                  {ledStatus}
                </p>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
