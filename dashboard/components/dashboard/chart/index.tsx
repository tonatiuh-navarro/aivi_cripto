"use client";

import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { Bullet } from "@/components/ui/bullet";
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import type { ChartPoint } from "@/types/dashboard";

const chartConfig = {
  income: {
    label: "Ingresos",
    color: "var(--chart-1)",
  },
  expenses: {
    label: "Gastos",
    color: "var(--chart-2)",
  },
  balance: {
    label: "Balance",
    color: "var(--chart-3)",
  },
} satisfies ChartConfig;

type Props = {
  data: ChartPoint[];
};

export default function DashboardChart({ data }: Props) {
  if (!data || data.length === 0) {
    return (
      <div className="bg-accent rounded-lg p-6 text-sm text-muted-foreground">
        Sin datos para el rango seleccionado.
      </div>
    );
  }

  const formatYAxisValue = (value: number) => {
    if (value === 0) {
      return "";
    }
    if (value >= 1000000) {
      return `${(value / 1000000).toFixed(0)}M`;
    }
    if (value >= 1000) {
      return `${(value / 1000).toFixed(0)}K`;
    }
    return value.toString();
  };

  return (
    <div className="bg-accent rounded-lg p-3">
      <div className="flex items-center gap-6 mb-4">
        {Object.entries(chartConfig).map(([key, value]) => (
          <ChartLegend key={key} label={value.label} color={value.color} />
        ))}
      </div>
      <ChartContainer className="md:aspect-[3/1] w-full" config={chartConfig}>
        <AreaChart
          accessibilityLayer
          data={data}
          margin={{
            left: -12,
            right: 12,
            top: 12,
            bottom: 12,
          }}
        >
          <defs>
            <linearGradient id="fillIncome" x1="0" y1="0" x2="0" y2="1">
              <stop
                offset="5%"
                stopColor="var(--color-income)"
                stopOpacity={0.8}
              />
              <stop
                offset="95%"
                stopColor="var(--color-income)"
                stopOpacity={0.1}
              />
            </linearGradient>
            <linearGradient id="fillExpenses" x1="0" y1="0" x2="0" y2="1">
              <stop
                offset="5%"
                stopColor="var(--color-expenses)"
                stopOpacity={0.8}
              />
              <stop
                offset="95%"
                stopColor="var(--color-expenses)"
                stopOpacity={0.1}
              />
            </linearGradient>
            <linearGradient id="fillBalance" x1="0" y1="0" x2="0" y2="1">
              <stop
                offset="5%"
                stopColor="var(--color-balance)"
                stopOpacity={0.8}
              />
              <stop
                offset="95%"
                stopColor="var(--color-balance)"
                stopOpacity={0.1}
              />
            </linearGradient>
          </defs>
          <CartesianGrid
            horizontal={false}
            strokeDasharray="8 8"
            strokeWidth={2}
            stroke="var(--muted-foreground)"
            opacity={0.3}
          />
          <XAxis
            dataKey="date"
            tickLine={false}
            tickMargin={12}
            strokeWidth={1.5}
            className="uppercase text-sm fill-muted-foreground"
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            tickMargin={0}
            tickCount={6}
            className="text-sm fill-muted-foreground"
            tickFormatter={formatYAxisValue}
            domain={[0, "dataMax"]}
          />
          <ChartTooltip
            cursor={false}
            content={
              <ChartTooltipContent
                indicator="dot"
                className="min-w-[200px] px-4 py-3"
              />
            }
          />
          <Area
            dataKey="income"
            type="linear"
            fill="url(#fillIncome)"
            fillOpacity={0.4}
            stroke="var(--color-income)"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
          <Area
            dataKey="expenses"
            type="linear"
            fill="url(#fillExpenses)"
            fillOpacity={0.4}
            stroke="var(--color-expenses)"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
          <Area
            dataKey="balance"
            type="linear"
            fill="url(#fillBalance)"
            fillOpacity={0.4}
            stroke="var(--color-balance)"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        </AreaChart>
      </ChartContainer>
    </div>
  );
}

export const ChartLegend = ({
  label,
  color,
}: {
  label: string;
  color: string;
}) => {
  return (
    <div className="flex items-center gap-2 uppercase">
      <Bullet style={{ backgroundColor: color }} className="rotate-45" />
      <span className="text-sm font-medium text-muted-foreground">
        {label}
      </span>
    </div>
  );
};
