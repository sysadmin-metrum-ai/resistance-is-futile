'use client';

import { DashboardLayout, PageCard } from '@/components/DashboardLayout';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useQuery } from '@tanstack/react-query';
import { getDrones, healthCheckAllDrones } from '@/lib/api';

export default function DashboardPage() {
  const { data: drones, isLoading: dronesLoading } = useQuery({
    queryKey: ['drones'],
    queryFn: getDrones,
  });

  const { data: healthData, isLoading: healthLoading } = useQuery({
    queryKey: ['health'],
    queryFn: healthCheckAllDrones,
    refetchInterval: 30000,
  });

  const activeDrones = drones?.filter(d => d.state !== 'offline' && d.enabled) || [];
  const idleDrones = drones?.filter(d => d.state === 'idle') || [];

  return (
    <DashboardLayout title="Drone Swarm Control">
      <div className="space-y-6">
        {/* Status Overview */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <PageCard title="Total Drones" description="Fleet size">
            <div className="text-4xl font-bold">{drones?.length || 0}</div>
          </PageCard>
          <PageCard title="Active" description="Currently flying">
            <div className="text-4xl font-bold">{activeDrones.length}</div>
          </PageCard>
          <PageCard title="Idle" description="Ready for missions">
            <div className="text-4xl font-bold">{idleDrones.length}</div>
          </PageCard>
          <PageCard title="Offline" description="Not connected">
            <div className="text-4xl font-bold">
              {drones?.filter(d => d.state === 'offline').length || 0}
            </div>
          </PageCard>
        </div>

        {/* Connection Status */}
        <Alert>
          <AlertTitle>API Connection</AlertTitle>
          <AlertDescription>
            {dronesLoading ? 'Connecting to API...' : `Connected. ${drones?.length || 0} drones registered.`}
          </AlertDescription>
        </Alert>

        {/* Drone Table */}
        <PageCard title="Fleet Status" description="Current status of all registered drones">
          {dronesLoading ? (
            <div className="py-4 text-center text-muted-foreground">Loading...</div>
          ) : !drones?.length ? (
            <div className="py-4 text-center text-muted-foreground">
              No drones registered. Use the API to register drones.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead>Battery</TableHead>
                  <TableHead>Connection</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {drones.map((drone) => (
                  <TableRow key={drone.id}>
                    <TableCell className="font-medium">{drone.name}</TableCell>
                    <TableCell>{drone.state}</TableCell>
                    <TableCell>
                      {drone.battery !== null ? `${drone.battery}%` : '-'}
                    </TableCell>
                    <TableCell>
                      {drone.connection_quality !== null
                        ? `${drone.connection_quality}%`
                        : '-'}
                    </TableCell>
                    <TableCell>
                      {drone.enabled ? (
                        <Badge variant="default">Enabled</Badge>
                      ) : (
                        <Badge variant="secondary">Disabled</Badge>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </PageCard>

        {/* Quick Actions */}
        <PageCard title="Quick Actions">
          <div className="flex gap-4">
            <Button variant="default">Refresh Status</Button>
            <Button variant="destructive">Emergency Kill Switch</Button>
          </div>
        </PageCard>
      </div>
    </DashboardLayout>
  );
}
