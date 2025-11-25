"use client";

import { useState } from "react";
import DashboardPageLayout from "@/components/dashboard/layout";
import BracketsIcon from "@/components/icons/brackets";
import { EventsTable } from "@/components/dashboard/events-table";
import { WalletInfoPanel } from "@/components/dashboard/wallet-info";
import { useWalletDashboard } from "@/hooks/useWalletDashboard";
import { Spinner } from "@/components/ui/spinner";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function DashboardOverview() {
  const {
    wallets,
    walletId,
    controls,
    stats,
    chart,
    events,
    alerts,
    loading,
    error,
    saveEvent,
    removeEvent,
    changeWallet,
    createWallet,
    updateControl,
  } = useWalletDashboard();
  const [walletDialogOpen, setWalletDialogOpen] = useState(false);
  const today = new Date().toISOString().slice(0, 10);
  const [walletForm, setWalletForm] = useState({
    name: "",
    initial_balance: "0",
    reference_date: today,
  });

  const handleCreateWallet = async () => {
    await createWallet({
      name: walletForm.name || "Nueva wallet",
      initial_balance: Number(walletForm.initial_balance) || 0,
      reference_date: walletForm.reference_date,
    });
    setWalletDialogOpen(false);
    setWalletForm({
      name: "",
      initial_balance: "0",
      reference_date: today,
    });
  };

  const handleWalletChange = (value: string) => {
    if (value === "__create__") {
      setWalletDialogOpen(true);
      return;
    }
    changeWallet(value);
  };

  return (
    <DashboardPageLayout
      header={{
        title: "Wallet",
        description: "Gestiona tus acciones y flujos",
        icon: BracketsIcon,
      }}
    >
      <div className="flex flex-col gap-4 mb-6">
        <div className="grid gap-2">
          <Label>Wallet</Label>
          <Select
            value={walletId || undefined}
            onValueChange={handleWalletChange}
          >
            <SelectTrigger>
              <SelectValue placeholder="Selecciona o crea una wallet" />
            </SelectTrigger>
            <SelectContent>
              {wallets.map((wallet) => (
                <SelectItem key={wallet.id} value={wallet.id}>
                  {wallet.name}
                </SelectItem>
              ))}
              <SelectItem value="__create__">+ Crear nueva wallet</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1">
            <Label>Inicio</Label>
            <Input
              type="date"
              value={controls.startDate}
              onChange={(e) =>
                updateControl({ startDate: e.target.value || today })
              }
            />
          </div>
          <div className="space-y-1">
            <Label>Fin</Label>
            <Input
              type="date"
              value={controls.endDate}
              onChange={(e) =>
                updateControl({ endDate: e.target.value || today })
              }
            />
          </div>
        </div>
        <Dialog open={walletDialogOpen} onOpenChange={setWalletDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Crear wallet</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-1">
                <Label>Nombre</Label>
                <Input
                  value={walletForm.name}
                  onChange={(e) =>
                    setWalletForm((prev) => ({
                      ...prev,
                      name: e.target.value,
                    }))
                  }
                />
              </div>
              <div className="space-y-1">
                <Label>Saldo inicial</Label>
                <Input
                  type="number"
                  value={walletForm.initial_balance}
                  onChange={(e) =>
                    setWalletForm((prev) => ({
                      ...prev,
                      initial_balance: e.target.value,
                    }))
                  }
                />
              </div>
              <div className="space-y-1">
                <Label>Fecha de referencia</Label>
                <Input
                  type="date"
                  value={walletForm.reference_date}
                  onChange={(e) =>
                    setWalletForm((prev) => ({
                      ...prev,
                      reference_date: e.target.value,
                    }))
                  }
                />
              </div>
              <Button onClick={handleCreateWallet}>Guardar</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
      {!walletId ? (
        <div className="text-sm text-muted-foreground">
          Crea una wallet para comenzar.
        </div>
      ) : (
        <>
          {error && (
            <div className="text-sm text-destructive mb-4">{error}</div>
          )}
          {loading && (
            <div
              className="flex items-center gap-2 text-sm text-muted-foreground mb-4"
            >
              <Spinner className="size-4" />
              Actualizando datos...
            </div>
          )}
          <div className="mb-6">
            <EventsTable
              events={events}
              onSave={saveEvent}
              onDelete={removeEvent}
              loading={loading}
            />
          </div>
          <WalletInfoPanel stats={stats} chart={chart} />
        </>
      )}
    </DashboardPageLayout>
  );
}
