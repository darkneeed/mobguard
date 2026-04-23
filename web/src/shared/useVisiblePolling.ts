import { useEffect, useRef } from "react";

export function useVisiblePolling(
  enabled: boolean,
  callback: () => void | Promise<void>,
  intervalMs: number,
  deps: ReadonlyArray<unknown> = []
): void {
  const callbackRef = useRef(callback);

  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!enabled) {
      return undefined;
    }

    let intervalId: number | null = null;

    const run = () => {
      void callbackRef.current();
    };

    const stop = () => {
      if (intervalId !== null) {
        window.clearInterval(intervalId);
        intervalId = null;
      }
    };

    const start = () => {
      if (typeof document !== "undefined" && document.hidden) {
        return;
      }
      if (intervalId === null) {
        intervalId = window.setInterval(run, intervalMs);
      }
    };

    const onVisibilityChange = () => {
      if (document.hidden) {
        stop();
        return;
      }
      run();
      start();
    };

    run();
    start();
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [enabled, intervalMs, ...deps]);
}
