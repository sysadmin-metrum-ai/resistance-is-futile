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
  Radio,
  MapPin,
  Activity,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  Settings,
  Edit,
  LayoutGrid,
  List,
  Wifi,
  WifiOff
} from 'lucide-react';
import { 
  getAnchors,
  getAnchorSystemStatus,
  createAnchor,
  updateAnchor,
  updateAnchorPosition,
  deleteAnchor,
  anchorHeartbeat
} from '@/lib/api';
import type { Anchor, AnchorSystemStatus } from '@/types';

const MODE_LABELS: Record<string, string> = {
  'TWR': 'Two-Way Ranging',
  'TDoA2': 'Time Difference of Arrival 2',
  'TDoA3': 'Time Difference of Arrival 3',
};

export default function AnchorsPage() {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [selectedMode, setSelectedMode] = useState<string>('all');
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [selectedAnchor, setSelectedAnchor] = useState<Anchor | null>(null);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  
  // New anchor form state
  const [newAnchorId, setNewAnchorId] = useState('');
  const [newAnchorName, setNewAnchorName] = useState('');
  const [newAnchorX, setNewAnchorX] = useState('');
  const [newAnchorY, setNewAnchorY] = useState('');
  const [newAnchorZ, setNewAnchorZ] = useState('');
  const [newAnchorMode, setNewAnchorMode] = useState('TWR');
  const [newAnchorNotes, setNewAnchorNotes] = useState('');

  // Edit position form state
  const [editX, setEditX] = useState('');
  const [editY, setEditY] = useState('');
  const [editZ, setEditZ] = useState('');

  // Fetch data
  const { data: anchorsData, isLoading: anchorsLoading, error: anchorsError } = useQuery({
    queryKey: ['anchors'],
    queryFn: () => getAnchors(),
  });

  const { data: systemStatus, isLoading: statusLoading } = useQuery({
    queryKey: ['anchor-system-status'],
    queryFn: getAnchorSystemStatus,
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  const anchors = anchorsData?.anchors || [];

  // Mutations
  const createAnchorMutation = useMutation({
    mutationFn: createAnchor,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anchors'] });
      queryClient.invalidateQueries({ queryKey: ['anchor-system-status'] });
      setIsCreateDialogOpen(false);
      resetCreateForm();
    },
  });

  const updateAnchorMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: { name?: string; status?: string; notes?: string } }) =>
      updateAnchor(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anchors'] });
    },
  });

  const updatePositionMutation = useMutation({
    mutationFn: ({ id, x, y, z }: { id: number; x: number; y: number; z: number }) =>
      updateAnchorPosition(id, { x, y, z }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anchors'] });
      queryClient.invalidateQueries({ queryKey: ['anchor-system-status'] });
      setSelectedAnchor(null);
    },
  });

  const deleteAnchorMutation = useMutation({
    mutationFn: deleteAnchor,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anchors'] });
      queryClient.invalidateQueries({ queryKey: ['anchor-system-status'] });
    },
  });

  const heartbeatMutation = useMutation({
    mutationFn: ({ id, battery }: { id: number; battery?: number }) =>
      anchorHeartbeat(id, battery),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anchors'] });
    },
  });

  const resetCreateForm = () => {
    setNewAnchorId('');
    setNewAnchorName('');
    setNewAnchorX('');
    setNewAnchorY('');
    setNewAnchorZ('');
    setNewAnchorMode('TWR');
    setNewAnchorNotes('');
  };

  const handleCreateAnchor = () => {
    if (!newAnchorId || !newAnchorName || !newAnchorX || !newAnchorY || !newAnchorZ) {
      alert('Please fill in all required fields');
      return;
    }
    
    createAnchorMutation.mutate({
      anchor_id: parseInt(newAnchorId),
      name: newAnchorName,
      x: parseFloat(newAnchorX),
      y: parseFloat(newAnchorY),
      z: parseFloat(newAnchorZ),
      mode: newAnchorMode,
      notes: newAnchorNotes,
    });
  };

  const handleUpdatePosition = () => {
    if (!selectedAnchor) return;
    
    updatePositionMutation.mutate({
      id: selectedAnchor.anchor_id,
      x: parseFloat(editX),
      y: parseFloat(editY),
      z: parseFloat(editZ),
    });
  };

  const handleDeleteAnchor = (anchorId: number, anchorName: string) => {
    if (confirm(`Are you sure you want to delete anchor "${anchorName}"?`)) {
      deleteAnchorMutation.mutate(anchorId);
    }
  };

  const openPositionDialog = (anchor: Anchor) => {
    setSelectedAnchor(anchor);
    setEditX(String(anchor.x));
    setEditY(String(anchor.y));
    setEditZ(String(anchor.z));
  };

  // Filter anchors
  const filteredAnchors = anchors.filter((anchor: Anchor) => {
    const matchesSearch = 
      anchor.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      String(anchor.anchor_id).includes(searchTerm);
    const matchesStatus = selectedStatus === 'all' || anchor.status === selectedStatus;
    const matchesMode = selectedMode === 'all' || anchor.mode === selectedMode;
    return matchesSearch && matchesStatus && matchesMode;
  });

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'online':
        return <Wifi className="h-4 w-4 text-green-500" />;
      case 'offline':
        return <WifiOff className="h-4 w-4 text-red-500" />;
      case 'calibrating':
        return <Activity className="h-4 w-4 text-yellow-500" />;
      case 'error':
        return <AlertTriangle className="h-4 w-4 text-red-500" />;
      default:
        return <WifiOff className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'online':
        return <Badge variant="default" className="bg-green-500">Online</Badge>;
      case 'offline':
        return <Badge variant="destructive">Offline</Badge>;
      case 'calibrating':
        return <Badge variant="outline" className="text-yellow-600">Calibrating</Badge>;
      case 'error':
        return <Badge variant="destructive">Error</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  return (
    <DashboardLayout title="Loco Positioning Anchors">
      {/* System Status */}
      {!statusLoading && systemStatus && (
        <div className="grid gap-4 md:grid-cols-5 mb-6">
          <PageCard title="Total Anchors" description="Installed">
            <div className="text-3xl font-bold">{systemStatus.total_anchors}</div>
          </PageCard>
          <PageCard title="Online" description="Active">
            <div className="text-3xl font-bold text-green-600">{systemStatus.online_anchors}</div>
          </PageCard>
          <PageCard title="Offline" description="Disconnected">
            <div className="text-3xl font-bold text-red-600">{systemStatus.offline_anchors}</div>
          </PageCard>
          <PageCard title="Mode" description="Positioning">
            <div className="text-xl font-bold">{systemStatus.positioning_mode}</div>
          </PageCard>
          <PageCard title="System" description="Status">
            <div className={`text-xl font-bold ${systemStatus.system_ready ? 'text-green-600' : 'text-red-600'}`}>
              {systemStatus.system_ready ? 'Ready' : 'Not Ready'}
            </div>
          </PageCard>
        </div>
      )}

      {/* Coverage Area */}
      {systemStatus?.coverage_area && (
        <Alert className="mb-6">
          <MapPin className="h-4 w-4" />
          <AlertTitle>Coverage Area</AlertTitle>
          <AlertDescription>
            X: {systemStatus.coverage_area.x_min.toFixed(1)}m to {systemStatus.coverage_area.x_max.toFixed(1)}m | 
            Y: {systemStatus.coverage_area.y_min.toFixed(1)}m to {systemStatus.coverage_area.y_max.toFixed(1)}m | 
            Z: {systemStatus.coverage_area.z_min.toFixed(1)}m to {systemStatus.coverage_area.z_max.toFixed(1)}m
          </AlertDescription>
        </Alert>
      )}

      {/* Error Alert */}
      {anchorsError && (
        <Alert variant="destructive" className="mb-6">
          <AlertTitle>Error loading anchors</AlertTitle>
          <AlertDescription>Failed to fetch anchor data. Please try again.</AlertDescription>
        </Alert>
      )}

      {/* Filters and Actions */}
      <div className="flex flex-col md:flex-row gap-4 mb-6">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search anchors by name or ID..."
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
            <SelectItem value="online">Online</SelectItem>
            <SelectItem value="offline">Offline</SelectItem>
            <SelectItem value="calibrating">Calibrating</SelectItem>
            <SelectItem value="error">Error</SelectItem>
          </SelectContent>
        </Select>

        <Select value={selectedMode} onValueChange={setSelectedMode}>
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Filter by mode" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Modes</SelectItem>
            <SelectItem value="TWR">TWR</SelectItem>
            <SelectItem value="TDoA2">TDoA2</SelectItem>
            <SelectItem value="TDoA3">TDoA3</SelectItem>
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
              Add Anchor
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Register New Anchor</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="anchorId">Anchor ID (0-7)</Label>
                  <Input
                    id="anchorId"
                    type="number"
                    min="0"
                    max="7"
                    placeholder="0"
                    value={newAnchorId}
                    onChange={(e) => setNewAnchorId(e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="mode">Mode</Label>
                  <Select value={newAnchorMode} onValueChange={setNewAnchorMode}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="TWR">TWR</SelectItem>
                      <SelectItem value="TDoA2">TDoA2</SelectItem>
                      <SelectItem value="TDoA3">TDoA3</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <Label htmlFor="name">Anchor Name</Label>
                <Input
                  id="name"
                  placeholder="e.g., anchor-northwest"
                  value={newAnchorName}
                  onChange={(e) => setNewAnchorName(e.target.value)}
                />
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <Label htmlFor="x">X (meters)</Label>
                  <Input
                    id="x"
                    type="number"
                    step="0.01"
                    placeholder="0.00"
                    value={newAnchorX}
                    onChange={(e) => setNewAnchorX(e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="y">Y (meters)</Label>
                  <Input
                    id="y"
                    type="number"
                    step="0.01"
                    placeholder="0.00"
                    value={newAnchorY}
                    onChange={(e) => setNewAnchorY(e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="z">Z (meters)</Label>
                  <Input
                    id="z"
                    type="number"
                    step="0.01"
                    placeholder="0.00"
                    value={newAnchorZ}
                    onChange={(e) => setNewAnchorZ(e.target.value)}
                  />
                </div>
              </div>
              <div>
                <Label htmlFor="notes">Notes</Label>
                <Input
                  id="notes"
                  placeholder="Installation notes..."
                  value={newAnchorNotes}
                  onChange={(e) => setNewAnchorNotes(e.target.value)}
                />
              </div>
              <Button 
                onClick={handleCreateAnchor} 
                disabled={!newAnchorId || !newAnchorName || !newAnchorX || !newAnchorY || !newAnchorZ || createAnchorMutation.isPending}
                className="w-full"
              >
                {createAnchorMutation.isPending ? 'Registering...' : 'Register Anchor'}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Edit Position Dialog */}
      <Dialog open={!!selectedAnchor} onOpenChange={(open) => !open && setSelectedAnchor(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Update Anchor Position</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <p className="text-sm text-muted-foreground">
              Updating position for: <strong>{selectedAnchor?.name}</strong>
            </p>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <Label htmlFor="editX">X (meters)</Label>
                <Input
                  id="editX"
                  type="number"
                  step="0.01"
                  value={editX}
                  onChange={(e) => setEditX(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="editY">Y (meters)</Label>
                <Input
                  id="editY"
                  type="number"
                  step="0.01"
                  value={editY}
                  onChange={(e) => setEditY(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="editZ">Z (meters)</Label>
                <Input
                  id="editZ"
                  type="number"
                  step="0.01"
                  value={editZ}
                  onChange={(e) => setEditZ(e.target.value)}
                />
              </div>
            </div>
            <Button 
              onClick={handleUpdatePosition} 
              disabled={updatePositionMutation.isPending}
              className="w-full"
            >
              {updatePositionMutation.isPending ? 'Updating...' : 'Update Position'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Anchors Display */}
      {anchorsLoading ? (
        <div className="text-center py-12">
          <RefreshCw className="mx-auto h-8 w-8 animate-spin text-muted-foreground" />
          <p className="mt-2 text-muted-foreground">Loading anchors...</p>
        </div>
      ) : filteredAnchors.length === 0 ? (
        <div className="text-center py-12 border rounded-lg">
          <Radio className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">No anchors found</h3>
          <p className="text-muted-foreground">
            {searchTerm || selectedStatus !== 'all' || selectedMode !== 'all'
              ? 'Try adjusting your filters'
              : 'Get started by adding your first Loco Positioning anchor'}
          </p>
        </div>
      ) : viewMode === 'grid' ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredAnchors.map((anchor: Anchor) => (
            <AnchorCard 
              key={anchor.id} 
              anchor={anchor}
              onEditPosition={() => openPositionDialog(anchor)}
              onDelete={() => handleDeleteAnchor(anchor.anchor_id, anchor.name)}
              onHeartbeat={() => heartbeatMutation.mutate({ id: anchor.anchor_id })}
              isHeartbeating={heartbeatMutation.isPending}
            />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {filteredAnchors.map((anchor: Anchor) => (
            <AnchorRow 
              key={anchor.id} 
              anchor={anchor}
              onEditPosition={() => openPositionDialog(anchor)}
              onDelete={() => handleDeleteAnchor(anchor.anchor_id, anchor.name)}
              onHeartbeat={() => heartbeatMutation.mutate({ id: anchor.anchor_id })}
              isHeartbeating={heartbeatMutation.isPending}
            />
          ))}
        </div>
      )}
    </DashboardLayout>
  );
}

// Anchor Card Component
interface AnchorCardProps {
  anchor: Anchor;
  onEditPosition: () => void;
  onDelete: () => void;
  onHeartbeat: () => void;
  isHeartbeating: boolean;
}

function AnchorCard({ anchor, onEditPosition, onDelete, onHeartbeat, isHeartbeating }: AnchorCardProps) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'online':
        return <Wifi className="h-4 w-4 text-green-500" />;
      case 'offline':
        return <WifiOff className="h-4 w-4 text-red-500" />;
      case 'calibrating':
        return <Activity className="h-4 w-4 text-yellow-500" />;
      case 'error':
        return <AlertTriangle className="h-4 w-4 text-red-500" />;
      default:
        return <WifiOff className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'online':
        return <Badge variant="default" className="bg-green-500">Online</Badge>;
      case 'offline':
        return <Badge variant="destructive">Offline</Badge>;
      case 'calibrating':
        return <Badge variant="outline" className="text-yellow-600">Calibrating</Badge>;
      case 'error':
        return <Badge variant="destructive">Error</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  return (
    <Card className="transition-shadow hover:shadow-md">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {getStatusIcon(anchor.status)}
            <CardTitle className="text-lg">{anchor.name}</CardTitle>
          </div>
          <div className="text-sm text-muted-foreground">
            ID: {anchor.anchor_id}
          </div>
        </div>
        <div className="flex gap-2">
          {getStatusBadge(anchor.status)}
          <Badge variant="outline">{anchor.mode}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="text-sm">
          <span className="font-medium">Position: </span>
          <span className="text-muted-foreground">
            X:{anchor.x.toFixed(2)} Y:{anchor.y.toFixed(2)} Z:{anchor.z.toFixed(2)}m
          </span>
        </div>
        
        {anchor.battery_level !== null && (
          <div className="text-sm">
            <span className="font-medium">Battery: </span>
            <span className={anchor.battery_level < 20 ? 'text-red-500' : 'text-green-500'}>
              {anchor.battery_level}%
            </span>
          </div>
        )}

        {anchor.last_seen && (
          <div className="text-xs text-muted-foreground">
            Last seen: {new Date(anchor.last_seen).toLocaleString()}
          </div>
        )}

        {anchor.notes && (
          <p className="text-sm text-muted-foreground line-clamp-2">
            {anchor.notes}
          </p>
        )}

        <div className="flex gap-2 pt-2">
          <Button 
            variant="outline" 
            size="sm" 
            className="flex-1"
            onClick={onEditPosition}
          >
            <Edit className="mr-1 h-3 w-3" />
            Position
          </Button>
          <Button 
            variant="outline" 
            size="sm" 
            className="flex-1"
            onClick={onHeartbeat}
            disabled={isHeartbeating}
          >
            <Activity className="mr-1 h-3 w-3" />
            Ping
          </Button>
          <Button variant="ghost" size="sm" onClick={onDelete}>
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// Anchor Row Component
interface AnchorRowProps {
  anchor: Anchor;
  onEditPosition: () => void;
  onDelete: () => void;
  onHeartbeat: () => void;
  isHeartbeating: boolean;
}

function AnchorRow({ anchor, onEditPosition, onDelete, onHeartbeat, isHeartbeating }: AnchorRowProps) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'online':
        return <Wifi className="h-4 w-4 text-green-500" />;
      case 'offline':
        return <WifiOff className="h-4 w-4 text-red-500" />;
      case 'calibrating':
        return <Activity className="h-4 w-4 text-yellow-500" />;
      case 'error':
        return <AlertTriangle className="h-4 w-4 text-red-500" />;
      default:
        return <WifiOff className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'online':
        return <Badge variant="default" className="bg-green-500">Online</Badge>;
      case 'offline':
        return <Badge variant="destructive">Offline</Badge>;
      case 'calibrating':
        return <Badge variant="outline" className="text-yellow-600">Calibrating</Badge>;
      case 'error':
        return <Badge variant="destructive">Error</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  return (
    <div className="flex items-center justify-between p-4 border rounded-lg hover:bg-accent/50 transition-colors">
      <div className="flex items-center gap-4">
        {getStatusIcon(anchor.status)}
        <div>
          <div className="flex items-center gap-2">
            <span className="font-medium">{anchor.name}</span>
            <span className="text-sm text-muted-foreground">ID: {anchor.anchor_id}</span>
            {getStatusBadge(anchor.status)}
            <Badge variant="outline">{anchor.mode}</Badge>
          </div>
          <div className="flex items-center gap-4 text-sm text-muted-foreground mt-1">
            <span>Position: X:{anchor.x.toFixed(2)} Y:{anchor.y.toFixed(2)} Z:{anchor.z.toFixed(2)}m</span>
            {anchor.battery_level !== null && (
              <span className={anchor.battery_level < 20 ? 'text-red-500' : ''}>
                Battery: {anchor.battery_level}%
              </span>
            )}
          </div>
        </div>
      </div>
      
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={onEditPosition}>
          <Edit className="mr-1 h-3 w-3" />
          Position
        </Button>
        <Button 
          variant="outline" 
          size="sm"
          onClick={onHeartbeat}
          disabled={isHeartbeating}
        >
          <Activity className="mr-1 h-3 w-3" />
          Ping
        </Button>
        <Button variant="ghost" size="sm" onClick={onDelete}>
          <Trash2 className="h-4 w-4 text-destructive" />
        </Button>
      </div>
    </div>
  );
}
