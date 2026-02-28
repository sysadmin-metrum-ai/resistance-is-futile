'use client';

import { useState } from 'react';
import { DashboardLayout, PageCard } from '@/components/DashboardLayout';
import { DroneCard } from '@/components/DroneCard';
import { DroneMap } from '@/components/DroneMap';
import { MissionQueue } from '@/components/MissionQueue';
import { LLMTerminal } from '@/components/LLMTerminal';
import { KillSwitch } from '@/components/KillSwitch';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { CollapsibleRoot, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getDrones,
  getMissions,
  cancelMission,
  healthCheckAllDrones,
} from '@/lib/api';

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const [terminalCollapsed, setTerminalCollapsed] = useState(true);

  // Fetch drones
  const { data: drones, isLoading: dronesLoading } = useQuery({
    queryKey: ['drones'],
    queryFn: getDrones,
  });

  // Fetch missions
  const { data: missions, isLoading: missionsLoading } = useQuery({
    queryKey: ['missions'],
    queryFn: getMissions,
  });

  // Fetch health data
  const { data: healthData } = useQuery({
    queryKey: ['health'],
    queryFn: healthCheckAllDrones,
    refetchInterval: 30000,
  });

  // Cancel mission mutation
  const cancelMissionMutation = useMutation({
    mutationFn: cancelMission,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['missions'] });
    },
  });

  const handleCancelMission = (missionId: string) => {
    cancelMissionMutation.mutate(missionId);
  };

  // Filter drones by state
  const activeDrones = drones?.filter(
    (d) => d.state !== 'offline' && d.enabled
  ) || [];
  const idleDrones = drones?.filter((d) => d.state === 'idle') || [];
  const offlineDrones = drones?.filter((d) => d.state === 'offline') || [];

  return (
    <DashboardLayout title="Drone Swarm Control">
      {/* Header with Kill Switch */}
      <div className="mb-6 flex items-center justify-between">
        <Alert className="flex-1 mr-4">
          <AlertTitle>API Connection</AlertTitle>
          <AlertDescription>
            {dronesLoading
              ? 'Connecting to API...'
              : `Connected. ${drones?.length || 0} drones registered.`}
          </AlertDescription>
        </Alert>
        <KillSwitch />
      </div>

      {/* Status Overview */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-6">
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
          <div className="text-4xl font-bold">{offlineDrones.length}</div>
        </PageCard>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-12 gap-4">
        {/* Left Column - Drone Cards */}
        <div className="col-span-12 lg:col-span-3 space-y-4">
          <PageCard title="Drones" description="Fleet status">
            {dronesLoading ? (
              <div className="py-4 text-center text-muted-foreground">Loading...</div>
            ) : !drones?.length ? (
              <div className="py-4 text-center text-muted-foreground">
                No drones registered
              </div>
            ) : (
              <div className="space-y-3 max-h-[500px] overflow-y-auto">
                {drones.map((drone) => (
                  <DroneCard key={drone.id} drone={drone} />
                ))}
              </div>
            )}
          </PageCard>
        </div>

        {/* Center Column - Map and Tabs */}
        <div className="col-span-12 lg:col-span-6">
          <Tabs defaultValue="map">
            <TabsList className="w-full">
              <TabsTrigger value="map" className="flex-1">Map</TabsTrigger>
              <TabsTrigger value="list" className="flex-1">List</TabsTrigger>
            </TabsList>
            <TabsContent value="map">
              <PageCard title="Fleet Map" description="Drone positions">
                <div className="h-[400px]">
                  <DroneMap drones={drones || []} />
                </div>
              </PageCard>
            </TabsContent>
            <TabsContent value="list">
              <PageCard title="Fleet Status" description="Current status of all drones">
                {dronesLoading ? (
                  <div className="py-4 text-center text-muted-foreground">Loading...</div>
                ) : !drones?.length ? (
                  <div className="py-4 text-center text-muted-foreground">
                    No drones registered
                  </div>
                ) : (
                  <div className="space-y-2">
                    {drones.map((drone) => (
                      <div
                        key={drone.id}
                        className="flex items-center justify-between rounded-lg border p-3"
                      >
                        <div className="flex items-center gap-3">
                          <span className="font-medium">{drone.name}</span>
                          <span className="text-sm text-muted-foreground">
                            {drone.state}
                          </span>
                        </div>
                        <div className="flex items-center gap-4 text-sm">
                          <span>
                            Battery: {drone.battery !== null ? `${drone.battery}%` : '-'}
                          </span>
                          <span>
                            Signal:{' '}
                            {drone.connection_quality !== null
                              ? `${drone.connection_quality}%`
                              : 'N/A'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </PageCard>
            </TabsContent>
          </Tabs>
        </div>

        {/* Right Column - Mission Queue */}
        <div className="col-span-12 lg:col-span-3">
          <MissionQueue
            missions={missions || []}
            onCancel={handleCancelMission}
            isCancelling={cancelMissionMutation.isPending ? 'cancelling' : null}
          />
        </div>
      </div>

      {/* Terminal Panel - Collapsible */}
      <div className="mt-6">
        <CollapsibleRoot defaultOpen={!terminalCollapsed}>
          <CollapsibleTrigger>
            <span className="text-sm font-medium">LLM Terminal</span>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2">
            <div className="h-[300px]">
              <LLMTerminal
                initialContent="> Drone Swarm Control Terminal Ready"
                readOnly
              />
            </div>
          </CollapsibleContent>
        </CollapsibleRoot>
      </div>
    </DashboardLayout>
  );
}
