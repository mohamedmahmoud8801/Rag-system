import { useCallback, useEffect, useState } from "react";

/** Counts down from `seconds`; start() restarts it. Used for "send the code again". */
export function useCountdown(seconds: number, startNow = true) {
  const [left, setLeft] = useState(startNow ? seconds : 0);

  useEffect(() => {
    if (left <= 0) return;
    const id = window.setTimeout(() => setLeft((value) => value - 1), 1000);
    return () => window.clearTimeout(id);
  }, [left]);

  const start = useCallback((from = seconds) => setLeft(from), [seconds]);

  return { left, start };
}
