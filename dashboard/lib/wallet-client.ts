import type {
  AlertPayload,
  BalanceResponse,
  CashFlowSpecPayload,
  ComparisonEventRow,
  ComparisonSummaryRow,
  ScenarioOption,
  WalletCreatePayload,
  WalletSummary,
} from "@/types/dashboard";

const API_BASE =
  process.env.NEXT_PUBLIC_WALLET_API ?? "http://localhost:8000";

type ComparisonResponse = {
  base: string;
  variant: string;
  events: ComparisonEventRow[];
  summary: ComparisonSummaryRow[];
};

const request = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Request failed ${res.status}`);
  }
  return (await res.json()) as T;
};

const withWallet = (path: string, walletId: string) => {
  const connector = path.includes("?") ? "&" : "?";
  return `${path}${connector}wallet_id=${walletId}`;
};

export const fetchWallets = async (): Promise<WalletSummary[]> => {
  return request<WalletSummary[]>("/wallets");
};

export const createWallet = async (
  payload: WalletCreatePayload,
): Promise<WalletSummary> => {
  return request<WalletSummary>("/wallets", {
    method: "POST",
    body: JSON.stringify(payload),
  });
};

export const fetchScenarios = async (
  walletId: string,
): Promise<ScenarioOption[]> => {
  return request<ScenarioOption[]>(withWallet("/scenarios", walletId));
};

export const fetchComparison = async (params: {
  base: string;
  variant: string;
  start_date: string;
  end_date: string;
  freq: string;
  wallet_id: string;
}): Promise<ComparisonResponse> => {
  const qs = new URLSearchParams(params).toString();
  return request<ComparisonResponse>(`/scenarios/compare?${qs}`);
};

export const fetchEvents = async (
  walletId: string,
): Promise<CashFlowSpecPayload[]> => {
  return request<CashFlowSpecPayload[]>(withWallet("/events", walletId));
};

export const createEvent = async (
  payload: CashFlowSpecPayload,
  walletId: string,
): Promise<CashFlowSpecPayload[]> => {
  return request<CashFlowSpecPayload[]>(withWallet("/events", walletId), {
    method: "POST",
    body: JSON.stringify(payload),
  });
};

export const updateEvent = async (
  payload: CashFlowSpecPayload,
  walletId: string,
): Promise<CashFlowSpecPayload[]> => {
  return request<CashFlowSpecPayload[]>(
    withWallet(`/events/${payload.id}`, walletId),
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
  );
};

export const deleteEvent = async (
  eventId: string,
  walletId: string,
): Promise<CashFlowSpecPayload[]> => {
  return request<CashFlowSpecPayload[]>(
    withWallet(`/events/${eventId}`, walletId),
    {
      method: "DELETE",
    },
  );
};

export const fetchAlerts = async (params: {
  start_date: string;
  end_date: string;
  scenario: string;
  wallet_id: string;
}): Promise<AlertPayload[]> => {
  const qs = new URLSearchParams(params).toString();
  const data = await request<{ alerts: AlertPayload[] }>(
    `/alerts?${qs}`,
  );
  return data.alerts;
};

export const fetchBalance = async (params: {
  wallet_id: string;
  as_of: string;
  scenario?: string;
}): Promise<BalanceResponse> => {
  const search = new URLSearchParams({
    wallet_id: params.wallet_id,
    as_of: params.as_of,
    scenario: params.scenario ?? "baseline",
  }).toString();
  return request<BalanceResponse>(`/balance?${search}`);
};
