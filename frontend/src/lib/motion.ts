/** Motion primitives.
 *
 *  No animation library. Everything here is either a CSS transition triggered by
 *  a mount flag, or one requestAnimationFrame loop for the count-ups that CSS
 *  cannot do. That is ~60 lines against ~50 kB of GSAP, for a product whose
 *  entire motion vocabulary is "a number arrives" and "a bar fills".
 *
 *  Every hook below collapses to its final state under a reduced-motion
 *  preference — not a shorter animation, none at all. Nothing here carries
 *  information that is not also in the text beside it, so there is nothing to
 *  lose by removing it.
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

/** True after the first paint, so a CSS transition has a frame to start from.
 *
 *  Setting a style on first render gives the browser nothing to interpolate:
 *  the element simply appears at its final value. */
export function useMounted(delay = 0): boolean {
  const [on, setOn] = useState(false);
  useEffect(() => {
    const id = window.setTimeout(() => setOn(true), delay);
    return () => window.clearTimeout(id);
  }, [delay]);
  return on;
}

// Deceleration: the figure arrives rather than departs. Per the animation
// guidance, ease-out for entry — not ease-in-out for everything.
const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

/**
 * Count from zero to `target`, in step with the gauge drawing beside it.
 *
 * The number is the accessible representation of these charts, so the element
 * displaying it should carry the final value in an aria-label rather than let a
 * screen reader read a blur of intermediate ones.
 */
export function useCountUp(target: number, duration = 900): number {
  const reduced = usePrefersReducedMotion();
  const [value, setValue] = useState(target);
  const frame = useRef(0);

  useEffect(() => {
    // requestAnimationFrame does not run in a background tab, so a figure that
    // started at zero would still read zero when the reader switched to it.
    // The number is the truth here and the animation is decoration: when the
    // decoration cannot run, show the truth. The same applies mid-flight, which
    // is why the loop settles on hide rather than waiting to be resumed.
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
