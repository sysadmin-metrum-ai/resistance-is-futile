'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { DashboardLayout, PageCard } from '@/components/DashboardLayout';
import { DroneCard } from '@/components/DroneCard';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Plus, Search, Trash2, RefreshCw, Users } from 'lucide-react';
import { 
  getDrones, 
  getFleets, 
  registerDrone, 
  unregisterDrone,
  assignDroneToFleet,
  unassignDroneFromFleet,
  discoverDrones 
} from '@/lib/api';
import type { Drone, Fleet } from '@/types';

export default function DronesPage() {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedFleet, setSelectedFleet] = useState<string>('all');
  const [selectedState, setSelectedState] = useState<string>('all');
  const [isRegisterDialogOpen, setIsRegisterDialogOpen] = useState(false);
  const [newDroneUri, setNewDroneUri] = useState('');
  const [newDroneName, setNewDroneName] = useState('');
  const [newDroneFleet, setNewDroneFleet] = useState<string>('');

  // Fetch data
  const { data: drones, isLoading: dronesLoading, error: dronesError } = useQuery({
    queryKey: ['drones'],
    queryFn: getDrones,
  });

  const { data: fleets, isLoading: fleetsLoading } = useQuery({
    queryKey: ['fleets'],
    queryFn: () => getFleets(),
  });

  // Mutations
  const registerMutation = useMutation({
    mutationFn: registerDrone,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drones'] });
      setIsRegisterDialogOpen(false);
      setNewDroneUri('');
      setNewDroneName('');
      setNewDroneFleet('');
    },
  });

  const unregisterMutation = useMutation({
    mutationFn: unregisterDrone,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drones'] });
    },
  });

  const assignToFleetMutation = useMutation({
    mutationFn: ({ droneId, fleetId }: { droneId: number; fleetId: number }) =>
      assignDroneToFleet(fleetId, { drone_id: droneId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drones'] });
      queryClient.invalidateQueries({ queryKey: ['fleets'] });
    },
  });

  const unassignFromFleetMutation = useMutation({
    mutationFn: ({ droneId, fleetId }: { droneId: number; fleetId: number }) =>
      unassignDroneFromFleet(fleetId, droneId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drones'] });
      queryClient.invalidateQueries({ queryKey: ['fleets'] });
    },
  });

  const discoverMutation = useMutation({
    mutationFn: discoverDrones,
  });

  // Filter drones
  const filteredDrones = drones?.filter((drone: Drone) => {
    const matchesSearch = 
      drone.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      drone.uri.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesFleet = selectedFleet === 'all' || String(drone.fleet_id) === selectedFleet;
    const matchesState = selectedState === 'all' || drone.state === selectedState;
    return matchesSearch && matchesFleet && matchesState;
  }) || [];

  // Group drones by fleet
  const dronesByFleet = fleets?.reduce((acc: Record<string, Drone[]>, fleet: Fleet) => {
    acc[fleet.id] = filteredDrones.filter((d: Drone) => d.fleet_id === fleet.id);
    return acc;
  }, {}) || {};

  const unassignedDrones = filteredDrones.filter((d: Drone) => !d.fleet_id);

  const handleRegister = () => {
    if (!newDroneUri || !newDroneName) return;
    
    registerMutation.mutate({
      uri: newDroneUri,
      name: newDroneName,
      fleet_id: newDroneFleet ? parseInt(newDroneFleet) : undefined,
    });
  };

  const handleUnregister = (droneId: number) => {
    if (confirm('Are you sure you want to unregister this drone?')) {
      unregisterMutation.mutate(droneId);
    }
  };

  // Calculate stats
  const totalDrones = drones?.length || 0;
  const idleDrones = drones?.filter((d: Drone) => d.state === 'idle').length || 0;
  const busyDrones = drones?.filter((d: Drone) => d.state === 'busy').length || 0;
  const offlineDrones = drones?.filter((d: Drone) => d.state === 'offline').length || 0;
  const errorDrones = drones?.filter((d: Drone) => d.state === 'error').length || 0;

  return (
    <DashboardLayout title="Drone Management">
      {/* Header Stats */}
      <div className="grid gap-4 md:grid-cols-5 mb-6">
        <PageCard title="Total Drones" description="In fleet">
          <div className="text-3xl font-bold">{totalDrones}</div>
        </PageCard>
        <PageCard title="Idle" description="Ready">
          <div className="text-3xl font-bold text-green-600">{idleDrones}</div>
        </PageCard>
        <PageCard title="Busy" description="In mission">
          <div className="text-3xl font-bold text-yellow-600">{busyDrones}</div>
        </PageCard>
        <PageCard title="Offline" description="Disconnected">
          <div className="text-3xl font-bold text-gray-500">{offlineDrones}</div>
        </PageCard>
        <PageCard title="Error" description="Needs attention">
          <div className="text-3xl font-bold text-red-600">{errorDrones}</div>
        </PageCard>
      </div>

      {/* Error Alert */}
      {dronesError && (
        <Alert variant="destructive" className="mb-6">
          <AlertTitle>Error loading drones</AlertTitle>
          <AlertDescription>Failed to fetch drone data. Please try again.</AlertDescription>
        </Alert>
      )}

      {/* Filters and Actions */}
      <div className="flex flex-col md:flex-row gap-4 mb-6">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search drones by name or URI..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
        
        <Select value={selectedFleet} onValueChange={setSelectedFleet}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Filter by fleet" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Fleets</SelectItem>
            {fleets?.map((fleet: Fleet) => (
              <SelectItem key={fleet.id} value={String(fleet.id)}>
                {fleet.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={selectedState} onValueChange={setSelectedState}>
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Filter by state" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All States</SelectItem>
            <SelectItem value="idle">Idle</SelectItem>
            <SelectItem value="busy">Busy</SelectItem>
            <SelectItem value="offline">Offline</SelectItem>
            <SelectItem value="error">Error</SelectItem>
          </SelectContent>
        </Select>

        <Button
          variant="outline"
          onClick={() => discoverMutation.mutate()}
          disabled={discoverMutation.isPending}
        >
          <RefreshCw className={`mr-2 h-4 w-4 ${discoverMutation.isPending ? 'animate-spin' : ''}`} />
          Discover
        </Button>

        <Dialog open={isRegisterDialogOpen} onOpenChange={setIsRegisterDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Register Drone
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Register New Drone</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div>
                <Label htmlFor="uri">Drone URI</Label>
                <Input
                  id="uri"
                  placeholder="radio://0/80/1M/100M"
                  value={newDroneUri}
                  onChange={(e) => setNewDroneUri(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  placeholder="drone-1"
                  value={newDroneName}
                  onChange={(e) => setNewDroneName(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="fleet">Fleet (Optional)</Label>
                <Select 
                  value={newDroneFleet || "none"} 
                  onValueChange={(value) => setNewDroneFleet(value === "none" ? "" : value)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select fleet" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None</SelectItem>
                    {fleets?.map((fleet: Fleet) => (
                      <SelectItem key={fleet.id} value={String(fleet.id)}>
                        {fleet.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button 
                onClick={handleRegister} 
                disabled={!newDroneUri || !newDroneName || registerMutation.isPending}
                className="w-full"
              >
                {registerMutation.isPending ? 'Registering...' : 'Register Drone'}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Drones List */}
      {dronesLoading ? (
        <div className="text-center py-12">
          <RefreshCw className="mx-auto h-8 w-8 animate-spin text-muted-foreground" />
          <p className="mt-2 text-muted-foreground">Loading drones...</p>
        </div>
      ) : filteredDrones.length === 0 ? (
        <div className="text-center py-12 border rounded-lg">
          <Users className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">No drones found</h3>
          <p className="text-muted-foreground">
            {searchTerm || selectedFleet !== 'all' || selectedState !== 'all'
              ? 'Try adjusting your filters'
              : 'Get started by registering your first drone'}
          </p>
        </div>
      ) : (
        <Tabs defaultValue="all" className="space-y-4">
          <TabsList>
            <TabsTrigger value="all">All Drones ({filteredDrones.length})</TabsTrigger>
            <TabsTrigger value="by-fleet">By Fleet</TabsTrigger>
          </TabsList>

          <TabsContent value="all">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {filteredDrones.map((drone: Drone) => (
                <DroneCard
                  key={drone.id}
                  drone={drone}
                  fleets={fleets}
                  onAssignToFleet={(fleetId) => assignToFleetMutation.mutate({ droneId: drone.id, fleetId })}
                  onRemoveFromFleet={(fleetId) => unassignFromFleetMutation.mutate({ droneId: drone.id, fleetId })}
                  onUnregister={() => handleUnregister(drone.id)}
                />
              ))}
            </div>
          </TabsContent>

          <TabsContent value="by-fleet">
            <div className="space-y-6">
              {/* Unassigned Drones */}
              {unassignedDrones.length > 0 && (
                <div>
                  <h3 className="text-lg font-semibold mb-3">Unassigned ({unassignedDrones.length})</h3>
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {unassignedDrones.map((drone: Drone) => (
                      <DroneCard
                        key={drone.id}
                        drone={drone}
                        fleets={fleets}
                        onAssignToFleet={(fleetId) => assignToFleetMutation.mutate({ droneId: drone.id, fleetId })}
                        onUnregister={() => handleUnregister(drone.id)}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Drones by Fleet */}
              {fleets?.map((fleet: Fleet) => {
                const fleetDrones = dronesByFleet[fleet.id] || [];
                if (fleetDrones.length === 0) return null;
                
                return (
                  <div key={fleet.id}>
                    <div className="flex items-center gap-2 mb-3">
                      <div 
                        className="w-4 h-4 rounded-full" 
                        style={{ backgroundColor: fleet.color }}
                      />
                      <h3 className="text-lg font-semibold">{fleet.name}</h3>
                      <span className="text-sm text-muted-foreground">
                        ({fleetDrones.length} drones)
                      </span>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                      {fleetDrones.map((drone: Drone) => (
                        <DroneCard
                          key={drone.id}
                          drone={drone}
                          fleets={fleets}
                          onRemoveFromFleet={() => unassignFromFleetMutation.mutate({ droneId: drone.id, fleetId: fleet.id })}
                          onUnregister={() => handleUnregister(drone.id)}
                        />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </TabsContent>
        </Tabs>
      )}
    </DashboardLayout>
  );
}
