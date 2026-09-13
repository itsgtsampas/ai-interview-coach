/** Motion primitives: CSS transitions plus one rAF loop for the count-ups.
 *
 *  Every hook collapses to its final state under reduced motion — none of this
 *  carries information the text beside it does not.
 */

import { useEffect, useRef, useState } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => typeof window !== "undefined" && window.matchMedia(QUERY).matches,
  );

  useEffect(() => {
    const mq = window.matchMedia(QUERY);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  return reduced;
}

/** True after the first paint, so a CSS transition has a frame to start from. */
export function useMounted(delay = 0): boolean {
  const [on, setOn] = useState(false);
  useEffect(() => {
    const id = window.setTimeout(() => setOn(true), delay);
    return () => window.clearTimeout(id);
  }, [delay]);
  return on;
}

// Ease-out: the figure arrives rather than departs.
const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

/** Count from zero to `target`, in step with the gauge beside it.
 *
 *  Callers should put the final value in an aria-label — a screen reader should
 *  not read the intermediate ones. */
export function useCountUp(target: number, duration = 900): number {
  const reduced = usePrefersReducedMotion();
  const [value, setValue] = useState(target);
  const frame = useRef(0);

  useEffect(() => {
    // rAF does not run in a background tab, so an animation started there would
    // still read zero when the reader arrives. Show the value instead.
    if (reduced || document.hidden) {
      setValue(target);
      return;
    }

    const started = performance.now();
    setValue(0);

    const settle = () => {
      cancelAnimationFrame(frame.current);
      setValue(target);
    };
    const onHide = () => document.hidden && settle();

    const tick = (now: number) => {
      const t = Math.min(1, (now - started) / duration);
      setValue(target * easeOut(t));
      if (t < 1) frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    document.addEventListener("visibilitychange", onHide);

    return () => {
      cancelAnimationFrame(frame.current);
      document.removeEventListener("visibilitychange", onHide);
    };
  }, [target, duration, reduced]);

  return value;
}
