"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import MonkeyIcon from "@/components/icons/monkey";
import MobileNotifications from
  "@/components/dashboard/notifications/mobile-notifications";
import BellIcon from "@/components/icons/bell";
import { useEffect, useState } from "react";
import type { Notification } from "@/types/dashboard";
import { fetchAlerts } from "@/lib/wallet-client";
import { cn } from "@/lib/utils";

const toNotification = (alert: {
  id: string;
  title: string;
  message: string;
  severity: string;
  date?: string | null;
}): Notification => ({
  id: alert.id,
  title: alert.title,
  message: alert.message,
  timestamp: alert.date ?? new Date().toISOString(),
  type: alert.severity === "danger" ? "error" : alert.severity,
  read: false,
  priority: alert.severity === "danger" ? "high" : "medium",
});

export function MobileHeader() {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  useEffect(() => {
    const today = new Date();
    const start = today.toISOString().slice(0, 10);
    const end = new Date(today.getTime() + 14 * 86400000)
      .toISOString()
      .slice(0, 10);
    fetchAlerts({
      start_date: start,
      end_date: end,
      scenario: "baseline",
    })
      .then((alerts) => setNotifications(alerts.map(toNotification)))
      .catch(() => setNotifications([]));
  }, []);

  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <div
      className={cn(
        "lg:hidden h-header-mobile sticky top-0 z-50",
        "bg-background/95 backdrop-blur-sm border-b border-border",
      )}
    >
      <div className="flex items-center justify-between px-4 py-3">
        <SidebarTrigger />

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div
              className={cn(
                "h-8 w-16 bg-primary rounded",
                "flex items-center justify-center",
              )}
            >
              <MonkeyIcon className="size-6 text-primary-foreground" />
            </div>
          </div>
        </div>

        <Sheet>
          <SheetTrigger asChild>
            <Button variant="secondary" size="icon" className="relative">
              {unreadCount > 0 && (
                <Badge
                  className={cn(
                    "absolute border-2 border-background -top-1 -left-2",
                    "h-5 w-5 text-xs p-0 flex items-center justify-center",
                  )}
                >
                  {unreadCount > 9 ? "9+" : unreadCount}
                </Badge>
              )}
              <BellIcon className="size-4" />
            </Button>
          </SheetTrigger>

          <SheetContent
            closeButton={false}
            side="right"
            className="w-[80%] max-w-md p-0"
          >
            <MobileNotifications notifications={notifications} />
          </SheetContent>
        </Sheet>
      </div>
    </div>
  );
}
