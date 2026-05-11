'use client';

import { PointerEvent, WheelEvent, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getSwarmDeployStatus, getSwarmStatus } from '@/lib/api';
import type { SwarmPlanDrone, Vec3 } from '@/types';

type Point3 = [number, number, number];
type Point2 = [number, number];

const BOOTH_FT = 10;
const FT_PER_M = 3.28084;
const SIM_DELAY_MS = 1500;
const STEP_MS = 3000;
const COLORS = ['#38bdf8', '#22c55e', '#a78bfa', '#fb923c', '#f43f5e'];
const LIGHTS: Array<[string, Point3]> = [
  ['LH1', [-5, -5, 10]],
  ['LH2', [5, -5, 10]],
  ['LH3', [5, 5, 10]],
  ['LH4', [-5, 5, 10]],
];
const SERVER_BOX = {
  min: [1.6, 1.4, 0] as Point3,
  max: [3.1, 3.0, 3.7] as Point3,
};

function toFeet(point: Vec3): Point3 {
  return [point[0] * FT_PER_M, point[1] * FT_PER_M, point[2] * FT_PER_M];
}

function pathFor(drone: SwarmPlanDrone): Vec3[] {
  return [
    drone.launch,
    ...drone.route_to_formation,
    drone.formation_slot,
    ...drone.pattern_points,
    ...drone.route_to_return,
    drone.return_point,
  ];
}

function interpolate(a: Vec3, b: Vec3, t: number): Vec3 {
  return [
    a[0] + (b[0] - a[0]) * t,
    a[1] + (b[1] - a[1]) * t,
    a[2] + (b[2] - a[2]) * t,
  ];
}

function plannedPosition(path: Vec3[], elapsedMs: number): Vec3 {
  if (elapsedMs <= 0 || path.length === 1) return path[0];
  const segment = Math.min(Math.floor(elapsedMs / STEP_MS), path.length - 2);
  const progress = (elapsedMs % STEP_MS) / STEP_MS;
  return interpolate(path[segment], path[segment + 1], progress);
}

function corners(min: Point3, max: Point3): Point3[] {
  const [x0, y0, z0] = min;
  const [x1, y1, z1] = max;
  return [
    [x0, y0, z0],
    [x1, y0, z0],
    [x1, y1, z0],
    [x0, y1, z0],
    [x0, y0, z1],
    [x1, y0, z1],
    [x1, y1, z1],
    [x0, y1, z1],
  ];
}

function rotate(point: Point3, yaw: number, pitch: number): Point3 {
  const [x, y, z] = point;
  const cy = Math.cos(yaw);
  const sy = Math.sin(yaw);
  const cp = Math.cos(pitch);
  const sp = Math.sin(pitch);
  const x1 = x * cy - y * sy;
  const y1 = x * sy + y * cy;
  const z1 = z - BOOTH_FT / 2;
  return [x1, y1 * cp - z1 * sp, y1 * sp + z1 * cp];
}

function project(point: Point3, yaw: number, pitch: number, zoom: number): { point: Point2; depth: number } {
  const [x, depth, z] = rotate(point, yaw, pitch);
  const scale = 34 * zoom;
  return {
    point: [450 + x * scale, 330 - z * scale],
    depth,
  };
}

function polygon(points: Point3[], yaw: number, pitch: number, zoom: number): string {
  return points.map((point) => project(point, yaw, pitch, zoom).point.join(',')).join(' ');
}

function avgDepth(points: Point3[], yaw: number, pitch: number): number {
  return points.reduce((sum, point) => sum + rotate(point, yaw, pitch)[1], 0) / points.length;
}

function serverSurfaces(min: Point3, max: Point3, yaw: number, pitch: number) {
  const c = corners(min, max);
  const center: Point3 = [
    (min[0] + max[0]) / 2,
    (min[1] + max[1]) / 2,
    (min[2] + max[2]) / 2,
  ];
  const centerDepth = rotate(center, yaw, pitch)[1];
  const verticalFaces = [
    { name: 'front', points: [c[0], c[1], c[5], c[4]], fill: '#020617' },
    { name: 'right', points: [c[1], c[2], c[6], c[5]], fill: '#030712' },
    { name: 'back', points: [c[2], c[3], c[7], c[6]], fill: '#111827' },
    { name: 'left', points: [c[3], c[0], c[4], c[7]], fill: '#0f172a' },
  ]
    .map((face) => ({ ...face, depth: avgDepth(face.points, yaw, pitch) }))
    .filter((face) => face.depth >= centerDepth)
    .sort((a, b) => a.depth - b.depth);

  return [
    ...verticalFaces,
    { name: 'top', points: [c[4], c[5], c[6], c[7]], fill: '#020617', depth: avgDepth([c[4], c[5], c[6], c[7]], yaw, pitch) },
  ];
}

function OrbitDot({ point, color, yaw, pitch, zoom }: {
  point: Point3;
  color: string;
  yaw: number;
  pitch: number;
  zoom: number;
}) {
  const projected = project(point, yaw, pitch, zoom).point;
  return (
    <g>
      <circle cx={projected[0]} cy={projected[1]} r="9" fill={color} stroke="#fff" strokeWidth="2" />
      <circle cx={projected[0]} cy={projected[1]} r="16" fill={color} opacity="0.12" />
    </g>
  );
}

export function BoothSwarmSimulation() {
  const [now, setNow] = useState(Date.now());
  const [yaw, setYaw] = useState(-0.62);
  const [pitch, setPitch] = useState(0.58);
  const [zoom, setZoom] = useState(1);
  const drag = useRef<{ x: number; y: number; yaw: number; pitch: number } | null>(null);
  const startedAtByMission = useRef<Record<string, number>>({});

  const { data: status } = useQuery({
    queryKey: ['swarm-status-for-sim'],
    queryFn: getSwarmStatus,
    refetchInterval: 2000,
  });

  const missionId = status?.active_mission_id ?? null;
  const { data: deploy } = useQuery({
    queryKey: ['swarm-plan-for-sim', missionId],
    queryFn: () => getSwarmDeployStatus(missionId as string),
    enabled: Boolean(missionId),
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchInterval: false,
  });

  useEffect(() => {
    if (!missionId) return;
    startedAtByMission.current[missionId] ??= Date.now();
  }, [missionId]);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(timer);
  }, []);

  const plan = deploy?.plan;
  const paths = useMemo(() => plan?.drones.map(pathFor) ?? [], [plan]);
  const missionStart = missionId ? startedAtByMission.current[missionId] : undefined;
  const elapsedMs = Math.max(0, now - (missionStart ?? now) - SIM_DELAY_MS);

  const faces = [
    { points: [[-5, -5, 0], [5, -5, 0], [5, 5, 0], [-5, 5, 0]] as Point3[], fill: '#3b82f6', opacity: 0.62 },
    { points: [[-5, 5, 0], [5, 5, 0], [5, 5, 10], [-5, 5, 10]] as Point3[], fill: '#1d4ed8', opacity: 0.72 },
    { points: [[-5, -5, 0], [-5, 5, 0], [-5, 5, 10], [-5, -5, 10]] as Point3[], fill: '#0f2745', opacity: 0.7 },
    { points: [[5, -5, 0], [5, 5, 0], [5, 5, 10], [5, -5, 10]] as Point3[], fill: '#0f2745', opacity: 0.7 },
    { points: [[-5, -5, 10], [5, -5, 10], [5, 5, 10], [-5, 5, 10]] as Point3[], fill: '#071839', opacity: 0.78 },
  ].sort((a, b) => avgDepth(a.points, yaw, pitch) - avgDepth(b.points, yaw, pitch));

  const serverFaces = serverSurfaces(SERVER_BOX.min, SERVER_BOX.max, yaw, pitch);
  const serverCorners = corners(SERVER_BOX.min, SERVER_BOX.max);

  function onPointerDown(event: PointerEvent<SVGSVGElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { x: event.clientX, y: event.clientY, yaw, pitch };
  }

  function onPointerMove(event: PointerEvent<SVGSVGElement>) {
    if (!drag.current) return;
    const dx = event.clientX - drag.current.x;
    const dy = event.clientY - drag.current.y;
    setYaw(drag.current.yaw + dx * 0.008);
    setPitch(Math.max(-0.05, Math.min(1.2, drag.current.pitch + dy * 0.006)));
  }

  function onPointerUp() {
    drag.current = null;
  }

  function onWheel(event: WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    setZoom((value) => Math.max(0.55, Math.min(1.85, value - event.deltaY * 0.001)));
  }

  return (
    <div className="h-full rounded-xl border bg-[#071421] p-3">
      <svg
        viewBox="0 0 900 660"
        className="h-full w-full cursor-grab touch-none rounded-lg active:cursor-grabbing"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onWheel={onWheel}
      >
        <defs>
          <radialGradient id="boothGlow" cx="50%" cy="18%" r="80%">
            <stop offset="0%" stopColor="#1d4ed8" stopOpacity="0.8" />
            <stop offset="100%" stopColor="#020617" stopOpacity="0.1" />
          </radialGradient>
        </defs>
        <rect width="900" height="660" fill="#071421" />

        {faces.map((face, index) => (
          <polygon
            key={index}
            points={polygon(face.points, yaw, pitch, zoom)}
            fill={index === 1 ? 'url(#boothGlow)' : face.fill}
            opacity={face.opacity}
            stroke="#2563eb"
            strokeOpacity="0.35"
          />
        ))}

        {Array.from({ length: 11 }, (_, index) => index - 5).map((value) => (
          <g key={value}>
            <polyline
              points={polygon([[value, -5, 0], [value, 5, 0]], yaw, pitch, zoom)}
              fill="none"
              stroke="#60a5fa"
              strokeOpacity="0.14"
            />
            <polyline
              points={polygon([[-5, value, 0], [5, value, 0]], yaw, pitch, zoom)}
              fill="none"
              stroke="#60a5fa"
              strokeOpacity="0.14"
            />
          </g>
        ))}

        {LIGHTS.map(([label, point]) => {
          const [x, y] = project(point, yaw, pitch, zoom).point;
          return (
            <g key={label}>
              <rect x={x - 34} y={y - 16} width="68" height="16" fill="#5a4a09" />
              <rect x={x - 26} y={y - 22} width="52" height="10" fill="#161b13" />
              <circle cx={x} cy={y} r="9" fill="#fde68a" />
              <circle cx={x} cy={y + 10} r="22" fill="#fbbf24" opacity="0.13" />
              <text x={x + 18} y={y + 4} fill="#fde68a" fontSize="13">{label}</text>
            </g>
          );
        })}

        {serverFaces.map((face) => (
          <polygon
            key={face.name}
            points={polygon(face.points, yaw, pitch, zoom)}
            fill={face.fill}
            stroke="#334155"
          />
        ))}
        {[0, 1, 2, 3].map((index) => (
          <polyline
            key={index}
            points={polygon([serverCorners[index], serverCorners[index + 4]], yaw, pitch, zoom)}
            fill="none"
            stroke="#64748b"
            strokeWidth="1.5"
          />
        ))}

        {plan?.drones.map((drone, index) => {
          const path = paths[index];
          const position = toFeet(plannedPosition(path, elapsedMs));
          return (
            <g key={drone.uri}>
              <polyline
                points={path.map((point) => project(toFeet(point), yaw, pitch, zoom).point.join(',')).join(' ')}
                fill="none"
                stroke={COLORS[index % COLORS.length]}
                strokeWidth="2"
                strokeOpacity="0.45"
              />
              <OrbitDot point={position} color={COLORS[index % COLORS.length]} yaw={yaw} pitch={pitch} zoom={zoom} />
            </g>
          );
        })}

        {!plan && (
          <text x="450" y="610" textAnchor="middle" fill="#cbd5e1" fontSize="18">
            Waiting for active swarm plan
          </text>
        )}

        <text x="28" y="34" fill="#cbd5e1" fontSize="15">
          Drag to orbit · Scroll to zoom · Planned position only
        </text>
      </svg>
    </div>
  );
}
