'use client';

import { MapPin, Clock, XCircle, CheckCircle, Loader2, AlertCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { MissionDetailResponse } from '@/types';

/**
 * MissionQueue - Displays list of missions with status and assignments.
 */
interface MissionQueueProps {
  missions: MissionDetailResponse[];
  onCancel?: (missionId: string) => void;
  isCancelling?: string | null;
}

/**
 * Get badge variant for mission status.
 */
function getStatusVariant(
  status: string
): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'completed':
      return 'default';
    case 'running':
      return 'secondary';
    case 'pending':
      return 'outline';
    case 'failed':
    case 'cancelled':
      return 'destructive';
    default:
      return 'outline';
  }
}

/**
 * Get icon for mission status.
 */
function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'completed':
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    case 'running':
      return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
    case 'failed':
      return <AlertCircle className="h-4 w-4 text-red-500" />;
    case 'cancelled':
      return <XCircle className="h-4 w-4 text-gray-500" />;
    default:
      return <Clock className="h-4 w-4 text-yellow-500" />;
  }
}

/**
 * Get color for status badge.
 */
function getStatusColor(status: string): string {
  switch (status) {
    case 'completed':
      return 'bg-green-500';
    case 'running':
      return 'bg-blue-500';
    case 'pending':
      return 'bg-yellow-500';
    case 'failed':
      return 'bg-red-500';
    case 'cancelled':
      return 'bg-gray-500';
    default:
      return 'bg-gray-500';
  }
}

export function MissionQueue({ missions, onCancel, isCancelling }: MissionQueueProps) {
  if (missions.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Mission Queue</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-center text-muted-foreground py-8">
            No missions in queue
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Mission Queue</CardTitle>
        <p className="text-sm text-muted-foreground">
          {missions.length} mission{missions.length !== 1 ? 's' : ''}
        </p>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {missions.map((mission) => (
            <div
              key={mission.mission_id}
              className="flex items-start justify-between rounded-lg border p-3"
            >
              <div className="flex-1 space-y-1">
                <div className="flex items-center gap-2">
                  <StatusIcon status={mission.status} />
                  <span className="font-mono text-sm">
                    {mission.mission_id.slice(0, 8)}
                  </span>
                  <Badge variant={getStatusVariant(mission.status)}>
                    {mission.status}
                  </Badge>
                </div>

                {/* Drone Assignment */}
                <div className="text-xs text-muted-foreground">
                  Drone:{' '}
                  {mission.drone_id ? (
                    <span className="font-medium">ID {mission.drone_id}</span>
                  ) : (
                    <span>Unassigned</span>
                  )}
                </div>

                {/* Waypoints Summary */}
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <MapPin className="h-3 w-3" />
                  <span>
                    {mission.waypoints.length} waypoint
                    {mission.waypoints.length !== 1 ? 's' : ''}
                  </span>
                  <span className="mx-1">|</span>
                  <Clock className="h-3 w-3" />
                  <span>{mission.duration_seconds}s</span>
                </div>
              </div>

              {/* Cancel Button */}
              {(mission.status === 'pending' || mission.status === 'running') &&
                onCancel && (
                  <button
                    onClick={() => onCancel(mission.mission_id)}
                    disabled={isCancelling === mission.mission_id}
                    className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-destructive disabled:opacity-50"
                    title="Cancel mission"
                  >
                    {isCancelling === mission.mission_id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <XCircle className="h-4 w-4" />
                    )}
                  </button>
                )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
