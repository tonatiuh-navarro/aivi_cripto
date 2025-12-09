"use client";

import { useEffect, useMemo, useState } from "react";
import DashboardPageLayout from "@/components/dashboard/layout";
import BracketsIcon from "@/components/icons/brackets";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import dynamic from "next/dynamic";

type HParamValue = string;

type StageChoice = {
  name: string;
  params: Record<string, HParamValue>;
};

const ENTRY = [{ name: "ma_signal", params: { fast: "", slow: "" } }];
const TP = [{ name: "atr_target", params: { multiplier: "" } }];
const SL = [{ name: "atr_stop", params: { multiplier: "" } }];

type EvalResult = {
  dataset: string;
  metrics?: Record<string, any>;
  data?: Record<string, any>[];
};

type MarketDataInfo = {
  ticker: string;
  freq: string;
  path: string;
  min_time?: string | null;
  max_time?: string | null;
  rows: number;
};

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

export default function EvaluateStrategyPage() {
  const [entry, setEntry] = useState("ma_signal");
  const [tp, setTp] = useState("atr_target");
  const [sl, setSl] = useState("atr_stop");
  const [params, setParams] = useState<Record<string, HParamValue>>({});
  const [results, setResults] = useState<EvalResult[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [objective, setObjective] = useState("total_return");
  const [running, setRunning] = useState(false);
  const [xRange, setXRange] = useState<[number, number] | null>(null);
  const [datasetFilter, setDatasetFilter] = useState<string[]>(["pre_out_of_time", "train", "test"]);
  const [marketData, setMarketData] = useState<MarketDataInfo[]>([]);
  const [selectedTicker, setSelectedTicker] = useState<string>("");
  const [selectedFreq, setSelectedFreq] = useState<string>("");
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");
  const [showPlot, setShowPlot] = useState(false);

  const currentParams = (kind: "entry" | "tp" | "sl") => {
    const source = kind === "entry" ? ENTRY : kind === "tp" ? TP : SL;
    const selected = source.find((s) => s.name === (kind === "entry" ? entry : kind === "tp" ? tp : sl));
    return selected?.params || {};
  };

  const handleParamChange = (kind: "entry" | "tp" | "sl", p: string, val: string) => {
    setParams((prev) => ({
      ...prev,
      [`${kind}_${p}`]: val,
    }));
  };

  const fetchMarketData = async () => {
    const baseUrl = process.env.NEXT_PUBLIC_WALLET_API || "";
    try {
      const resp = await fetch(`${baseUrl}/market_data/available`);
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const json = await resp.json();
      const items = (json?.items || []) as MarketDataInfo[];
      setMarketData(items);
      if (items.length && !selectedTicker) {
        setSelectedTicker(items[0].ticker);
        const freqs = items.filter((i) => i.ticker === items[0].ticker);
        if (freqs.length) {
          setSelectedFreq(freqs[0].freq);
        }
      }
    } catch (err: any) {
      setLogs((prev) => [...prev, `Error al cargar datos disponibles: ${err?.message || err}`]);
    }
  };

  const loadExport = (data: any) => {
    const best = data?.best_params || {};
    const merged: Record<string, string> = {};
    ["entry", "target_price", "stop_loss"].forEach((k) => {
      const vals = best[k] || {};
      Object.keys(vals).forEach((p) => {
        merged[`${k === "target_price" ? "tp" : k === "stop_loss" ? "sl" : "entry"}_${p}`] = String(vals[p]);
      });
    });
    setParams(merged);
  };

  const handleFile = async (file?: File | null) => {
    if (!file) return;
    try {
      const txt = await file.text();
      const parsed = JSON.parse(txt);
      loadExport(parsed);
      setLogs((prev) => [...prev, "Solución cargada"]);
    } catch {
      setLogs((prev) => [...prev, "Archivo inválido"]);
    }
  };

  const buildStageCfgs = () => {
    const cfgs = [
      { kind: "entry", name: entry, params: {} as Record<string, any> },
      { kind: "target_price", name: tp, params: {} as Record<string, any> },
      { kind: "stop_loss", name: sl, params: {} as Record<string, any> },
    ];
    cfgs.forEach((c) => {
      const prefix = c.kind === "entry" ? "entry" : c.kind === "target_price" ? "tp" : "sl";
      Object.keys(currentParams(prefix as "entry" | "tp" | "sl")).forEach((p) => {
        const key = `${prefix}_${p}`;
        if (params[key]) {
          c.params[p] = Number(params[key]);
        }
      });
    });
    return cfgs;
  };

  const runEvaluate = async () => {
    if (!selectedTicker || !selectedFreq) {
      setLogs((prev) => [...prev, "Selecciona ticker y frecuencia"]);
      return;
    }
    setRunning(true);
    setLogs([]);
    setResults([]);
    const baseUrl = process.env.NEXT_PUBLIC_WALLET_API || "";
    const payload = {
      stage_cfgs: buildStageCfgs(),
      include_data: true,
      ticker: selectedTicker || "BTCUSDT",
      freq: selectedFreq || "1h",
      start: startDate || undefined,
      end: endDate || undefined,
    };
    try {
      setLogs((prev) => [...prev, "Ejecutando evaluación..."]);
      const resp = await fetch(`${baseUrl}/evaluate_strategy_run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(`HTTP ${resp.status}: ${txt}`);
      }
      const data = await resp.json();
      setResults(data.results || []);
      setLogs((prev) => [...prev, "Evaluación finalizada"]);
    } catch (err: any) {
      setLogs((prev) => [...prev, `Error: ${err?.message || err}`]);
    }
    setRunning(false);
  };

  const freqsForTicker = useMemo(() => {
    return marketData.filter((m) => m.ticker === selectedTicker);
  }, [marketData, selectedTicker]);

  const selectedMeta = useMemo(() => {
    return marketData.find((m) => m.ticker === selectedTicker && m.freq === selectedFreq);
  }, [marketData, selectedTicker, selectedFreq]);

  useEffect(() => {
    fetchMarketData();
  }, []);

  useEffect(() => {
    setShowPlot(false);
    setXRange(null);
  }, [results]);

  const combinedData = () => {
    const rows: any[] = [];
    results.forEach((r) => {
      (r.data || []).forEach((row) => {
        rows.push({
          ...row,
          data_set: r.dataset,
        });
      });
    });
    return rows;
  };

  const chartData = combinedData().map((row) => ({
    time: row.open_time,
    timeISO: row.open_time ? new Date(row.open_time).toISOString() : row.open_time,
    timeMs: row.open_time ? new Date(row.open_time).valueOf() : undefined,
    open: row.open,
    high: row.high,
    low: row.low,
    close: row.close,
    ma_fast: row.ma_fast,
    ma_slow: row.ma_slow,
    trade: row.trade_event ? row.entry_price ?? row.close : null,
    signal: row.signal,
    tp_price: row.tp_price,
    sl_price: row.sl_price,
    exit_price: row.exit_price,
    win: row.trade_label === "win" ? row.exit_price ?? row.tp_price ?? row.close : null,
    loss: row.trade_label === "loss" ? row.exit_price ?? row.sl_price ?? row.close : null,
    data_set: row.data_set,
  }));

  const enrichedChartData = useMemo(() => {
    let lastEntryPrice: number | null = null;
    let lastSignal: number | null = null;
    return chartData.map((d) => {
      if (d.trade !== null && typeof d.trade === "number") {
        lastEntryPrice = d.trade;
        lastSignal = d.signal ?? 1;
      }
      const exitBasis = d.exit_price ?? d.close;
      const pct_change =
        lastEntryPrice !== null && lastSignal !== null
          ? (exitBasis / lastEntryPrice - 1) * (lastSignal || 1)
          : null;
      return {
        ...d,
        entry_price: lastEntryPrice,
        pct_change,
      };
    });
  }, [chartData]);

  const plotData = useMemo(() => {
    if (!enrichedChartData.length) return [];
    const data = xRange
      ? enrichedChartData.filter(
          (d) => d.timeMs !== undefined && d.timeMs >= xRange[0] && d.timeMs <= xRange[1]
        )
      : enrichedChartData;
    const xs = data.map((d) => d.timeISO ?? d.time);
    const times = enrichedChartData.map((d) => d.timeMs ?? 0);
    const deltas: number[] = [];
    for (let i = 1; i < times.length; i++) {
      const delta = times[i] - times[i - 1];
      if (delta > 0) deltas.push(delta);
    }
    const defaultDelta = deltas.length ? deltas.sort((a, b) => a - b)[Math.floor(deltas.length / 2)] : 3600000;
    const span = defaultDelta * 0.1;
    const tpX: number[] = [];
    const tpY: number[] = [];
    const slX: number[] = [];
    const slY: number[] = [];
    const tpPoints: { x: string; y: number }[] = [];
    const slPoints: { x: string; y: number }[] = [];
    enrichedChartData.forEach((d) => {
      if (d.tp_price !== null && d.tp_price !== undefined && d.timeMs !== undefined) {
        tpX.push(
          new Date(d.timeMs - span).toISOString(),
          new Date(d.timeMs + span).toISOString(),
          null as any
        );
        tpY.push(d.tp_price, d.tp_price, null as any);
        tpPoints.push({ x: new Date(d.timeMs).toISOString(), y: d.tp_price });
      }
      if (d.sl_price !== null && d.sl_price !== undefined && d.timeMs !== undefined) {
        slX.push(
          new Date(d.timeMs - span).toISOString(),
          new Date(d.timeMs + span).toISOString(),
          null as any
        );
        slY.push(d.sl_price, d.sl_price, null as any);
        slPoints.push({ x: new Date(d.timeMs).toISOString(), y: d.sl_price });
      }
    });
    const candle = {
      type: "candlestick" as const,
      x: xs,
      open: data.map((d) => d.open ?? d.close),
      high: data.map((d) => d.high ?? d.close),
      low: data.map((d) => d.low ?? d.close),
      close: data.map((d) => d.close),
      name: "OHLC",
      increasing: { line: { color: "#26de81" } },
      decreasing: { line: { color: "#ff3838" } },
      hovertemplate:
        "<b>%{x|%Y-%m-%d %H:%M}</b><br>O: %{open:$,.2f}<br>H: %{high:$,.2f}<br>L: %{low:$,.2f}<br>C: %{close:$,.2f}<extra></extra>",
    };
    const maFast = {
      type: "scatter" as const,
      mode: "lines",
      x: xs,
      y: data.map((d) => d.ma_fast),
      name: "MA fast",
      line: { color: "#00E396", width: 1.5 },
      hovertemplate: "%{x|%Y-%m-%d %H:%M}<br>$%{y:,.4f}<extra></extra>",
    };
    const maSlow = {
      type: "scatter" as const,
      mode: "lines",
      x: xs,
      y: data.map((d) => d.ma_slow),
      name: "MA slow",
      line: { color: "#FEB019", width: 1.5 },
      hovertemplate: "%{x|%Y-%m-%d %H:%M}<br>$%{y:,.4f}<extra></extra>",
    };
    const entries = data.filter((d) => d.trade !== null);
    const wins = data.filter((d) => d.win !== null);
    const losses = data.filter((d) => d.loss !== null);
    const entryTrace = {
      type: "scatter" as const,
      mode: "markers",
      x: entries.map((d) => d.timeISO ?? d.time),
      y: entries.map((d) => d.trade),
      name: "Entries",
      marker: { color: "#8884d8", size: 7, symbol: "diamond" },
      hovertemplate: "%{x|%Y-%m-%d %H:%M}<br>Entry: $%{y:,.4f}<extra></extra>",
    };
    const winTrace = {
      type: "scatter" as const,
      mode: "markers",
      x: wins.map((d) => d.timeISO ?? d.time),
      y: wins.map((d) => d.win ?? d.exit_price ?? d.tp_price),
      name: "Wins",
      marker: { color: "#26de81", size: 8, symbol: "triangle-up" },
      text: wins.map((d) =>
        d.pct_change !== null && d.pct_change !== undefined
          ? `${(d.pct_change * 100).toFixed(2)}%`
          : ""
      ),
      hovertemplate:
        "%{x|%Y-%m-%d %H:%M}<br>$%{y:,.4f}<br>%{text}<extra></extra>",
    };
    const lossTrace = {
      type: "scatter" as const,
      mode: "markers",
      x: losses.map((d) => d.timeISO ?? d.time),
      y: losses.map((d) => d.loss ?? d.exit_price ?? d.sl_price),
      name: "Losses",
      marker: { color: "#ff3838", size: 8, symbol: "triangle-down" },
      text: losses.map((d) =>
        d.pct_change !== null && d.pct_change !== undefined
          ? `${(d.pct_change * 100).toFixed(2)}%`
          : ""
      ),
      hovertemplate:
        "%{x|%Y-%m-%d %H:%M}<br>$%{y:,.4f}<br>%{text}<extra></extra>",
    };
    const tpLine = {
      type: "scatter" as const,
      mode: "lines",
      x: tpX,
      y: tpY,
      name: "TP",
      line: { color: "#10b981", width: 2, dash: "dot" },
      hovertemplate: "%{x|%Y-%m-%d %H:%M}<br>TP: $%{y:,.4f}<extra></extra>",
    };
    const slLine = {
      type: "scatter" as const,
      mode: "lines",
      x: slX,
      y: slY,
      name: "SL",
      line: { color: "#ef4444", width: 2, dash: "dot" },
      hovertemplate: "%{x|%Y-%m-%d %H:%M}<br>SL: $%{y:,.4f}<extra></extra>",
    };
    const tpMarks = {
      type: "scatter" as const,
      mode: "markers",
      x: tpPoints.map((p) => p.x),
      y: tpPoints.map((p) => p.y),
      name: "TP marks",
      marker: { color: "#10b981", size: 14, symbol: "line-ew" },
      hovertemplate: "%{x|%Y-%m-%d %H:%M}<br>TP: $%{y:,.4f}<extra></extra>",
    };
    const slMarks = {
      type: "scatter" as const,
      mode: "markers",
      x: slPoints.map((p) => p.x),
      y: slPoints.map((p) => p.y),
      name: "SL marks",
      marker: { color: "#ef4444", size: 14, symbol: "line-ew" },
      hovertemplate: "%{x|%Y-%m-%d %H:%M}<br>SL: $%{y:,.4f}<extra></extra>",
    };
    return [candle, maFast, maSlow, tpLine, slLine, tpMarks, slMarks, entryTrace, winTrace, lossTrace];
  }, [enrichedChartData, datasetFilter, xRange]);

  const plotShapes = useMemo(() => {
    const shapes: any[] = [];
    if (!enrichedChartData.length) return shapes;
    let current = enrichedChartData[0].data_set;
    let startIdx = 0;
    enrichedChartData.forEach((d, idx) => {
      if (d.data_set !== current) {
        const x0 = enrichedChartData[startIdx].timeMs ?? enrichedChartData[startIdx].time;
        const x1 = enrichedChartData[idx - 1].timeMs ?? enrichedChartData[idx - 1].time;
        shapes.push({
          type: "rect",
          xref: "x",
          yref: "paper",
          x0,
          x1,
          y0: 0,
          y1: 1,
          fillcolor:
            current === "train"
              ? "rgba(0, 227, 150, 0.05)"
              : current === "test"
                ? "rgba(255, 170, 23, 0.05)"
                : "rgba(90, 103, 216, 0.05)",
          line: { width: 0 },
        });
        current = d.data_set;
        startIdx = idx;
      }
    });
    const x0 = enrichedChartData[startIdx].timeMs ?? enrichedChartData[startIdx].time;
    const x1 = enrichedChartData[enrichedChartData.length - 1].timeMs ?? enrichedChartData[enrichedChartData.length - 1].time;
    shapes.push({
      type: "rect",
      xref: "x",
      yref: "paper",
      x0,
      x1,
      y0: 0,
      y1: 1,
      fillcolor:
        current === "train"
          ? "rgba(0, 227, 150, 0.05)"
          : current === "test"
            ? "rgba(255, 170, 23, 0.05)"
            : "rgba(90, 103, 216, 0.05)",
      line: { width: 0 },
    });
    return shapes;
  }, [enrichedChartData]);

  const filteredRows = useMemo(() => {
    const base = datasetFilter.length ? enrichedChartData.filter((d) => datasetFilter.includes(d.data_set || "")) : enrichedChartData;
    if (!xRange) return base;
    return base.filter(
      (d) => d.timeMs !== undefined && d.timeMs >= xRange[0] && d.timeMs <= xRange[1]
    );
  }, [enrichedChartData, xRange, datasetFilter]);

  const handleRelayout = (e: any) => {
    const r0 = e["xaxis.range[0]"];
    const r1 = e["xaxis.range[1]"];
    const auto = e["xaxis.autorange"];
    if (r0 && r1) {
      setXRange([new Date(r0).valueOf(), new Date(r1).valueOf()]);
    } else if (auto) {
      setXRange(null);
    }
  };

  const metricKeys = useMemo(() => {
    const keys = new Set<string>();
    results.forEach((r) => {
      Object.keys(r.metrics || {}).forEach((k) => keys.add(k));
    });
    return Array.from(keys);
  }, [results]);

  const tableColumns = [
    "time",
    "close",
    "ma_fast",
    "ma_slow",
    "tp_price",
    "sl_price",
    "trade",
    "exit_price",
    "trade_label",
    "pct_change",
    "data_set",
  ];
  const currencyFmt = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  });

  const toggleDataset = (ds: string) => {
    setXRange(null);
    setDatasetFilter((prev) =>
      prev.includes(ds) ? prev.filter((x) => x !== ds) : [...prev, ds]
    );
  };

  const formatVal = (v: any) => {
    if (typeof v === "number" && Number.isFinite(v)) {
      return currencyFmt.format(v);
    }
    if (v instanceof Date) return v.toISOString();
    return v ?? "";
  };

  return (
    <DashboardPageLayout
      header={{
        title: "Evaluate strategy",
        description: "Corre y compara sets pre/train/test",
        icon: BracketsIcon,
      }}
    >
      <div className="space-y-6">
        <Card className="p-4 space-y-3">
          <div className="text-lg font-semibold">Datos disponibles</div>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <Label>Ticker</Label>
              <Select value={selectedTicker} onValueChange={(v) => { setSelectedTicker(v); setSelectedFreq(""); }}>
                <SelectTrigger>
                  <SelectValue placeholder="Selecciona ticker" />
                </SelectTrigger>
                <SelectContent>
                  {[...new Set(marketData.map((m) => m.ticker))].map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Frecuencia</Label>
              <Select value={selectedFreq} onValueChange={setSelectedFreq} disabled={!selectedTicker}>
                <SelectTrigger>
                  <SelectValue placeholder="Selecciona frecuencia" />
                </SelectTrigger>
                <SelectContent>
                  {freqsForTicker.map((f) => (
                    <SelectItem key={`${f.ticker}-${f.freq}`} value={f.freq}>
                      {f.freq}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1 text-sm">
              <div className="font-semibold">Rango disponible</div>
              <div>Min: {selectedMeta?.min_time ? String(selectedMeta.min_time) : "-"}</div>
              <div>Max: {selectedMeta?.max_time ? String(selectedMeta.max_time) : "-"}</div>
              <div>Filas: {selectedMeta?.rows ?? 0}</div>
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1">
              <Label>Fecha inicio (opcional)</Label>
              <Input
                type="datetime-local"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                disabled={!selectedFreq}
              />
            </div>
            <div className="space-y-1">
              <Label>Fecha fin (opcional)</Label>
              <Input
                type="datetime-local"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                disabled={!selectedFreq}
              />
            </div>
          </div>
        </Card>
        <Card className="p-4 space-y-4">
          <div className="text-lg font-semibold">Configurar evaluación</div>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <Label>Entry</Label>
              <Select value={entry} onValueChange={setEntry}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ENTRY.map((opt) => (
                    <SelectItem key={opt.name} value={opt.name}>
                      {opt.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {Object.keys(currentParams("entry")).map((p) => (
                <div key={p} className="space-y-1">
                  <Label>{p} (valor)</Label>
                  <Input
                    placeholder="valor"
                    value={params[`entry_${p}`] || ""}
                    onChange={(e) => handleParamChange("entry", p, e.target.value)}
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
                  {TP.map((opt) => (
                    <SelectItem key={opt.name} value={opt.name}>
                      {opt.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {Object.keys(currentParams("tp")).map((p) => (
                <div key={p} className="space-y-1">
                  <Label>{p} (valor)</Label>
                  <Input
                    placeholder="valor"
                    value={params[`tp_${p}`] || ""}
                    onChange={(e) => handleParamChange("tp", p, e.target.value)}
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
                  {SL.map((opt) => (
                    <SelectItem key={opt.name} value={opt.name}>
                      {opt.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {Object.keys(currentParams("sl")).map((p) => (
                <div key={p} className="space-y-1">
                  <Label>{p} (valor)</Label>
                  <Input
                    placeholder="valor"
                    value={params[`sl_${p}`] || ""}
                    onChange={(e) => handleParamChange("sl", p, e.target.value)}
                  />
                </div>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            {["pre_out_of_time", "train", "test"].map((ds) => (
              <Button
                key={ds}
                size="sm"
                variant={datasetFilter.includes(ds) ? "default" : "outline"}
                onClick={() => toggleDataset(ds)}
              >
                {ds}
              </Button>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <div className="space-y-1">
              <Label>Importar solución</Label>
              <Input type="file" accept="application/json" onChange={(e) => handleFile(e.target.files?.[0])} />
            </div>
            <Button onClick={runEvaluate} disabled={running}>
              {running ? "Evaluating..." : "Run Evaluate"}
            </Button>
          </div>
          <Card className="p-3 space-y-2">
            <div className="font-semibold">Logs</div>
            <div className="h-32 overflow-auto text-xs bg-muted/30 p-2 rounded">
              {logs.map((l, i) => (
                <div key={i}>{l}</div>
              ))}
            </div>
          </Card>
        </Card>
        <div className="space-y-4">
          <Card className="p-4 space-y-2">
            <div className="font-semibold">Métricas por dataset</div>
            {results.length === 0 ? (
              <div className="text-xs text-muted-foreground">Ejecuta la evaluación para ver métricas.</div>
            ) : (
              <div className="overflow-auto">
                <table className="min-w-full text-xs">
                  <thead>
                    <tr>
                      <th className="px-2 py-1 text-left font-semibold">dataset</th>
                      {metricKeys.map((k) => (
                        <th key={k} className="px-2 py-1 text-left font-semibold">
                          {k}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((r) => (
                      <tr key={r.dataset} className="border-b">
                        <td className="px-2 py-1 font-semibold">{r.dataset}</td>
                        {metricKeys.map((k) => (
                          <td key={k} className="px-2 py-1">
                            {r.metrics && k in r.metrics ? String(r.metrics[k]) : ""}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
          <Card className="p-4 space-y-3 min-h-[420px]">
            <div className="flex items-center justify-between">
              <div className="text-sm font-semibold">Gráfico</div>
              <Button size="sm" variant="outline" onClick={() => setShowPlot(true)} disabled={plotData.length === 0 || showPlot}>
                {showPlot ? "Gráfico listo" : "Mostrar gráfico"}
              </Button>
            </div>
            <div className="w-full min-h-[420px]">
              {!showPlot ? (
                <div className="text-xs text-muted-foreground">Carga el gráfico cuando lo necesites para evitar latencia.</div>
              ) : plotData.length === 0 ? (
                <div className="text-xs text-muted-foreground">Ejecuta la evaluación para ver datos.</div>
              ) : (
                <Plot
                  data={plotData as any}
                  layout={{
                    autosize: true,
                    height: 480,
                    margin: { l: 40, r: 20, t: 20, b: 40 },
                    xaxis: {
                      type: "date",
                      tickformat: "%Y-%m-%d %H:%M",
                      rangeslider: { visible: true },
                      showspikes: true,
                    },
                    yaxis: { fixedrange: false, showspikes: true },
                    shapes: plotShapes,
                    dragmode: "zoom",
                  }}
                  config={{
                    responsive: true,
                    displaylogo: false,
                    modeBarButtonsToRemove: ["select2d", "lasso2d"],
                    modeBarButtonsToAdd: ["zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d"],
                    scrollZoom: true,
                    doubleClick: "reset",
                  }}
                  style={{ width: "100%", height: "100%" }}
                  onRelayout={handleRelayout}
                  useResizeHandler
                />
              )}
            </div>
          </Card>
          <Card className="p-4 space-y-3">
            <div className="text-sm font-semibold">Datos filtrados</div>
            <div className="overflow-auto">
              <table className="min-w-full text-xs">
                <thead>
                  <tr>
                    {tableColumns.map((c) => (
                      <th key={c} className="px-2 py-1 text-left font-semibold">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredRows.slice(0, 200).map((row, idx) => (
                    <tr key={idx} className="border-b">
                      {tableColumns.map((c) => (
                        <td key={c} className="px-2 py-1">
                          {formatVal((row as any)[c])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {filteredRows.length > 200 && (
                <div className="text-xs text-muted-foreground mt-1">
                  Mostrando 200 de {filteredRows.length} filas
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </DashboardPageLayout>
  );
}
