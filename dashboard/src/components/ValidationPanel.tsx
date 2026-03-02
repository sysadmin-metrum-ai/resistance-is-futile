'use client';

import { useState, useEffect } from 'react';
import { CheckCircle, XCircle, AlertTriangle, Loader2, Battery, Signal, Plane, Navigation, Clock } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { preFlightCheck, healthCheckDrone, validateMission } from '@/lib/api';
import type { Drone, Waypoint, PreFlightCheckResponse, HealthCheckResponse, MissionValidationResponse } from '@/types';

/**
 * ValidationPanel - Orchestrates validation workflow before mission submission.
 *
 * Validates in sequence: pre-flight -> health -> mission validation
 * Disables submit button when any validation fails.
 */
interface ValidationPanelProps {
  drone: Drone;
  waypoints: Waypoint[];
  durationSeconds: number;
  onValidationComplete?: (isValid: boolean) => void;
}

/**
 * CheckItem - Displays individual validation check result.
 */
function CheckItem({
  label,
  value,
  isPending,
}: {
  label: string;
  value: boolean | null;
  isPending?: boolean;
}) {
  if (isPending) {
    return (
      <div className="flex items-center justify-between py-1">
        <span className="text-sm text-muted-foreground">{label}</span>
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const isTrue = value === true;
  const isNull = value === null;

  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-sm text-muted-foreground">{label}</span>
      {isNull ? (
        <XCircle className="h-4 w-4 text-muted-foreground" />
      ) : isTrue ? (
        <CheckCircle className="h-4 w-4 text-green-500" />
      ) : (
        <XCircle className="h-4 w-4 text-red-500" />
      )}
    </div>
  );
}

/**
 * SectionCard - Displays a validation section with title and checks.
 */
function SectionCard({
  title,
  icon: Icon,
  children,
  status,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
  status?: 'pending' | 'success' | 'error';
}) {
  const statusColors = {
    pending: 'border-yellow-500',
    success: 'border-green-500',
    error: 'border-red-500',
  };

  const statusIcon = {
    pending: <Loader2 className="h-4 w-4 animate-spin text-yellow-500" />,
    success: <CheckCircle className="h-4 w-4 text-green-500" />,
    error: <XCircle className="h-4 w-4 text-red-500" />,
  };

  return (
    <Card className={`border-l-4 ${status ? statusColors[status] : 'border-l-muted'}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon className="h-4 w-4" />
            <CardTitle className="text-base">{title}</CardTitle>
          </div>
          {status && statusIcon[status]}
        </div>
      </CardHeader>
      <CardContent className="space-y-1">
        {children}
      </CardContent>
    </Card>
  );
}

export function ValidationPanel({
  drone,
  waypoints,
  durationSeconds,
  onValidationComplete,
}: ValidationPanelProps) {
  const [preflight, setPreflight] = useState<PreFlightCheckResponse | null>(null);
  const [health, setHealth] = useState<HealthCheckResponse | null>(null);
  const [missionValidation, setMissionValidation] = useState<MissionValidationResponse | null>(null);

  const [preflightLoading, setPreflightLoading] = useState(false);
  const [healthLoading, setHealthLoading] = useState(false);
  const [missionLoading, setMissionLoading] = useState(false);

  const [allValid, setAllValid] = useState(false);

  // Run validation when drone, waypoints, or duration changes
  useEffect(() => {
    if (!drone || !drone.id) return;
    runValidation();
  }, [drone.id, drone.battery, drone.state, drone.enabled]);

  // Run mission validation when preflight and health are done
  useEffect(() => {
    if (preflight?.ready && health?.ready && drone.id && waypoints.length > 0) {
      runMissionValidation();
    }
  }, [preflight?.ready, health?.ready]);

  // Notify parent when validation state changes
  useEffect(() => {
    if (onValidationComplete) {
      onValidationComplete(allValid);
    }
  }, [allValid, onValidationComplete]);

  const runValidation = async () => {
    if (!drone?.id) return;

    // Step 1: Pre-flight check
    setPreflightLoading(true);
    try {
      const pfResult = await preFlightCheck(drone.id);
      setPreflight(pfResult);
    } catch (error) {
      console.error('Preflight check failed:', error);
      setPreflight({ ready: false, checks: { error: true } });
    }
    setPreflightLoading(false);

    // Step 2: Health check
    setHealthLoading(true);
    try {
      const hResult = await healthCheckDrone(drone.id);
      setHealth(hResult);
    } catch (error) {
      console.error('Health check failed:', error);
      setHealth({ ready: false, battery: null, connection_quality: null, reason: 'Check failed' });
    }
    setHealthLoading(false);
  };

  const runMissionValidation = async () => {
    if (!drone?.id || waypoints.length === 0) return;

    setMissionLoading(true);
    try {
      const mvResult = await validateMission(drone.id, waypoints, durationSeconds);
      setMissionValidation(mvResult);

      // All valid if preflight ready, health ready, and mission valid
      const isValid = (preflight?.ready ?? false) && (health?.ready ?? false) && mvResult.valid;
      setAllValid(isValid);
    } catch (error) {
      console.error('Mission validation failed:', error);
      setMissionValidation({
        valid: false,
        checks: { drone_ready: false, battery_sufficient: false, waypoints_in_range: false },
        warnings: ['Validation request failed'],
      });
      setAllValid(false);
    }
    setMissionLoading(false);
  };

  // Determine section statuses
  const preflightStatus: 'pending' | 'success' | 'error' = preflightLoading
    ? 'pending'
    : preflight?.ready
    ? 'success'
    : 'error';

  const healthStatus: 'pending' | 'success' | 'error' = healthLoading
    ? 'pending'
    : health?.ready
    ? 'success'
    : 'error';

  const missionStatus: 'pending' | 'success' | 'error' = missionLoading
    ? 'pending'
    : missionValidation?.valid
    ? 'success'
    : missionValidation
    ? 'error'
    : 'pending';

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Validation</CardTitle>
          {allValid ? (
            <Badge variant="default" className="bg-green-500">
              Ready to Fly
            </Badge>
          ) : (
            <Badge variant="destructive">Not Ready</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Pre-flight Section */}
        <SectionCard title="Pre-Flight Check" icon={Plane} status={preflightStatus}>
          <CheckItem label="Drone Enabled" value={preflight?.checks?.enabled ?? null} isPending={preflightLoading} />
          <CheckItem label="State: Idle" value={preflight?.checks?.state_idle ?? null} isPending={preflightLoading} />
          <CheckItem label="Battery OK" value={preflight?.checks?.battery_ok ?? null} isPending={preflightLoading} />
          <CheckItem label="Connection OK" value={preflight?.checks?.connection_ok ?? null} isPending={preflightLoading} />
        </SectionCard>

        {/* Health Section */}
        <SectionCard title="Health Status" icon={Battery} status={healthStatus}>
          <div className="flex items-center justify-between py-1">
            <span className="text-sm text-muted-foreground">Battery Level</span>
            <span className={`text-sm font-medium ${
              (health?.battery ?? 0) >= 50 ? 'text-green-500' :
              (health?.battery ?? 0) >= 20 ? 'text-yellow-500' : 'text-red-500'
            }`}>
              {healthLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : `${health?.battery ?? '-'}%`}
            </span>
          </div>
          <div className="flex items-center justify-between py-1">
            <span className="text-sm text-muted-foreground">Connection Quality</span>
            <span className={`text-sm font-medium ${
              (health?.connection_quality ?? 0) >= 70 ? 'text-green-500' :
              (health?.connection_quality ?? 0) >= 40 ? 'text-yellow-500' : 'text-red-500'
            }`}>
              {healthLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : `${health?.connection_quality ?? '-'}%`}
            </span>
          </div>
        </SectionCard>

        {/* Mission Validation Section */}
        <SectionCard title="Mission Validation" icon={Navigation} status={missionStatus}>
          <CheckItem
            label="Drone Ready"
            value={missionValidation?.checks?.drone_ready ?? null}
            isPending={missionLoading}
          />
          <CheckItem
            label="Battery Sufficient"
            value={missionValidation?.checks?.battery_sufficient ?? null}
            isPending={missionLoading}
          />
          <CheckItem
            label="Waypoints in Range"
            value={missionValidation?.checks?.waypoints_in_range ?? null}
            isPending={missionLoading}
          />

          {/* Warnings */}
          {missionValidation?.warnings && missionValidation.warnings.length > 0 && (
            <div className="mt-2 p-2 bg-yellow-500/10 rounded border border-yellow-500/20">
              <div className="flex items-center gap-1 text-yellow-600 text-sm font-medium">
                <AlertTriangle className="h-3 w-3" />
                Warnings
              </div>
              <ul className="mt-1 text-xs text-yellow-600 space-y-1">
                {missionValidation.warnings.map((warning, i) => (
                  <li key={i}>• {warning}</li>
                ))}
              </ul>
            </div>
          )}
        </SectionCard>

        {/* Run Validation Button */}
        <Button
          variant="outline"
          className="w-full"
          onClick={runValidation}
          disabled={preflightLoading || healthLoading || missionLoading}
        >
          {preflightLoading || healthLoading || missionLoading ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Validating...
            </>
          ) : (
            'Re-run Validation'
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
