"use client";

import { useState } from "react";
import DashboardPageLayout from "@/components/dashboard/layout";
import BracketsIcon from "@/components/icons/brackets";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

type HParamRange = {
  min?: string;
  max?: string;
  step?: string;
  list?: string;
};

type StageConfig = {
  name: string;
  params: Record<string, HParamRange>;
};

const ENTRY_OPTIONS: StageConfig[] = [{ name: "ma_signal", params: { fast: {}, slow: {} } }];
const TP_OPTIONS: StageConfig[] = [{ name: "atr_target", params: { multiplier: {} } }];
const SL_OPTIONS: StageConfig[] = [{ name: "atr_stop", params: { multiplier: {} } }];

export default function OptimizationsPage() {
  const [entry, setEntry] = useState("ma_signal");
  const [tp, setTp] = useState("atr_target");
  const [sl, setSl] = useState("atr_stop");
  const [hparams, setHparams] = useState<Record<string, HParamRange>>({});
  const [objective, setObjective] = useState("total_return");
  const [sampler, setSampler] = useState("grid");
  const [maxIters, setMaxIters] = useState("20");
  const [maxTime, setMaxTime] = useState("60");
  const [logs, setLogs] = useState<string[]>([]);
  const [bestMetrics, setBestMetrics] = useState<Record<string, number>>({});
  const [bestParams, setBestParams] = useState<Record<string, any>>({});
  const [trials, setTrials] = useState<
    { trial_id: number; params: Record<string, any>; metrics: Record<string, any> }[]
  >([]);
  const [running, setRunning] = useState(false);

  const currentStageParams = (kind: "entry" | "tp" | "sl") => {
    const source = kind === "entry" ? ENTRY_OPTIONS : kind === "tp" ? TP_OPTIONS : SL_OPTIONS;
    const selected = source.find((opt) => opt.name === (kind === "entry" ? entry : kind === "tp" ? tp : sl));
    return selected?.params || {};
  };

  const handleRangeChange = (kind: "entry" | "tp" | "sl", param: string, field: keyof HParamRange, value: string) => {
    const key = `${kind}_${param}`;
    setHparams((prev) => ({
      ...prev,
      [key]: {
        ...(prev[key] || {}),
        [field]: value,
      },
    }));
  };

  const buildSearchSpace = () => {
    const out: Record<string, any> = {};
    const stages: [("entry" | "tp" | "sl"), string][] = [
      ["entry", entry],
      ["tp", tp],
      ["sl", sl],
    ];
    for (const [kind, name] of stages) {
      const params = currentStageParams(kind);
      for (const p of Object.keys(params)) {
        const key = `${kind}_${p}`;
        const cfg = hparams[key];
        if (cfg?.list) {
          const values = cfg.list
            .split(",")
            .map((v) => v.trim())
            .filter(Boolean)
            .map(Number)
            .filter((v) => !Number.isNaN(v));
          if (values.length) {
            out[`${kind}.${p}`] = values;
          }
        } else if (cfg?.min && cfg?.max && cfg?.step) {
          out[`${kind}.${p}`] = {
            min: Number(cfg.min),
            max: Number(cfg.max),
            step: Number(cfg.step),
          };
        }
      }
    }
    return out;
  };

  const runOptimize = async () => {
    setRunning(true);
    setLogs([]);
    setBestMetrics({});
    setBestParams({});
    setTrials([]);
    const baseUrl = process.env.NEXT_PUBLIC_WALLET_API || "";
    const searchSpace = buildSearchSpace();
    const payload = {
      stage_cfgs: [
        { kind: "entry", name: entry, params: {} },
        { kind: "target_price", name: tp, params: {} },
        { kind: "stop_loss", name: sl, params: {} },
      ],
      search_space: searchSpace,
      sampler,
      max_iters: maxIters ? Number(maxIters) : null,
      max_time: maxTime ? Number(maxTime) : null,
      objective,
    };
    try {
      setLogs((prev) => [...prev, "Lanzando optimización..."]);
      const resp = await fetch(`${baseUrl}/optimize_strategy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(`HTTP ${resp.status}: ${txt}`);
      }
      const data = await resp.json();
      setLogs((prev) => [...prev, "Optimización finalizada"]);
      setBestParams(data.best_params || {});
      setBestMetrics(data.best_metrics || {});
      setTrials(data.trials || []);
    } catch (err: any) {
      setLogs((prev) => [...prev, `Error: ${err?.message || err}`]);
    }
    setRunning(false);
  };

  const exportBest = () => {
    const payload = { best_params: bestParams, best_metrics: bestMetrics };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "best_strategy.json";
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <DashboardPageLayout
      header={{
        title: "Optimizations",
        description: "Optimiza estrategias de trading",
        icon: BracketsIcon,
      }}
    >
      <div className="space-y-6">
        <Card className="p-4 space-y-4">
          <div className="text-lg font-semibold">Configurar optimización</div>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <Label>Entry</Label>
              <Select value={entry} onValueChange={setEntry}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ENTRY_OPTIONS.map((opt) => (
                    <SelectItem key={opt.name} value={opt.name}>
                      {opt.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {Object.keys(currentStageParams("entry")).map((p) => (
                <div key={p} className="space-y-1">
                  <Label>{p} (min/max/step o lista)</Label>
                  <div className="grid grid-cols-3 gap-2">
                    <Input placeholder="min" onChange={(e) => handleRangeChange("entry", p, "min", e.target.value)} />
                    <Input placeholder="max" onChange={(e) => handleRangeChange("entry", p, "max", e.target.value)} />
                    <Input
                      placeholder="step"
                      onChange={(e) => handleRangeChange("entry", p, "step", e.target.value)}
                    />
                  </div>
                  <Textarea
                    placeholder="v1, v2, v3"
                    onChange={(e) => handleRangeChange("entry", p, "list", e.target.value)}
                  />
                </div>
              ))}
            </div>
            <div className="space-y-2">
              <Label>Target Price</Label>
              <Select value={tp} onValueChange={setTp}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TP_OPTIONS.map((opt) => (
                    <SelectItem key={opt.name} value={opt.name}>
                      {opt.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {Object.keys(currentStageParams("tp")).map((p) => (
                <div key={p} className="space-y-1">
                  <Label>{p} (min/max/step o lista)</Label>
                  <div className="grid grid-cols-3 gap-2">
                    <Input placeholder="min" onChange={(e) => handleRangeChange("tp", p, "min", e.target.value)} />
                    <Input placeholder="max" onChange={(e) => handleRangeChange("tp", p, "max", e.target.value)} />
                    <Input
                      placeholder="step"
                      onChange={(e) => handleRangeChange("tp", p, "step", e.target.value)}
                    />
                  </div>
                  <Textarea
                    placeholder="v1, v2, v3"
                    onChange={(e) => handleRangeChange("tp", p, "list", e.target.value)}
                  />
                </div>
              ))}
            </div>
            <div className="space-y-2">
              <Label>Stop Loss</Label>
              <Select value={sl} onValueChange={setSl}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SL_OPTIONS.map((opt) => (
                    <SelectItem key={opt.name} value={opt.name}>
                      {opt.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {Object.keys(currentStageParams("sl")).map((p) => (
                <div key={p} className="space-y-1">
                  <Label>{p} (min/max/step o lista)</Label>
                  <div className="grid grid-cols-3 gap-2">
                    <Input placeholder="min" onChange={(e) => handleRangeChange("sl", p, "min", e.target.value)} />
                    <Input placeholder="max" onChange={(e) => handleRangeChange("sl", p, "max", e.target.value)} />
                    <Input
                      placeholder="step"
                      onChange={(e) => handleRangeChange("sl", p, "step", e.target.value)}
                    />
                  </div>
                  <Textarea
                    placeholder="v1, v2, v3"
                    onChange={(e) => handleRangeChange("sl", p, "list", e.target.value)}
                  />
                </div>
              ))}
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <Label>Objective</Label>
              <Select value={objective} onValueChange={setObjective}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="total_return">total_return</SelectItem>
                  <SelectItem value="calmar">calmar</SelectItem>
                  <SelectItem value="profit_factor">profit_factor</SelectItem>
                  <SelectItem value="sharpe">sharpe</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Sampler</Label>
              <Select value={sampler} onValueChange={setSampler}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="grid">Grid</SelectItem>
                  <SelectItem value="random">Random</SelectItem>
                  <SelectItem value="bayes">Bayes</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>max_iters</Label>
              <Input type="number" value={maxIters} onChange={(e) => setMaxIters(e.target.value)} />
              <Label>max_time (s)</Label>
              <Input type="number" value={maxTime} onChange={(e) => setMaxTime(e.target.value)} />
            </div>
          </div>
          <div className="flex items-center gap-4">
            <Button onClick={runOptimize} disabled={running}>
              {running ? "Optimizing..." : "Run Optimization"}
            </Button>
            <Button onClick={exportBest} disabled={!bestMetrics || !bestParams || Object.keys(bestParams).length === 0}>
              Export best
            </Button>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Card className="p-3 space-y-2">
              <div className="font-semibold">Logs</div>
              <div className="h-40 overflow-auto text-xs bg-muted/30 p-2 rounded">
                {logs.map((l, i) => (
                  <div key={i}>{l}</div>
                ))}
              </div>
            </Card>
            <Card className="p-3 space-y-2">
              <div className="font-semibold">Best Result</div>
              <div className="text-sm">Objective: {objective}</div>
              <div className="text-sm">Score: {bestMetrics?.[objective] ?? "N/A"}</div>
              <div className="text-xs break-words">Params: {JSON.stringify(bestParams)}</div>
              <div className="text-xs break-words">Metrics: {JSON.stringify(bestMetrics)}</div>
            </Card>
          </div>
          <Card className="p-3 space-y-2">
            <div className="font-semibold">Trials (top 10)</div>
            <div className="text-xs bg-muted/30 p-2 rounded h-48 overflow-auto">
              {trials.slice(0, 10).map((t) => (
                <div key={t.trial_id} className="mb-2 border-b pb-1">
                  <div className="flex items-center justify-between">
                    <span>trial {t.trial_id}</span>
                    <span className={cn("font-semibold")}>{t.metrics?.[objective] ?? "N/A"}</span>
                  </div>
                  <div>params: {JSON.stringify(t.params)}</div>
                  <div>metrics: {JSON.stringify(t.metrics)}</div>
                </div>
              ))}
            </div>
          </Card>
        </Card>
      </div>
    </DashboardPageLayout>
  );
}
