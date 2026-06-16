export function createDelayedUpdateQueue<T>(
  applyUpdate: (updater: (value: T) => T) => void,
  delayMs: number,
) {
  const queue: Array<(value: T) => T> = [];
  let isProcessing = false;
  let drainResolve: (() => void) | null = null;

  const flush = () => {
    const next = queue.shift();
    if (!next) {
      isProcessing = false;
      drainResolve?.();
      drainResolve = null;
      return;
    }

    applyUpdate(next);
    window.setTimeout(flush, delayMs);
  };

  return {
    enqueue(updater: (value: T) => T) {
      queue.push(updater);
      if (!isProcessing) {
        isProcessing = true;
        flush();
      }
    },
    waitForDrain() {
      return new Promise<void>((resolve) => {
        if (!isProcessing && queue.length === 0) {
          resolve();
          return;
        }
        drainResolve = resolve;
      });
    },
  };
}
