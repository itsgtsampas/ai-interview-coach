/** Score display.
 *
 *  A readiness score is a single KPI against thresholds, which is the one case
 *  a gauge is the right chart rather than an ornament. The thresholds are drawn
 *  and *labelled* on the dial: the guidance for this chart type is explicit that
 *  colour zones alone are not sufficient, and it is also just the honest thing —
 *  the reader can see that 56 sits in "nearly", without decoding an amber.
 *
 *  The house rule still holds. The dial track, the ticks and the labels are
 *  achromatic; the only coloured element is the value arc, which is a verdict.
 */

import { useId } from "react";

import { toneForScore } from "./bits";
import { useCountUp, useMounted, usePrefersReducedMotion } from "../lib/motion";

/** The two points where the verdict changes, as fractions of the scale. */
const THRESHOLDS = [
  { at: 45, label: "Nearly" },
  { at: 70, label: "Ready" },
];

// A 270° dial with the gap at the bottom, where a needle would be least useful.
const SWEEP = 270;
const START = 135;

function polar(cx: number, cy: number, r: number, deg: number) {
  const rad = (deg * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

export function ArcGauge({
  value,
  max = 100,
  size = 176,
  band,
  caption,
  suffix,
}: {
  value: number;
  max?: number;
  size?: number;
  /** The verdict in words — "Nearly ready". Shown under the figure. */
  band?: string;
  /** What the number measures, when that is not obvious from context. */
  caption?: string;
  suffix?: string;
}) {
  const reduced = usePrefersReducedMotion();
  const mounted = useMounted(60);
  const shown = useCountUp(value);
  const labelId = useId();

  const stroke = 11;
  const r = (size - stroke) / 2 - 9; // room for the tick labels outside the dial
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * r;
  const track = circumference * (SWEEP / 360);
  const pct = Math.max(0, Math.min(1, value / max));
  const tone = toneForScore(value, max);

  // Before mount the arc is empty, so the transition has somewhere to travel
  // from. Under reduced motion it is drawn at its final length immediately.
  const drawn = reduced || mounted ? track * pct : 0;

  return (
    <figure className="arc" role="img" aria-labelledby={labelId}>
      <figcaption id={labelId} className="visually-hidden">
        {`${Math.round(value)} out of ${max}${band ? `, ${band}` : ""}`}
      </figcaption>

      {/* The dial is a fixed square; the labels below it flow, so a long band
          name wraps instead of escaping the figure and landing on whatever
          follows it. */}
      <div className="arc__dial" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <g transform={`rotate(${START} ${cx} ${cy})`}>
          <circle
            cx={cx} cy={cy} r={r}
            className="arc__track"
            strokeWidth={stroke}
            strokeDasharray={`${track} ${circumference}`}
            strokeLinecap="round"
          />
          <circle
            cx={cx} cy={cy} r={r}
            className="arc__value"
            stroke={`var(--${tone})`}
            strokeWidth={stroke}
            strokeDasharray={`${drawn} ${circumference}`}
            strokeLinecap="round"
          />
        </g>

        {/* Threshold ticks, drawn across the band so they read as divisions of
            the dial rather than as marks sitting on top of it. */}
        {THRESHOLDS.map((t) => {
          const deg = START + SWEEP * (t.at / max);
          const inner = polar(cx, cy, r - stroke / 2 - 1, deg);
          const outer = polar(cx, cy, r + stroke / 2 + 1, deg);
          const text = polar(cx, cy, r + stroke / 2 + 9, deg);
          return (
            <g key={t.at}>
              <line
                x1={inner.x} y1={inner.y} x2={outer.x} y2={outer.y}
                className="arc__tick"
              />
              <text
                x={text.x} y={text.y}
                className="arc__ticklabel"
                textAnchor={text.x < cx ? "end" : "start"}
                dominantBaseline="middle"
              >
                {t.label}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="arc__mid">
        <span className="num arc__v" style={{ color: `var(--${tone})` }}>
          {Math.round(shown)}
        </span>
        <span className="arc__d">{suffix ?? `/ ${max}`}</span>
      </div>
      </div>

      {band ? <span className="arc__band label">{band}</span> : null}
      {caption ? <span className="arc__cap hint">{caption}</span> : null}
    </figure>
  );
}

/**
 * A labelled bar with an optional benchmark marker — a bullet chart, which is
 * the compact form of "value against a target" and the right shape for a column
 * of competencies.
 *
 * `index` staggers the fill so the column reads top to bottom on arrival
 * instead of snapping in as a block.
 */
export function BulletBar({
  label,
  value,
  max = 5,
  benchmark,
  index = 0,
}: {
  label: string;
  value: number;
  max?: number;
  /** Where "good enough" sits on this scale. Drawn as a marker, labelled once
   *  in the caption beside the group rather than repeated on every row. */
  benchmark?: number;
  index?: number;
}) {
  const reduced = usePrefersReducedMotion();
  const mounted = useMounted(reduced ? 0 : 80 + index * 70);
  const tone = toneForScore(value, max);
  const pct = Math.max(0, Math.min(1, value / max));

  return (
    <div className="bullet">
      <div className="bullet__top">
        <span className="bullet__name">{label}</span>
        <span className="bullet__val num" style={{ color: `var(--${tone})` }}>
          {value.toFixed(1)}
          <span className="bullet__max"> / {max}</span>
        </span>
      </div>
      <div
        className="bullet__track"
        role="meter"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-label={`${label}: ${value.toFixed(1)} out of ${max}`}
      >
        {/* Scaled, not resized: animating width lays out the page on every
            frame. The clip keeps the rounded ends from stretching with it. */}
        <span className="bullet__clip">
          <span
            className="bullet__fill"
            style={{
              transform: `scaleX(${reduced || mounted ? pct : 0})`,
              background: `var(--${tone})`,
            }}
          />
        </span>
        {benchmark !== undefined ? (
          <span
            className="bullet__mark"
            style={{ left: `${(benchmark / max) * 100}%` }}
            aria-hidden="true"
          />
        ) : null}
      </div>
    </div>
  );
}

/**
 * Linear progress through a fixed sequence — how far this application has got.
 *
 * Linear easing, deliberately: this is steady progress through discrete steps,
 * not an element arriving on screen, and the guidance is to let those differ.
 */
export function StepProgress({
  done,
  total,
  label,
}: {
  done: number;
  total: number;
  label?: string;
}) {
  const reduced = usePrefersReducedMotion();
  const mounted = useMounted(reduced ? 0 : 120);
  const pct = total ? done / total : 0;

  return (
    <div className="stepbar">
      <div className="stepbar__track" aria-hidden="true">
        {Array.from({ length: total }, (_, i) => (
          <span key={i} className="stepbar__seg" data-on={i < done} />
        ))}
        <span
          className="stepbar__sweep"
          style={{ transform: `scaleX(${reduced || mounted ? pct : 0})` }}
        />
      </div>
      <span className="hint stepbar__label">
        {label ?? `${done} of ${total} stages`}
      </span>
    </div>
  );
}
