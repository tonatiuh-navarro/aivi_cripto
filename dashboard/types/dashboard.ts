export type SummaryFreq = "daily" | "weekly" | "monthly";

export type WalletSummary = {
  id: string;
  name: string;
  initial_balance: number;
  reference_date: string;
};

export type WalletCreatePayload = {
  name: string;
  initial_balance: number;
  reference_date: string;
};

export type ScenarioOption = {
  name: string;
  parent?: string | null;
};

export type ComparisonEventRow = {
  date: string;
  concept: string;
  income_base: number;
  expenses_base: number;
  income_variant: number;
  expenses_variant: number;
  income_delta: number;
  expenses_delta: number;
};

export type ComparisonSummaryRow = {
  date: string;
  income_base: number;
  expenses_base: number;
  net_base: number;
  balance_base: number;
  income_variant: number;
  expenses_variant: number;
  net_variant: number;
  balance_variant: number;
  income_delta: number;
  expenses_delta: number;
  net_delta: number;
  balance_delta: number;
};

export type CashFlowSpecPayload = {
  id: string;
  concept: string;
  amount: number;
  frequency: string;
  start_date: string;
  end_date?: string | null;
  metadata: Record<string, unknown>;
};

export type AlertPayload = {
  id: string;
  title: string;
  message: string;
  severity: "success" | "warning" | "danger";
  date?: string | null;
};

export type DashboardStatMetric = {
  label: string;
  value: string;
  description?: string;
  tag?: string;
  icon: "gear" | "proccesor" | "boom";
  intent?: "positive" | "negative" | "neutral";
  direction?: "up" | "down";
};

export type ChartPoint = {
  date: string;
  income: number;
  expenses: number;
  balance: number;
};

export type Notification = {
  id: string;
  title: string;
  message: string;
  timestamp: string;
  type: "info" | "warning" | "success" | "danger";
  read: boolean;
  priority: "low" | "medium" | "high";
};

export type WidgetData = {
  location: string;
  timezone: string;
  temperature: string;
};

export type BalanceResponse = {
  as_of: string;
  balance: number;
};
