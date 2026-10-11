import { useEffect, useRef, useState } from "react";

function formatUsd(value: number): string {
  return value.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });
}

export function CashTicker({ balance }: { balance: number | null }) {
  const previous = useRef<number | null>(null);
  const [direction, setDirection] = useState<"drop" | "rise" | null>(null);

  useEffect(() => {
    if (balance === null) return;
    if (previous.current !== null && balance !== previous.current) {
      setDirection(balance < previous.current ? "drop" : "rise");
      const t = setTimeout(() => setDirection(null), 650);
      previous.current = balance;
      return () => clearTimeout(t);
    }
    previous.current = balance;
  }, [balance]);

  return (
    <div className={`cash-ticker${direction ? ` cash-${direction}` : ""}`} title="Checking account balance">
      <span className="cash-label">Checking</span>
      <span className="cash-value">{balance === null ? "—" : formatUsd(balance)}</span>
    </div>
  );
}
