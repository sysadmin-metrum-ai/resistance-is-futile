'use client';

import { ReactNode } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface DashboardLayoutProps {
  children: ReactNode;
  title?: string;
}

/**
 * Dashboard layout with header, navigation, and main content area.
 * Supports customizable logo via public/logos/logo.png or public/logos/logo.svg
 */
export function DashboardLayout({ children, title = 'Drone Swarm Control' }: DashboardLayoutProps) {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <div className="flex items-center gap-4">
            {/* Logo - customizable via public/logos/ */}
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary">
              <span className="text-xl font-bold text-primary-foreground">DS</span>
            </div>
            <h1 className="text-xl font-semibold">{title}</h1>
          </div>

          {/* Navigation */}
          <nav className="flex items-center gap-2">
            <Button variant="ghost" asChild>
              <Link href="/">Dashboard</Link>
            </Button>
            <Button variant="ghost" asChild>
              <Link href="/drones">Drones</Link>
            </Button>
            <Button variant="ghost" asChild>
              <Link href="/missions">Missions</Link>
            </Button>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-6">
        {children}
      </main>

      {/* Footer */}
      <footer className="border-t bg-card">
        <div className="container mx-auto px-4 py-4">
          <p className="text-sm text-muted-foreground text-center">
            Drone Swarm Control Panel
          </p>
        </div>
      </footer>
    </div>
  );
}

/**
 * Page wrapper with card styling.
 */
interface PageCardProps {
  title: string;
  description?: string;
  children: ReactNode;
}

export function PageCard({ title, description, children }: PageCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && (
          <p className="text-sm text-muted-foreground">{description}</p>
        )}
      </CardHeader>
      <CardContent>
        {children}
      </CardContent>
    </Card>
  );
}
