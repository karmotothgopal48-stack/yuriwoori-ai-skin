"use client";

import { useEffect, useState } from "react";

export function useCountdown(active: boolean, onComplete: () => void) {
  const [count, setCount] = useState<number | null>(null);

  useEffect(() => {
    if (!active) {
      setCount(null);
      return;
    }

    setCount(3);
    const timers: ReturnType<typeof setTimeout>[] = [];
    [1, 2].forEach((n, i) => {
      timers.push(setTimeout(() => setCount(3 - (i + 1)), (i + 1) * 800));
    });
    timers.push(
      setTimeout(() => {
        setCount(null);
        onComplete();
      }, 3 * 800)
    );

    return () => timers.forEach(clearTimeout);
  }, [active, onComplete]);

  return count;
}

export function CountdownDisplay({ count }: { count: number | null }) {
  if (count === null) return null;
  return (
    <div className="absolute bottom-[120px] left-0 right-0 text-center z-10">
      <div className="font-display text-white text-6xl font-medium">{count}</div>
    </div>
  );
}