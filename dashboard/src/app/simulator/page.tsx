'use client';

import { BoothSwarmSimulation } from '@/components/BoothSwarmSimulation';
import { DashboardLayout, PageCard } from '@/components/DashboardLayout';

export default function SimulatorPage() {
  return (
    <DashboardLayout title="Demo Simulator">
      <PageCard
        title="Booth Simulator"
        description="10ft x 10ft x 10ft planned-position view. In-flight pose telemetry is not used."
      >
        <div className="h-[620px]">
          <BoothSwarmSimulation />
        </div>
      </PageCard>
    </DashboardLayout>
  );
}
