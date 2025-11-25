"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createEvent,
  deleteEvent,
  fetchAlerts,
  fetchComparison,
  fetchEvents,
  fetchScenarios,
  fetchWallets,
  createWallet as requestCreateWallet,
  updateEvent,
} from "@/lib/wallet-client";
import type {
  AlertPayload,
  CashFlowSpecPayload,
  ChartPoint,
  DashboardStatMetric,
  Notification,
  ScenarioOption,
  SummaryFreq,
  WalletCreatePayload,
  WalletSummary,
} from "@/types/dashboard";

type Controls = {
  base: string;
  variant: string;
  startDate: string;
  endDate: string;
  freq: SummaryFreq;
};

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

const dateRange = () => {
  const end = new Date();
  const start = new Date();
  start.setMonth(start.getMonth() - 1);
  return {
    start: start.toISOString().slice(0, 10),
    end: end.toISOString().slice(0, 10),
  };
};

export const useWalletDashboard = () => {
  const initialRange = dateRange();
  const [controls, setControls] = useState<Controls>({
    base: "",
    variant: "",
    startDate: initialRange.start,
    endDate: initialRange.end,
    freq: "weekly",
  });
  const [scenarios, setScenarios] = useState<ScenarioOption[]>([]);
  const [wallets, setWallets] = useState<WalletSummary[]>([]);
  const [walletId, setWalletId] = useState("");
  const [stats, setStats] = useState<DashboardStatMetric[]>([]);
  const [chart, setChart] = useState<ChartPoint[]>([]);
  const [events, setEvents] = useState<CashFlowSpecPayload[]>([]);
  const [alerts, setAlerts] = useState<AlertPayload[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [endingBalance, setEndingBalance] = useState(0);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const storedWallet =
      window.localStorage.getItem("walletDashboard:selectedWallet");
    const storedEnd =
      window.localStorage.getItem("walletDashboard:endDate");
    if (storedWallet) {
      setWalletId(storedWallet);
    }
    if (storedEnd) {
      setControls((prev) => ({ ...prev, endDate: storedEnd }));
    }
  }, []);

  const notifications: Notification[] = useMemo(() => {
    return alerts.map((alert) => ({
      id: alert.id,
      title: alert.title,
      message: alert.message,
      timestamp: alert.date ?? new Date().toISOString(),
      type: alert.severity === "danger" ? "error" : alert.severity,
      read: false,
      priority: alert.severity === "danger" ? "high" : "medium",
    }));
  }, [alerts]);

  const refreshWallets = useCallback(
    async (preferredId?: string) => {
      try {
        const data = await fetchWallets();
        setWallets(data);
        if (preferredId) {
          setWalletId(preferredId);
          return;
        }
        if (!walletId && data.length > 0) {
          setWalletId(data[0].id);
          return;
        }
        if (
          walletId &&
          !data.some((wallet) => wallet.id === walletId) &&
          data.length > 0
        ) {
          setWalletId(data[0].id);
        }
        if (data.length === 0) {
          setWalletId("");
        }
      } catch (err) {
        setError((err as Error).message);
      }
    },
    [walletId],
  );

  useEffect(() => {
    refreshWallets();
  }, [refreshWallets]);

  const dispatchUpdate = useCallback(
    (nextWallet?: string, nextEnd?: string) => {
      if (typeof window === "undefined") {
        return;
      }
      window.dispatchEvent(
        new CustomEvent("walletDashboard:update", {
          detail: {
            walletId: nextWallet ?? walletId,
            endDate: nextEnd ?? controls.endDate,
          },
        }),
      );
    },
    [walletId, controls.endDate],
  );

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (walletId) {
      window.localStorage.setItem(
        "walletDashboard:selectedWallet",
        walletId,
      );
      dispatchUpdate(walletId);
    }
  }, [walletId, dispatchUpdate]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(
      "walletDashboard:endDate",
      controls.endDate,
    );
    dispatchUpdate(undefined, controls.endDate);
  }, [controls.endDate, dispatchUpdate]);

  useEffect(() => {
    if (!walletId) {
      setScenarios([]);
      setControls((prev) => ({
        ...prev,
        base: "",
        variant: "",
      }));
      return;
    }
    const loadScenarios = async () => {
      try {
        const data = await fetchScenarios(walletId);
        setScenarios(data);
        if (data.length === 0) {
          setControls((prev) => ({ ...prev, base: "", variant: "" }));
          return;
        }
        setControls((prev) => {
          const nextBase = data.some((item) => item.name === prev.base)
            ? prev.base
            : data[0].name;
          const fallback =
            data.find((item) => item.name !== nextBase)?.name ||
            nextBase;
          const nextVariant = data.some(
            (item) => item.name === prev.variant,
          )
            ? prev.variant
            : fallback;
          return {
            ...prev,
            base: nextBase,
            variant: nextVariant,
          };
        });
      } catch (err) {
        setError((err as Error).message);
      }
    };
    loadScenarios();
  }, [walletId]);

  const computeStats = useCallback((summaryRows: ChartPoint[]) => {
    if (summaryRows.length === 0) {
      return [];
    }
    const totalIncome = summaryRows.reduce(
      (acc, row) => acc + row.income,
      0,
    );
    const totalExpenses = summaryRows.reduce(
      (acc, row) => acc + row.expenses,
      0,
    );
    const balance = summaryRows[summaryRows.length - 1]?.balance ?? 0;
    const net = totalIncome - totalExpenses;
    return [
      {
        label: "Ingresos plan",
        value: currency.format(totalIncome),
        description: "Total periodo seleccionado",
        icon: "gear",
        intent: "positive",
        direction: "up",
      },
      {
        label: "Gastos plan",
        value: currency.format(totalExpenses),
        description: "Servicios y renta",
        icon: "proccesor",
        intent: "negative",
        direction: "down",
      },
      {
        label: "Saldo fin plan",
        value: currency.format(balance),
        description: `Neto ${currency.format(net)}`,
        icon: "boom",
        intent: net >= 0 ? "positive" : "negative",
        direction: net >= 0 ? "up" : "down",
      },
    ];
  }, []);

  const refresh = useCallback(async () => {
    if (!controls.base || !controls.variant || !walletId) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [comparison, eventData, alertData] = await Promise.all([
        fetchComparison({
          base: controls.base,
          variant: controls.variant,
          start_date: controls.startDate,
          end_date: controls.endDate,
          freq: controls.freq,
          wallet_id: walletId,
        }),
        fetchEvents(walletId),
        fetchAlerts({
          start_date: controls.startDate,
          end_date: controls.endDate,
          scenario: controls.base,
          wallet_id: walletId,
        }),
      ]);
      const summaryRows: ChartPoint[] = comparison.summary.map((row) => ({
        date: row.date,
        income: row.income_variant,
        expenses: row.expenses_variant,
        balance: row.balance_variant,
      }));
      setChart(summaryRows);
      setStats(computeStats(summaryRows));
      if (summaryRows.length > 0) {
        setEndingBalance(summaryRows.at(-1)?.balance ?? 0);
      }
      setEvents(eventData);
      setAlerts(alertData);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [
    controls.base,
    controls.variant,
    controls.startDate,
    controls.endDate,
    controls.freq,
    walletId,
    computeStats,
  ]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const saveEvent = useCallback(
    async (payload: CashFlowSpecPayload) => {
      if (!walletId) {
        return;
      }
      const record = payload.id
        ? payload
        : { ...payload, id: crypto.randomUUID() };
      await (payload.id
        ? updateEvent(record, walletId)
        : createEvent(record, walletId));
      await refresh();
    },
    [refresh, walletId],
  );

  const removeEvent = useCallback(
    async (id: string) => {
      if (!walletId) {
        return;
      }
      await deleteEvent(id, walletId);
      await refresh();
    },
    [refresh, walletId],
  );

  const updateControl = useCallback(
    (partial: Partial<Controls>) => {
      setControls((prev) => ({
        ...prev,
        ...partial,
      }));
    },
    [],
  );

  const changeWallet = useCallback((id: string) => {
    setWalletId(id);
  }, []);

  const createWallet = useCallback(
    async (payload: WalletCreatePayload) => {
      const wallet = await requestCreateWallet(payload);
      await refreshWallets(wallet.id);
    },
    [refreshWallets],
  );

  return {
    wallets,
    walletId,
    controls,
    scenarios,
    stats,
    chart,
    events,
    alerts,
    notifications,
    loading,
    error,
    updateControl,
    saveEvent,
    removeEvent,
    changeWallet,
    createWallet,
    endingBalance,
  };
};
