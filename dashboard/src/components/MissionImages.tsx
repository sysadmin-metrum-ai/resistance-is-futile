'use client';

import { useState, useEffect } from 'react';
import { X, Image as ImageIcon, Loader2, AlertCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { getMissionImages, getImageUrl } from '@/lib/api';
import type { ImageListResponse } from '@/types';

interface MissionImagesProps {
  missionId: string;
  onClose: () => void;
}

/**
 * MissionImages - Displays images captured during a mission.
 */
export function MissionImages({ missionId, onClose }: MissionImagesProps) {
  const [images, setImages] = useState<ImageListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch images on mount
  useEffect(() => {
    async function fetchImages() {
      try {
        setLoading(true);
        const data = await getMissionImages(missionId);
        setImages(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load images');
      } finally {
        setLoading(false);
      }
    }
    fetchImages();
  }, [missionId]);

  return (
    <Card className="w-full">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Mission Images</CardTitle>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        <p className="text-sm text-muted-foreground">
          Mission ID: {missionId}
        </p>
      </CardHeader>
      <CardContent>
        {loading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            <span className="ml-2 text-muted-foreground">Loading images...</span>
          </div>
        )}

        {error && (
          <div className="flex items-center justify-center py-8 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <span className="ml-2">{error}</span>
          </div>
        )}

        {!loading && !error && images && (
          <>
            {images.count === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                <ImageIcon className="h-12 w-12 mb-2" />
                <p>No images captured for this mission</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {images.images.map((imageId, index) => (
                  <div
                    key={imageId}
                    className="relative aspect-square rounded-md overflow-hidden border"
                  >
                    <img
                      src={getImageUrl(imageId)}
                      alt={`Mission image ${index + 1}`}
                      className="object-cover w-full h-full"
                      onError={(e) => {
                        // Fallback to icon on error
                        const target = e.target as HTMLImageElement;
                        target.style.display = 'none';
                        const parent = target.parentElement;
                        if (parent) {
                          const icon = document.createElement('div');
                          icon.className = 'flex items-center justify-center h-full bg-muted';
                          icon.innerHTML = '<svg class="h-8 w-8 text-muted-foreground" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>';
                          parent.appendChild(icon);
                        }
                      }}
                    />
                  </div>
                ))}
              </div>
            )}
            <p className="text-sm text-muted-foreground mt-2">
              {images.count} image(s) captured
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
