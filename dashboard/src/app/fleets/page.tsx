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
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { 
  Plus, 
  Search, 
  Trash2, 
  RefreshCw, 
  Users,
  Settings,
  Edit,
  ChevronRight,
  LayoutGrid,
  List
} from 'lucide-react';
import { 
  getFleets, 
  getFleetDrones,
  createFleet,
  updateFleet,
  deleteFleet,
  bulkAssignDronesToFleet,
  getDrones
} from '@/lib/api';
import type { Fleet, Drone } from '@/types';

const CATEGORY_COLORS: Record<string, string> = {
  inventory: '#22c55e',
  security: '#ef4444',
  'cable-monitoring': '#3b82f6',
  inspection: '#f59e0b',
  emergency: '#dc2626',
  general: '#6b7280',
};

const CATEGORY_LABELS: Record<string, string> = {
  inventory: 'Inventory',
  security: 'Security',
  'cable-monitoring': 'Cable Monitoring',
  inspection: 'Inspection',
  emergency: 'Emergency',
  general: 'General',
};

export default function FleetsPage() {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [selectedFleet, setSelectedFleet] = useState<Fleet | null>(null);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  
  // New fleet form state
  const [newFleetName, setNewFleetName] = useState('');
  const [newFleetDescription, setNewFleetDescription] = useState('');
  const [newFleetCategory, setNewFleetCategory] = useState('general');
  const [newFleetMaxDrones, setNewFleetMaxDrones] = useState('10');

  // Edit fleet form state
  const [editFleetName, setEditFleetName] = useState('');
  const [editFleetDescription, setEditFleetDescription] = useState('');
  const [editFleetMaxDrones, setEditFleetMaxDrones] = useState('');

  // Fetch data
  const { data: fleets, isLoading: fleetsLoading, error: fleetsError } = useQuery({
    queryKey: ['fleets'],
    queryFn: () => getFleets(),
  });

  const { data: drones } = useQuery({
    queryKey: ['drones'],
    queryFn: getDrones,
  });

  // Mutations
  const createFleetMutation = useMutation({
    mutationFn: createFleet,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fleets'] });
      setIsCreateDialogOpen(false);
      resetCreateForm();
    },
  });

  const updateFleetMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: { name?: string; description?: string; max_drones?: number } }) =>
      updateFleet(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fleets'] });
      setSelectedFleet(null);
    },
  });

  const deleteFleetMutation = useMutation({
    mutationFn: deleteFleet,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fleets'] });
    },
  });

  const bulkAssignMutation = useMutation({
    mutationFn: ({ fleetId, droneIds }: { fleetId: number; droneIds: number[] }) =>
      bulkAssignDronesToFleet(fleetId, { drone_ids: droneIds }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drones'] });
      queryClient.invalidateQueries({ queryKey: ['fleets'] });
    },
  });

  const resetCreateForm = () => {
    setNewFleetName('');
    setNewFleetDescription('');
    setNewFleetCategory('general');
    setNewFleetMaxDrones('10');
  };

  const handleCreateFleet = () => {
    if (!newFleetName) return;
    
    createFleetMutation.mutate({
      name: newFleetName,
      description: newFleetDescription,
      category: newFleetCategory,
      max_drones: parseInt(newFleetMaxDrones) || 10,
    });
  };

  const handleUpdateFleet = () => {
    if (!selectedFleet) return;
    
    const updates: { name?: string; description?: string; max_drones?: number } = {};
    if (editFleetName) updates.name = editFleetName;
    if (editFleetDescription) updates.description = editFleetDescription;
    if (editFleetMaxDrones) updates.max_drones = parseInt(editFleetMaxDrones);
    
    updateFleetMutation.mutate({ id: selectedFleet.id, data: updates });
  };

  const handleDeleteFleet = (fleetId: number, fleetName: string) => {
    if (confirm(`Are you sure you want to delete fleet "${fleetName}"? Drones will be unassigned.`)) {
      deleteFleetMutation.mutate(fleetId);
    }
  };

  const handleAssignDrones = (fleetId: number) => {
    // Get unassigned idle drones
    const unassignedDrones = drones?.filter((d: Drone) => !d.fleet_id && d.state === 'idle');
    if (!unassignedDrones || unassignedDrones.length === 0) {
      alert('No unassigned idle drones available');
      return;
    }
    
    const droneIds = unassignedDrones.slice(0, 5).map((d: Drone) => d.id);
    bulkAssignMutation.mutate({ fleetId, droneIds });
  };

  const openEditDialog = (fleet: Fleet) => {
    setSelectedFleet(fleet);
    setEditFleetName(fleet.name);
    setEditFleetDescription(fleet.description || '');
    setEditFleetMaxDrones(String(fleet.max_drones));
  };

  // Filter fleets
  const filteredFleets = fleets?.filter((fleet: Fleet) => {
    const matchesSearch = 
      fleet.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (fleet.description && fleet.description.toLowerCase().includes(searchTerm.toLowerCase()));
    const matchesCategory = selectedCategory === 'all' || fleet.category === selectedCategory;
    return matchesSearch && matchesCategory;
  }) || [];

  // Calculate stats
  const totalFleets = fleets?.length || 0;
  const totalDronesInFleets = fleets?.reduce((acc: number, f: Fleet) => acc + (f.drone_count || 0), 0) || 0;
  const avgDronesPerFleet = totalFleets > 0 ? Math.round(totalDronesInFleets / totalFleets) : 0;

  return (
    <DashboardLayout title="Fleet Management">
      {/* Header Stats */}
      <div className="grid gap-4 md:grid-cols-4 mb-6">
        <PageCard title="Total Fleets" description="Active groups">
          <div className="text-3xl font-bold">{totalFleets}</div>
        </PageCard>
        <PageCard title="Drones in Fleets" description="Assigned drones">
          <div className="text-3xl font-bold text-blue-600">{totalDronesInFleets}</div>
        </PageCard>
        <PageCard title="Unassigned Drones" description="Available">
          <div className="text-3xl font-bold text-yellow-600">
            {drones?.filter((d: Drone) => !d.fleet_id).length || 0}
          </div>
        </PageCard>
        <PageCard title="Avg per Fleet" description="Drones">
          <div className="text-3xl font-bold">{avgDronesPerFleet}</div>
        </PageCard>
      </div>

      {/* Error Alert */}
      {fleetsError && (
        <Alert variant="destructive" className="mb-6">
          <AlertTitle>Error loading fleets</AlertTitle>
          <AlertDescription>Failed to fetch fleet data. Please try again.</AlertDescription>
        </Alert>
      )}

      {/* Filters and Actions */}
      <div className="flex flex-col md:flex-row gap-4 mb-6">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search fleets..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
        
        <Select value={selectedCategory} onValueChange={setSelectedCategory}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Filter by category" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Categories</SelectItem>
            <SelectItem value="inventory">Inventory</SelectItem>
            <SelectItem value="security">Security</SelectItem>
            <SelectItem value="cable-monitoring">Cable Monitoring</SelectItem>
            <SelectItem value="inspection">Inspection</SelectItem>
            <SelectItem value="emergency">Emergency</SelectItem>
            <SelectItem value="general">General</SelectItem>
          </SelectContent>
        </Select>

        <div className="flex gap-2">
          <Button
            variant={viewMode === 'grid' ? 'default' : 'outline'}
            size="icon"
            onClick={() => setViewMode('grid')}
          >
            <LayoutGrid className="h-4 w-4" />
          </Button>
          <Button
            variant={viewMode === 'list' ? 'default' : 'outline'}
            size="icon"
            onClick={() => setViewMode('list')}
          >
            <List className="h-4 w-4" />
          </Button>
        </div>

        <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Create Fleet
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New Fleet</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div>
                <Label htmlFor="name">Fleet Name</Label>
                <Input
                  id="name"
                  placeholder="e.g., security-patrol-north"
                  value={newFleetName}
                  onChange={(e) => setNewFleetName(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="description">Description</Label>
                <Input
                  id="description"
                  placeholder="What this fleet is used for..."
                  value={newFleetDescription}
                  onChange={(e) => setNewFleetDescription(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="category">Category</Label>
                <Select value={newFleetCategory} onValueChange={setNewFleetCategory}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="inventory">Inventory</SelectItem>
                    <SelectItem value="security">Security</SelectItem>
                    <SelectItem value="cable-monitoring">Cable Monitoring</SelectItem>
                    <SelectItem value="inspection">Inspection</SelectItem>
                    <SelectItem value="emergency">Emergency</SelectItem>
                    <SelectItem value="general">General</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label htmlFor="maxDrones">Max Drones</Label>
                <Input
                  id="maxDrones"
                  type="number"
                  value={newFleetMaxDrones}
                  onChange={(e) => setNewFleetMaxDrones(e.target.value)}
                  min="1"
                  max="100"
                />
              </div>
              <Button 
                onClick={handleCreateFleet} 
                disabled={!newFleetName || createFleetMutation.isPending}
                className="w-full"
              >
                {createFleetMutation.isPending ? 'Creating...' : 'Create Fleet'}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Edit Fleet Dialog */}
      <Dialog open={!!selectedFleet} onOpenChange={(open) => !open && setSelectedFleet(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Fleet</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="editName">Fleet Name</Label>
              <Input
                id="editName"
                value={editFleetName}
                onChange={(e) => setEditFleetName(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="editDescription">Description</Label>
              <Input
                id="editDescription"
                value={editFleetDescription}
                onChange={(e) => setEditFleetDescription(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="editMaxDrones">Max Drones</Label>
              <Input
                id="editMaxDrones"
                type="number"
                value={editFleetMaxDrones}
                onChange={(e) => setEditFleetMaxDrones(e.target.value)}
                min="1"
                max="100"
              />
            </div>
            <Button 
              onClick={handleUpdateFleet} 
              disabled={updateFleetMutation.isPending}
              className="w-full"
            >
              {updateFleetMutation.isPending ? 'Updating...' : 'Update Fleet'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Fleets Display */}
      {fleetsLoading ? (
        <div className="text-center py-12">
          <RefreshCw className="mx-auto h-8 w-8 animate-spin text-muted-foreground" />
          <p className="mt-2 text-muted-foreground">Loading fleets...</p>
        </div>
      ) : filteredFleets.length === 0 ? (
        <div className="text-center py-12 border rounded-lg">
          <Users className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">No fleets found</h3>
          <p className="text-muted-foreground">
            {searchTerm || selectedCategory !== 'all'
              ? 'Try adjusting your filters'
              : 'Get started by creating your first fleet'}
          </p>
        </div>
      ) : viewMode === 'grid' ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredFleets.map((fleet: Fleet) => (
            <FleetCard 
              key={fleet.id} 
              fleet={fleet} 
              onEdit={() => openEditDialog(fleet)}
              onDelete={() => handleDeleteFleet(fleet.id, fleet.name)}
              onAssignDrones={() => handleAssignDrones(fleet.id)}
              isAssigning={bulkAssignMutation.isPending}
            />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {filteredFleets.map((fleet: Fleet) => (
            <FleetRow 
              key={fleet.id} 
              fleet={fleet}
              onEdit={() => openEditDialog(fleet)}
              onDelete={() => handleDeleteFleet(fleet.id, fleet.name)}
              onAssignDrones={() => handleAssignDrones(fleet.id)}
              isAssigning={bulkAssignMutation.isPending}
            />
          ))}
        </div>
      )}
    </DashboardLayout>
  );
}

// Fleet Card Component
interface FleetCardProps {
  fleet: Fleet;
  onEdit: () => void;
  onDelete: () => void;
  onAssignDrones: () => void;
  isAssigning: boolean;
}

function FleetCard({ fleet, onEdit, onDelete, onAssignDrones, isAssigning }: FleetCardProps) {
  const capacityPercent = Math.round(((fleet.drone_count || 0) / fleet.max_drones) * 100);
  
  return (
    <Card className="transition-shadow hover:shadow-md">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div 
              className="w-4 h-4 rounded-full" 
              style={{ backgroundColor: fleet.color || CATEGORY_COLORS[fleet.category] }}
            />
            <CardTitle className="text-lg">{fleet.name}</CardTitle>
          </div>
          <Badge variant={fleet.enabled ? 'default' : 'secondary'}>
            {fleet.enabled ? 'Active' : 'Disabled'}
          </Badge>
        </div>
        <Badge variant="outline">{CATEGORY_LABELS[fleet.category] || fleet.category}</Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground line-clamp-2">
          {fleet.description || 'No description'}
        </p>
        
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>Capacity</span>
            <span>{fleet.drone_count || 0} / {fleet.max_drones}</span>
          </div>
          <div className="h-2 bg-secondary rounded-full overflow-hidden">
            <div 
              className="h-full transition-all"
              style={{ 
                width: `${capacityPercent}%`,
                backgroundColor: fleet.color || CATEGORY_COLORS[fleet.category]
              }}
            />
          </div>
        </div>

        <div className="flex gap-2 pt-2">
          <Button variant="outline" size="sm" className="flex-1" onClick={onEdit}>
            <Edit className="mr-1 h-3 w-3" />
            Edit
          </Button>
          <Button 
            variant="outline" 
            size="sm" 
            className="flex-1"
            onClick={onAssignDrones}
            disabled={isAssigning || (fleet.drone_count || 0) >= fleet.max_drones}
          >
            <Plus className="mr-1 h-3 w-3" />
            Add Drones
          </Button>
          <Button variant="ghost" size="sm" onClick={onDelete}>
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// Fleet Row Component
interface FleetRowProps {
  fleet: Fleet;
  onEdit: () => void;
  onDelete: () => void;
  onAssignDrones: () => void;
  isAssigning: boolean;
}

function FleetRow({ fleet, onEdit, onDelete, onAssignDrones, isAssigning }: FleetRowProps) {
  return (
    <div className="flex items-center justify-between p-4 border rounded-lg hover:bg-accent/50 transition-colors">
      <div className="flex items-center gap-4">
        <div 
          className="w-4 h-4 rounded-full" 
          style={{ backgroundColor: fleet.color || CATEGORY_COLORS[fleet.category] }}
        />
        <div>
          <div className="flex items-center gap-2">
            <span className="font-medium">{fleet.name}</span>
            <Badge variant="outline">{CATEGORY_LABELS[fleet.category] || fleet.category}</Badge>
            <Badge variant={fleet.enabled ? 'default' : 'secondary'}>
              {fleet.enabled ? 'Active' : 'Disabled'}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            {fleet.drone_count || 0} / {fleet.max_drones} drones
            {fleet.description && ` • ${fleet.description}`}
          </p>
        </div>
      </div>
      
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={onEdit}>
          <Edit className="mr-1 h-3 w-3" />
          Edit
        </Button>
        <Button 
          variant="outline" 
          size="sm"
          onClick={onAssignDrones}
          disabled={isAssigning || (fleet.drone_count || 0) >= fleet.max_drones}
        >
          <Plus className="mr-1 h-3 w-3" />
          Add Drones
        </Button>
        <Button variant="ghost" size="sm" onClick={onDelete}>
          <Trash2 className="h-4 w-4 text-destructive" />
        </Button>
      </div>
    </div>
  );
}
