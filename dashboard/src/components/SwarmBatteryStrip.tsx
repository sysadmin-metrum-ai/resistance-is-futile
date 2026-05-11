'use client';

import { useQuery } from '@tanstack/react-query';
import { getSwarmBatteryTelemetry, getSwarmStatus } from '@/lib/api';
import type { SwarmBatterySample } from '@/types';

function shortUri(uri: string): string {
  return uri.split('/').at(-1) || uri;
}

function clampPercent(value: number | null | undefined): number {
  if (value === null || value === undefined || Number.isNaN(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}

function fillClass(percent: number): string {
  if (percent < 15) return 'bg-red-500';
  if (percent < 30) return 'bg-yellow-500';
  return 'bg-green-500';
}

function voltageLabel(sample?: SwarmBatterySample): string {
  if (sample?.voltage === null || sample?.voltage === undefined) return 'voltage pending';
  return `${sample.voltage.toFixed(2)}V`;
}

function BatteryIcon({ percent }: { percent: number }) {
  return (
    <div className="flex items-center gap-1">
      <div className="relative h-7 w-14 rounded-md border-2 border-slate-700 bg-slate-950 p-0.5">
        <div
          className={`h-full rounded-sm ${fillClass(percent)}`}
          style={{ width: `${percent}%` }}
        />
        <div className="absolute inset-0 flex items-center justify-center text-[11px] font-bold text-white">
          {percent}%
        </div>
      </div>
      <div className="h-3 w-1 rounded-r-sm bg-slate-700" />
    </div>
  );
}

export function SwarmBatteryStrip() {
  const { data: status } = useQuery({
    queryKey: ['swarm-status'],
    queryFn: getSwarmStatus,
    refetchInterval: 2000,
  });

  const missionId = status?.active_mission_id ?? null;
  const selectedUris = status?.selected ?? [];

  const { data: batteryData } = useQuery({
    queryKey: ['swarm-battery', missionId],
    queryFn: () => getSwarmBatteryTelemetry(missionId as string),
    enabled: Boolean(missionId),
    refetchInterval: 1000,
  });

  const telemetry = batteryData?.telemetry ?? {};
  const displayUris = selectedUris.length ? selectedUris : Object.keys(telemetry);

  return (
    <div className="fixed inset-x-0 bottom-0 z-40 border-t bg-background/95 px-4 py-2 shadow-lg backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center gap-4 overflow-x-auto">
        <div className="shrink-0 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Live battery
        </div>

        {!missionId && (
          <div className="text-sm text-muted-foreground">No active swarm battery samples</div>
        )}

        {missionId && displayUris.length === 0 && (
          <div className="text-sm text-muted-foreground">Waiting for first 1Hz battery samples</div>
        )}

        {displayUris.map((uri) => {
          const sample = telemetry[uri];
          const percent = clampPercent(sample?.battery_percent);
          return (
            <div key={uri} className="flex shrink-0 items-center gap-2 rounded-lg border px-3 py-2">
              <BatteryIcon percent={percent} />
              <div className="leading-tight">
                <div className="text-sm font-medium">{shortUri(uri)}</div>
                <div className="text-xs text-muted-foreground">
                  {sample ? voltageLabel(sample) : 'sample pending'}
                </div>
              </div>
              {sample?.watchdog_landed && (
                <div className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                  landing
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
