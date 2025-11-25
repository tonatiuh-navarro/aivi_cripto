"use client";

import DashboardStat from "@/components/dashboard/stat";
import DashboardChart from "@/components/dashboard/chart";
import GearIcon from "@/components/icons/gear";
import ProcessorIcon from "@/components/icons/proccesor";
import BoomIcon from "@/components/icons/boom";
import type { ChartPoint, DashboardStatMetric } from "@/types/dashboard";

const iconMap = {
  gear: GearIcon,
  proccesor: ProcessorIcon,
  boom: BoomIcon,
};

type Props = {
  stats: DashboardStatMetric[];
  chart: ChartPoint[];
};

export function WalletInfoPanel({ stats, chart }: Props) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {stats.map((stat, index) => {
          const Icon = iconMap[stat.icon];
          return (
            <DashboardStat
              key={index}
              label={stat.label}
              value={stat.value}
              description={stat.description}
              icon={Icon}
              tag={stat.tag}
              intent={stat.intent}
              direction={stat.direction}
            />
          );
        })}
      </div>
      <DashboardChart data={chart} />
    </div>
  );
}
