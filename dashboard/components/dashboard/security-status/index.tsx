import DashboardCard from "@/components/dashboard/card";
import type { AlertPayload } from "@/types/dashboard";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
import { Bullet } from "@/components/ui/bullet";

const alertVariants = cva("border rounded-md ring-4", {
  variants: {
    variant: {
      success: "border-success bg-success/5 text-success ring-success/30",
      warning: "border-warning bg-warning/5 text-warning ring-warning/30",
      danger: [
        "border-destructive bg-destructive/5",
        "text-destructive ring-destructive/30",
      ].join(" "),
    },
  },
  defaultVariants: {
    variant: "success",
  },
});

type AlertCardProps = {
  alert: AlertPayload;
} & VariantProps<typeof alertVariants>;

function AlertCard({ alert, variant }: AlertCardProps) {
  return (
    <div className={cn(alertVariants({ variant }))}>
      <div
        className="flex items-center gap-2 py-1 px-2 border-b border-current"
      >
        <Bullet
          size="sm"
          variant={variant === "danger" ? "destructive" : variant}
        />
        <span className="text-sm font-medium">{alert.title}</span>
      </div>
      <div className="py-2 px-3">
        <p className="text-sm">{alert.message}</p>
        {alert.date && (
          <p className="text-xs opacity-50 mt-1">Fecha {alert.date}</p>
        )}
      </div>
    </div>
  );
}

type Props = {
  alerts: AlertPayload[];
};

export default function SecurityStatus({ alerts }: Props) {
  return (
    <DashboardCard title="SALUD FINANCIERA" intent="success">
      <div className="grid gap-3">
        {alerts.map((alert) => (
          <AlertCard key={alert.id} alert={alert} variant={alert.severity} />
        ))}
        {alerts.length === 0 && (
          <div className="text-sm text-muted-foreground">
            Sin alertas para el rango seleccionado
          </div>
        )}
      </div>
    </DashboardCard>
  );
}
