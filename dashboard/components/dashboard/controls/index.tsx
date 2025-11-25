"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { ScenarioOption, SummaryFreq } from "@/types/dashboard";

type ControlsState = {
  base: string;
  variant: string;
  startDate: string;
  endDate: string;
  freq: SummaryFreq;
};

type Props = {
  scenarios: ScenarioOption[];
  controls: ControlsState;
  onChange: (partial: Partial<ControlsState>) => void;
};

const freqOptions: { label: string; value: SummaryFreq }[] = [
  { label: "Diario", value: "daily" },
  { label: "Semanal", value: "weekly" },
  { label: "Mensual", value: "monthly" },
];

export function DashboardControls({
  scenarios,
  controls,
  onChange,
}: Props) {
  const swap = () => {
    onChange({
      base: controls.variant,
      variant: controls.base,
    });
  };

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <div className="grid gap-2">
        <span className="text-xs uppercase text-muted-foreground">
          Escenario base
        </span>
        <Select
          value={controls.base}
          onValueChange={(value) => onChange({ base: value })}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {scenarios.map((scenario) => (
              <SelectItem key={scenario.name} value={scenario.name}>
                {scenario.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="grid gap-2">
        <span className="text-xs uppercase text-muted-foreground">
          Escenario comparado
        </span>
        <Select
          value={controls.variant}
          onValueChange={(value) => onChange({ variant: value })}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {scenarios.map((scenario) => (
              <SelectItem key={scenario.name} value={scenario.name}>
                {scenario.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="grid gap-2">
        <span className="text-xs uppercase text-muted-foreground">
          Inicio
        </span>
        <Input
          type="date"
          value={controls.startDate}
          onChange={(e) => onChange({ startDate: e.target.value })}
        />
      </div>
      <div className="grid gap-2">
        <span className="text-xs uppercase text-muted-foreground">
          Fin
        </span>
        <Input
          type="date"
          value={controls.endDate}
          onChange={(e) => onChange({ endDate: e.target.value })}
        />
      </div>
      <div className="grid gap-2 md:col-span-2">
        <span className="text-xs uppercase text-muted-foreground">
          Frecuencia
        </span>
        <Select
          value={controls.freq}
          onValueChange={(value: SummaryFreq) => onChange({ freq: value })}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {freqOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="md:col-span-2 flex items-end">
        <Button variant="outline" onClick={swap}>
          Intercambiar escenarios
        </Button>
      </div>
    </div>
  );
}
