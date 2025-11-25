"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";
import TVNoise from "@/components/ui/tv-noise";
import Image from "next/image";
import { cn } from "@/lib/utils";
import { fetchBalance } from "@/lib/wallet-client";

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

export default function Widget() {
  const [currentTime, setCurrentTime] = useState(new Date());
  const [balance, setBalance] = useState<number | null>(null);
  const [asOf, setAsOf] = useState<string | null>(null);

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  const loadBalance = useCallback(async () => {
    if (typeof window === "undefined") {
      return;
    }
    const walletId = window.localStorage.getItem(
      "walletDashboard:selectedWallet",
    );
    const endDate = window.localStorage.getItem(
      "walletDashboard:endDate",
    );
    setAsOf(endDate);
    if (!walletId || !endDate) {
      setBalance(null);
      return;
    }
    try {
      const response = await fetchBalance({
        wallet_id: walletId,
        as_of: endDate,
      });
      setBalance(response.balance);
    } catch {
      setBalance(null);
    }
  }, []);

  useEffect(() => {
    loadBalance();
    const handler = () => {
      loadBalance();
    };
    window.addEventListener("walletDashboard:update", handler);
    return () => {
      window.removeEventListener("walletDashboard:update", handler);
    };
  }, [loadBalance]);

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString("en-US", {
      hour12: true,
      hour: "numeric",
      minute: "2-digit",
    });
  };

  const formatDate = (date: Date) => {
    const dayOfWeek = date.toLocaleDateString("es-MX", {
      weekday: "long",
    });
    const restOfDate = date.toLocaleDateString("es-MX", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
    return { dayOfWeek, restOfDate };
  };

  const dateInfo = formatDate(currentTime);

  return (
    <Card className="w-full aspect-[2] relative overflow-hidden">
      <TVNoise opacity={0.3} intensity={0.2} speed={40} />
      <CardContent
        className={cn(
          "bg-accent/30 flex-1 flex flex-col justify-between",
          "text-sm font-medium uppercase relative z-20",
        )}
      >
        <div className="flex justify-between items-center">
          <span className="opacity-50">{dateInfo.dayOfWeek}</span>
          <div className="flex items-center gap-2 text-xs">
            <span>{dateInfo.restOfDate}</span>
            <span suppressHydrationWarning className="opacity-70">
              {formatTime(currentTime)}
            </span>
          </div>
        </div>
        <div className="text-center space-y-1">
          <div className="text-4xl font-display">
            {balance !== null ? currency.format(balance) : "—"}
          </div>
          <p className="text-xs text-muted-foreground">
            Balance al {asOf ?? "—"}
          </p>
        </div>

        <div className="absolute inset-0 -z-[1]">
          <Image
            src="/assets/pc_blueprint.gif"
            alt="logo"
            width={250}
            height={250}
            className="size-full object-contain"
          />
        </div>
      </CardContent>
    </Card>
  );
}
