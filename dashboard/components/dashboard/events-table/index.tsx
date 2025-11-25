"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import DashboardCard from "@/components/dashboard/card";
import type { CashFlowSpecPayload } from "@/types/dashboard";
import { cn } from "@/lib/utils";

type Props = {
  events: CashFlowSpecPayload[];
  onSave: (event: CashFlowSpecPayload) => Promise<void> | void;
  onDelete: (id: string) => Promise<void> | void;
  loading?: boolean;
};

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

const emptyEvent: CashFlowSpecPayload = {
  id: "",
  concept: "",
  amount: 0,
  frequency: "once",
  start_date: "",
  end_date: "",
  metadata: {},
};

export function EventsTable({
  events,
  onSave,
  onDelete,
  loading,
}: Props) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<CashFlowSpecPayload>(emptyEvent);

  const handleSubmit = async () => {
    await onSave(form);
    setOpen(false);
    setForm(emptyEvent);
  };

  const handleEdit = (event: CashFlowSpecPayload) => {
    setForm(event);
    setOpen(true);
  };

  const handleAdd = () => {
    setForm(emptyEvent);
    setOpen(true);
  };

  return (
    <DashboardCard
      title="EVENTOS"
      intent="default"
      addon={
        <Button variant="outline" size="sm" onClick={handleAdd}>
          Nueva acción
        </Button>
      }
    >
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Concepto</TableHead>
              <TableHead>Frecuencia</TableHead>
              <TableHead>Monto</TableHead>
              <TableHead>Inicio</TableHead>
              <TableHead>Fin</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {events.map((event) => (
              <TableRow key={event.id}>
                <TableCell>{event.concept}</TableCell>
                <TableCell className="uppercase">{event.frequency}</TableCell>
                <TableCell
                  className={cn(
                    event.amount >= 0 ? "text-success" : "text-destructive",
                  )}
                >
                  {currency.format(event.amount)}
                </TableCell>
                <TableCell>{event.start_date}</TableCell>
                <TableCell>{event.end_date || "—"}</TableCell>
                <TableCell className="text-right space-x-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleEdit(event)}
                  >
                    Editar
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => onDelete(event.id)}
                    disabled={loading}
                  >
                    Eliminar
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {form.id ? "Actualizar acción" : "Nueva acción"}
            </DialogTitle>
          </DialogHeader>
          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label>Concepto</Label>
              <Input
                value={form.concept}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, concept: e.target.value }))
                }
              />
            </div>
            <div className="grid gap-2">
              <Label>Monto</Label>
              <Input
                type="number"
                value={form.amount}
                onChange={(e) =>
                  setForm((prev) => ({
                    ...prev,
                    amount: Number(e.target.value),
                  }))
                }
              />
            </div>
            <div className="grid gap-2">
              <Label>Frecuencia</Label>
              <Select
                value={form.frequency}
                onValueChange={(value) =>
                  setForm((prev) => ({ ...prev, frequency: value }))
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="once">Única</SelectItem>
                  <SelectItem value="weekly">Semanal</SelectItem>
                  <SelectItem value="monthly">Mensual</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>Inicio</Label>
              <Input
                type="date"
                value={form.start_date}
                onChange={(e) =>
                  setForm((prev) => ({
                    ...prev,
                    start_date: e.target.value,
                  }))
                }
              />
            </div>
            <div className="grid gap-2">
              <Label>Fin</Label>
              <Input
                type="date"
                value={form.end_date ?? ""}
                onChange={(e) =>
                  setForm((prev) => ({
                    ...prev,
                    end_date: e.target.value,
                  }))
                }
              />
            </div>
            <Button onClick={handleSubmit} disabled={loading}>
              Guardar
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </DashboardCard>
  );
}
