'use client';

import { useQuery } from '@tanstack/react-query';
import { DashboardLayout, PageCard } from '@/components/DashboardLayout';
import { getDrones, getSwarmBatteryTelemetry, getSwarmStatus } from '@/lib/api';
import type { Drone, SwarmBatterySample } from '@/types';

function shortName(uri: string): string {
  return uri.split('/').at(-1) || uri;
}

function percentFrom(sample?: SwarmBatterySample, drone?: Drone): number | null {
  const value = sample?.battery_percent ?? drone?.battery ?? null;
  return value === null || value === undefined ? null : Math.round(value);
}

function fillClass(percent: number | null): string {
  if (percent === null) return 'bg-slate-700';
  if (percent < 15) return 'bg-red-500';
  if (percent < 30) return 'bg-yellow-500';
  return 'bg-green-500';
}

function BatteryGauge({ percent }: { percent: number | null }) {
  const width = percent === null ? 0 : Math.max(0, Math.min(100, percent));
  return (
    <div className="flex items-center gap-2">
      <div className="relative h-16 w-32 rounded-xl border-4 border-slate-800 bg-slate-950 p-1">
        <div className={`h-full rounded-md ${fillClass(percent)}`} style={{ width: `${width}%` }} />
        <div className="absolute inset-0 flex items-center justify-center text-2xl font-bold text-white">
          {percent === null ? '--' : `${percent}%`}
        </div>
      </div>
      <div className="h-7 w-2 rounded-r bg-slate-800" />
    </div>
  );
}

export default function BatteryPage() {
  const { data: drones } = useQuery({
    queryKey: ['demo-drones'],
    queryFn: getDrones,
    refetchInterval: 5000,
  });

  const { data: status } = useQuery({
    queryKey: ['swarm-status'],
    queryFn: getSwarmStatus,
    refetchInterval: 2000,
  });

  const missionId = status?.active_mission_id ?? null;
  const { data: batteryData } = useQuery({
    queryKey: ['swarm-battery', missionId],
    queryFn: () => getSwarmBatteryTelemetry(missionId as string),
    enabled: Boolean(missionId),
    refetchInterval: 1000,
  });

  const telemetry = batteryData?.telemetry ?? {};
  const byUri = new Map((drones ?? []).map((drone) => [drone.uri, drone]));
  const activeUris = status?.selected ?? Object.keys(telemetry);
  const idleDrones = (drones ?? []).filter((drone) => !activeUris.includes(drone.uri));

  return (
    <DashboardLayout title="Drone Battery">
      <div className="space-y-6">
        <PageCard title="Active Drones" description="Live 1Hz battery watchdog readings during flight">
          {activeUris.length === 0 ? (
            <div className="text-muted-foreground">No active drones.</div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {activeUris.map((uri) => {
                const sample = telemetry[uri];
                const drone = byUri.get(uri);
                const percent = percentFrom(sample, drone);
                return (
                  <div key={uri} className="rounded-xl border p-4">
                    <div className="mb-3">
                      <div className="text-lg font-semibold">{drone?.name ?? shortName(uri)}</div>
                      <div className="text-xs text-muted-foreground">{uri}</div>
                    </div>
                    <BatteryGauge percent={percent} />
                    <div className="mt-3 text-sm text-muted-foreground">
                      {sample?.voltage ? `${sample.voltage.toFixed(2)}V` : 'waiting for live sample'}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </PageCard>

        <PageCard title="Idle Drones" description="Last known registered battery levels">
          {idleDrones.length === 0 ? (
            <div className="text-muted-foreground">No idle drones registered.</div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {idleDrones.map((drone) => (
                <div key={drone.id} className="rounded-xl border p-4">
                  <div className="mb-3">
                    <div className="text-lg font-semibold">{drone.name}</div>
                    <div className="text-xs text-muted-foreground">{drone.uri}</div>
                  </div>
                  <BatteryGauge percent={percentFrom(undefined, drone)} />
                  <div className="mt-3 text-sm text-muted-foreground">{drone.state}</div>
                </div>
              ))}
            </div>
          )}
        </PageCard>
      </div>
    </DashboardLayout>
  );
}
