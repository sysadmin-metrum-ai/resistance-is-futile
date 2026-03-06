'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { DashboardLayout, PageCard } from '@/components/DashboardLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { 
  Plus, 
  Search, 
  Trash2, 
  RefreshCw, 
  Play,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  MapPin,
  Timer
} from 'lucide-react';
import { 
  getMissions, 
  getDrones,
  getFleets,
  createMission,
  cancelMission,
  abortMission
} from '@/lib/api';
import type { MissionDetailResponse, Drone, Fleet, Waypoint } from '@/types';

export default function MissionsPage() {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  
  // New mission form state
  const [missionName, setMissionName] = useState('');
  const [selectedDrone, setSelectedDrone] = useState<string>('');
  const [selectedFleet, setSelectedFleet] = useState<string>('');
  const [duration, setDuration] = useState('60');
  const [waypointsText, setWaypointsText] = useState('');
  const [missionType, setMissionType] = useState('inspection');

  // Fetch data
  const { data: missions, isLoading: missionsLoading, error: missionsError } = useQuery({
    queryKey: ['missions'],
    queryFn: getMissions,
  });

  const { data: drones } = useQuery({
    queryKey: ['drones'],
    queryFn: getDrones,
  });

  const { data: fleets } = useQuery({
    queryKey: ['fleets'],
    queryFn: () => getFleets(),
  });

  // Mutations
  const createMissionMutation = useMutation({
    mutationFn: createMission,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['missions'] });
      setIsCreateDialogOpen(false);
      resetForm();
    },
  });

  const cancelMissionMutation = useMutation({
    mutationFn: cancelMission,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['missions'] });
    },
  });

  const abortMissionMutation = useMutation({
    mutationFn: abortMission,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['missions'] });
    },
  });

  const resetForm = () => {
    setMissionName('');
    setSelectedDrone('');
    setSelectedFleet('');
    setDuration('60');
    setWaypointsText('');
    setMissionType('inspection');
  };

  // Parse waypoints from text input (format: "x,y,z; x,y,z")
  const parseWaypoints = (text: string): Waypoint[] => {
    return text
      .split(';')
      .map(wp => wp.trim())
      .filter(wp => wp.length > 0)
      .map(wp => {
        const coords = wp.split(',').map(c => parseFloat(c.trim()));
        return {
          x: coords[0] || 0,
          y: coords[1] || 0,
          z: coords[2] || 1,
        };
      });
  };

  const handleCreateMission = () => {
    const waypoints = parseWaypoints(waypointsText);
    if (waypoints.length === 0) {
      alert('Please enter at least one waypoint');
      return;
    }

    createMissionMutation.mutate({
      waypoints,
      duration_seconds: parseInt(duration) || 60,
      target_drone_id: selectedDrone ? parseInt(selectedDrone) : undefined,
      callback_url: undefined,
    });
  };

  const handleCancel = (missionId: string) => {
    if (confirm('Are you sure you want to cancel this mission?')) {
      cancelMissionMutation.mutate(missionId);
    }
  };

  const handleAbort = (missionId: string) => {
    if (confirm('Are you sure you want to abort this mission? This will immediately stop the drone.')) {
      abortMissionMutation.mutate(missionId);
    }
  };

  // Filter missions
  const filteredMissions = missions?.filter((mission: MissionDetailResponse) => {
    const matchesSearch = mission.id.toString().includes(searchTerm);
    const matchesStatus = selectedStatus === 'all' || mission.status === selectedStatus;
    return matchesSearch && matchesStatus;
  }) || [];

  // Group by status
  const pendingMissions = filteredMissions.filter((m: MissionDetailResponse) => m.status === 'pending');
  const runningMissions = filteredMissions.filter((m: MissionDetailResponse) => m.status === 'running');
  const completedMissions = filteredMissions.filter((m: MissionDetailResponse) => m.status === 'completed');
  const failedMissions = filteredMissions.filter((m: MissionDetailResponse) => m.status === 'failed');
  const cancelledMissions = filteredMissions.filter((m: MissionDetailResponse) => m.status === 'cancelled');

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <Clock className="h-4 w-4" />;
      case 'running':
        return <Play className="h-4 w-4" />;
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'cancelled':
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      default:
        return <Clock className="h-4 w-4" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'pending':
        return <Badge variant="outline">Pending</Badge>;
      case 'running':
        return <Badge variant="default">Running</Badge>;
      case 'completed':
        return <Badge variant="secondary">Completed</Badge>;
      case 'failed':
        return <Badge variant="destructive">Failed</Badge>;
      case 'cancelled':
        return <Badge variant="outline" className="text-yellow-600">Cancelled</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  return (
    <DashboardLayout title="Mission Control">
      {/* Header Stats */}
      <div className="grid gap-4 md:grid-cols-6 mb-6">
        <PageCard title="Total" description="All missions">
          <div className="text-3xl font-bold">{missions?.length || 0}</div>
        </PageCard>
        <PageCard title="Pending" description="In queue">
          <div className="text-3xl font-bold text-yellow-600">{pendingMissions.length}</div>
        </PageCard>
        <PageCard title="Running" description="Active">
          <div className="text-3xl font-bold text-blue-600">{runningMissions.length}</div>
        </PageCard>
        <PageCard title="Completed" description="Finished">
          <div className="text-3xl font-bold text-green-600">{completedMissions.length}</div>
        </PageCard>
        <PageCard title="Failed" description="Errors">
          <div className="text-3xl font-bold text-red-600">{failedMissions.length}</div>
        </PageCard>
        <PageCard title="Cancelled" description="Aborted">
          <div className="text-3xl font-bold text-gray-500">{cancelledMissions.length}</div>
        </PageCard>
      </div>

      {/* Error Alert */}
      {missionsError && (
        <Alert variant="destructive" className="mb-6">
          <AlertTitle>Error loading missions</AlertTitle>
          <AlertDescription>Failed to fetch mission data. Please try again.</AlertDescription>
        </Alert>
      )}

      {/* Filters and Actions */}
      <div className="flex flex-col md:flex-row gap-4 mb-6">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by mission ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
        
        <Select value={selectedStatus} onValueChange={setSelectedStatus}>
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="running">Running</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
            <SelectItem value="cancelled">Cancelled</SelectItem>
          </SelectContent>
        </Select>

        <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              New Mission
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Create New Mission</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div>
                <Label htmlFor="type">Mission Type</Label>
                <Select value={missionType} onValueChange={setMissionType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="inspection">Inspection</SelectItem>
                    <SelectItem value="patrol">Patrol</SelectItem>
                    <SelectItem value="security">Security</SelectItem>
                    <SelectItem value="cable-check">Cable Check</SelectItem>
                    <SelectItem value="emergency">Emergency</SelectItem>
                    <SelectItem value="custom">Custom</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="drone">Assign Drone (Optional)</Label>
                <Select value={selectedDrone} onValueChange={setSelectedDrone}>
                  <SelectTrigger>
                    <SelectValue placeholder="Auto-assign" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">Auto-assign</SelectItem>
                    {drones?.filter((d: Drone) => d.state === 'idle').map((drone: Drone) => (
                      <SelectItem key={drone.id} value={String(drone.id)}>
                        {drone.name} ({drone.battery}% battery)
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="duration">
                  Duration (seconds)
                </Label>
                <Input
                  id="duration"
                  type="number"
                  value={duration}
                  onChange={(e) => setDuration(e.target.value)}
                  min="10"
                  max="3600"
                />
              </div>

              <div>
                <Label htmlFor="waypoints">
                  Waypoints (format: x,y,z; x,y,z)
                </Label>
                <textarea
                  id="waypoints"
                  className="w-full min-h-[100px] px-3 py-2 border rounded-md text-sm"
                  placeholder="0,0,1; 2,0,1; 2,2,1; 0,2,1"
                  value={waypointsText}
                  onChange={(e) => setWaypointsText(e.target.value)}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Enter waypoints separated by semicolons. Format: x,y,z (in meters)
                </p>
              </div>

              <Button 
                onClick={handleCreateMission} 
                disabled={!waypointsText || createMissionMutation.isPending}
                className="w-full"
              >
                {createMissionMutation.isPending ? 'Creating...' : 'Create Mission'}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Missions List */}
      {missionsLoading ? (
        <div className="text-center py-12">
          <RefreshCw className="mx-auto h-8 w-8 animate-spin text-muted-foreground" />
          <p className="mt-2 text-muted-foreground">Loading missions...</p>
        </div>
      ) : filteredMissions.length === 0 ? (
        <div className="text-center py-12 border rounded-lg">
          <MapPin className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">No missions found</h3>
          <p className="text-muted-foreground">
            {searchTerm || selectedStatus !== 'all'
              ? 'Try adjusting your filters'
              : 'Get started by creating your first mission'}
          </p>
        </div>
      ) : (
        <Tabs defaultValue="all" className="space-y-4">
          <TabsList>
            <TabsTrigger value="all">All ({filteredMissions.length})</TabsTrigger>
            <TabsTrigger value="pending">Pending ({pendingMissions.length})</TabsTrigger>
            <TabsTrigger value="running">Running ({runningMissions.length})</TabsTrigger>
            <TabsTrigger value="completed">Completed ({completedMissions.length})</TabsTrigger>
            <TabsTrigger value="failed">Failed ({failedMissions.length})</TabsTrigger>
          </TabsList>

          <TabsContent value="all">
            <div className="space-y-2">
              {filteredMissions.map((mission: MissionDetailResponse) => (
                <MissionRow 
                  key={mission.id} 
                  mission={mission} 
                  drones={drones}
                  onCancel={() => handleCancel(String(mission.id))}
                  onAbort={() => handleAbort(String(mission.id))}
                  getStatusBadge={getStatusBadge}
                  getStatusIcon={getStatusIcon}
                />
              ))}
            </div>
          </TabsContent>

          <TabsContent value="pending">
            <div className="space-y-2">
              {pendingMissions.map((mission: MissionDetailResponse) => (
                <MissionRow 
                  key={mission.id} 
                  mission={mission} 
                  drones={drones}
                  onCancel={() => handleCancel(String(mission.id))}
                  onAbort={() => handleAbort(String(mission.id))}
                  getStatusBadge={getStatusBadge}
                  getStatusIcon={getStatusIcon}
                />
              ))}
            </div>
          </TabsContent>

          <TabsContent value="running">
            <div className="space-y-2">
              {runningMissions.map((mission: MissionDetailResponse) => (
                <MissionRow 
                  key={mission.id} 
                  mission={mission} 
                  drones={drones}
                  onCancel={() => handleCancel(String(mission.id))}
                  onAbort={() => handleAbort(String(mission.id))}
                  getStatusBadge={getStatusBadge}
                  getStatusIcon={getStatusIcon}
                />
              ))}
            </div>
          </TabsContent>

          <TabsContent value="completed">
            <div className="space-y-2">
              {completedMissions.map((mission: MissionDetailResponse) => (
                <MissionRow 
                  key={mission.id} 
                  mission={mission} 
                  drones={drones}
                  onCancel={() => handleCancel(String(mission.id))}
                  onAbort={() => handleAbort(String(mission.id))}
                  getStatusBadge={getStatusBadge}
                  getStatusIcon={getStatusIcon}
                />
              ))}
            </div>
          </TabsContent>

          <TabsContent value="failed">
            <div className="space-y-2">
              {failedMissions.map((mission: MissionDetailResponse) => (
                <MissionRow 
                  key={mission.id} 
                  mission={mission} 
                  drones={drones}
                  onCancel={() => handleCancel(String(mission.id))}
                  onAbort={() => handleAbort(String(mission.id))}
                  getStatusBadge={getStatusBadge}
                  getStatusIcon={getStatusIcon}
                />
              ))}
            </div>
          </TabsContent>
        </Tabs>
      )}
    </DashboardLayout>
  );
}

// Mission Row Component
interface MissionRowProps {
  mission: MissionDetailResponse;
  drones?: Drone[];
  onCancel: () => void;
  onAbort: () => void;
  getStatusBadge: (status: string) => React.ReactNode;
  getStatusIcon: (status: string) => React.ReactNode;
}

function MissionRow({ mission, drones, onCancel, onAbort, getStatusBadge, getStatusIcon }: MissionRowProps) {
  const drone = drones?.find(d => d.id === mission.drone_id);
  
  return (
    <div className="flex items-center justify-between p-4 border rounded-lg hover:bg-accent/50 transition-colors">
      <div className="flex items-center gap-4">
        {getStatusIcon(mission.status)}
        <div>
          <div className="flex items-center gap-2">
            <span className="font-medium">Mission #{mission.id}</span>
            {getStatusBadge(mission.status)}
          </div>
          <div className="flex items-center gap-4 text-sm text-muted-foreground mt-1">
            <span className="flex items-center gap-1">
              <Timer className="h-3 w-3" />
              {mission.duration_seconds}s
            </span>
            <span className="flex items-center gap-1">
              <MapPin className="h-3 w-3" />
              {mission.waypoints?.length || 0} waypoints
            </span>
            {drone && (
              <span>Drone: {drone.name}</span>
            )}
          </div>
        </div>
      </div>
      
      <div className="flex items-center gap-2">
        {(mission.status === 'pending' || mission.status === 'running') && (
          <>
            <Button 
              variant="outline" 
              size="sm"
              onClick={onCancel}
            >
              Cancel
            </Button>
            {mission.status === 'running' && (
              <Button 
                variant="destructive" 
                size="sm"
                onClick={onAbort}
              >
                Abort
              </Button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
