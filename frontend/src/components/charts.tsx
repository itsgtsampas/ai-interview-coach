/** Data display.
 *
 *  Hand-rolled SVG rather than a charting library: two chart shapes, twenty
 *  lines each, and every library ships a categorical palette that breaks the
 *  house rule. Axes and grid stay achromatic; only the data points carry
 *  colour, because each one is a verdict.
 */

import { useId, useRef, useState } from "react";

import { toneForScore } from "./bits";
import { useCountUp, useMounted, usePrefersReducedMotion } from "../lib/motion";
import { useT } from "../lib/i18n";

/* --- shared geometry ----------------------------------------------------- */

const PAD = { top: 14, right: 14, bottom: 26, left: 30 };

/** The thresholds where the verdict changes, drawn so the y-axis reads as a
 *  legend rather than relying on colour. */
const BANDS = [
  { at: 70, label: "Interview ready" },
  { at: 45, label: "Nearly ready" },
];

export interface TrendPoint {
  /** Identifies the point in the readout. Never drawn on the axis — titles are
   *  long and similar, and truncating three of them to "Meridian La…" labels
   *  nothing. */
  label: string;
  value: number;
  meta?: string;
}

/** Readiness across sessions.
 *
 *  Not rendered below three points: a line through two dots asserts a direction
 *  the data does not support. */
export function Trend({
  points,
  height = 210,
  max = 100,
  caption,
}: {
  points: TrendPoint[];
  height?: number;
  max?: number;
  caption?: string;
}) {
  const [active, setActive] = useState<number | null>(null);
  const titleId = useId();
  const width = 620;
  const reduced = usePrefersReducedMotion();
  const mounted = useMounted(reduced ? 0 : 80);
  // Measured once the path exists, so the dash animation knows how far to travel.
  const path = useRef<SVGPathElement | null>(null);
  const length = path.current?.getTotalLength?.() ?? 1200;

  if (points.length === 0) return null;

  const plotW = width - PAD.left - PAD.right;
  const plotH = height - PAD.top - PAD.bottom;
  const x = (i: number) =>
    PAD.left + (points.length === 1 ? plotW / 2 : (i / (points.length - 1)) * plotW);
  const y = (v: number) => PAD.top + plotH - (Math.min(v, max) / max) * plotH;

  const line = points.map((p, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(p.value)}`).join(" ");
  const area =
    `${line} L ${x(points.length - 1)} ${PAD.top + plotH} L ${x(0)} ${PAD.top + plotH} Z`;

  const first = points[0].value;
  const last = points[points.length - 1].value;
  const summary =
    `Readiness across ${points.length} scored sessions, ` +
    `from ${first} to ${last} out of ${max}.`;

  return (
    <figure className="chart">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="chart__svg"
        role="img"
        aria-labelledby={titleId}
        preserveAspectRatio="xMidYMid meet"
      >
        <title id={titleId}>{summary}</title>

        {/* band thresholds, doubling as the y legend */}
        {BANDS.map((band) => (
          <g key={band.at}>
            <line
              x1={PAD.left} x2={width - PAD.right}
              y1={y(band.at)} y2={y(band.at)}
              className="chart__band"
            />
            <text x={width - PAD.right} y={y(band.at) - 4} className="chart__bandlabel"
                  textAnchor="end">
              {band.label}
            </text>
          </g>
        ))}

        <line x1={PAD.left} x2={PAD.left} y1={PAD.top} y2={PAD.top + plotH}
              className="chart__axis" />
        {[0, max / 2, max].map((tick) => (
          <text key={tick} x={PAD.left - 6} y={y(tick) + 3} className="chart__tick"
                textAnchor="end">
            {tick}
          </text>
        ))}

        <path
          d={area}
          className="chart__area"
          style={{ opacity: reduced || mounted ? undefined : 0 }}
        />
        <path
          ref={path}
          d={line}
          className="chart__line"
          style={
            reduced
              ? undefined
              : {
                  strokeDasharray: length,
                  strokeDashoffset: mounted ? 0 : length,
                }
          }
        />

        {points.map((p, i) => (
          <g key={`${p.label}-${i}`}>
            <circle
              cx={x(i)} cy={y(p.value)} r={active === i ? 6 : 4.5}
              className="chart__dot"
              style={{
                fill: `var(--${toneForScore(p.value, max)})`,
                // Each dot lands as the line reaches it.
                opacity: reduced || mounted ? 1 : 0,
                transitionDelay: reduced ? undefined
                  : `${300 + (i / Math.max(1, points.length - 1)) * 600}ms`,
              }}
            />
            {/* A real hit area; 4.5px of dot is not one. */}
            <circle
              cx={x(i)} cy={y(p.value)} r={16}
              className="chart__hit"
              tabIndex={0}
              role="button"
              aria-label={
                `Session ${i + 1}, ${p.label}: ${p.value} of ${max}` +
                (p.meta ? `, ${p.meta}` : "")
              }
              onMouseEnter={() => setActive(i)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(i)}
              onBlur={() => setActive(null)}
            />
          </g>
        ))}

        {/* The axis is session order, not elapsed time. Identity lives in the
            readout, where there is room for it. */}
        {points.map((_, i) => (
          <text key={`l-${i}`} x={x(i)} y={height - 8} className="chart__xlabel"
                textAnchor="middle">
            {i + 1}
          </text>
        ))}
      </svg>

      {/* Text rather than a tooltip: works on touch, announced without hover. */}
      <p className="chart__readout" role="status" aria-live="polite">
        {active !== null ? (
          <>
            <span className="chart__n label">{active + 1}</span>
            <strong>{points[active].label}</strong>
            <span className="num" style={{ color: `var(--${toneForScore(points[active].value, max)})` }}>
              {points[active].value}
            </span>
            {points[active].meta ? <span className="hint">{points[active].meta}</span> : null}
          </>
        ) : (
          <span className="hint">{caption ?? "Hover or tab through a point for its score."}</span>
        )}
      </p>
    </figure>
  );
}

/** A line small enough for a table row: shape only, no axes or interaction. */
export function Sparkline({ values, max = 5 }: { values: number[]; max?: number }) {
  const reduced = usePrefersReducedMotion();
  const mounted = useMounted(reduced ? 0 : 200);
  if (values.length < 2) return null;
  const w = 68;
  const h = 20;
  const step = w / (values.length - 1);
  const y = (v: number) => h - 2 - (Math.min(v, max) / max) * (h - 4);
  const d = values.map((v, i) => `${i === 0 ? "M" : "L"} ${i * step} ${y(v)}`).join(" ");

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="spark" aria-hidden="true">
      <path
        d={d}
        className="spark__line"
        style={reduced ? undefined : { strokeDasharray: 200, strokeDashoffset: mounted ? 0 : 200 }}
      />
      <circle cx={w} cy={y(values[values.length - 1])} r="2.5"
              style={{ fill: `var(--${toneForScore(values[values.length - 1], max)})` }} />
    </svg>
  );
}

/** A headline figure. `tone` is opt-in: a count is not a judgement. */
export function Stat({
  label, value, suffix, tone, note, decimals = 0,
}: {
  label: string;
  value: string | number;
  suffix?: string;
  tone?: string;
  note?: string;
  /** Numeric values count up; strings are shown as given. */
  decimals?: number;
}) {
  const numeric = typeof value === "number";
  const counted = useCountUp(numeric ? (value as number) : 0);
  const shown = numeric ? counted.toFixed(decimals) : value;

  return (
    <div className="stat">
      <span className="label">{label}</span>
      {/* The final value is what a screen reader should hear, not the blur of
          intermediate ones the animation produces. */}
      <p
        className="stat__v num"
        style={tone ? { color: `var(--${tone})` } : undefined}
        aria-label={numeric ? `${value}${suffix ?? ""}` : undefined}
      >
        <span aria-hidden={numeric || undefined}>{shown}</span>
        {suffix ? <span className="stat__suffix" aria-hidden="true">{suffix}</span> : null}
      </p>
      {note ? <span className="hint stat__note">{note}</span> : null}
    </div>
  );
}

/** A change, carrying direction as a glyph as well as a colour. */
export function Delta({ value, suffix = "" }: { value: number; suffix?: string }) {
  if (value === 0) {
    return <span className="delta" data-dir="flat">No change</span>;
  }
  const up = value > 0;
  return (
    <span className="delta" data-dir={up ? "up" : "down"}>
      <svg width="9" height="9" viewBox="0 0 9 9" aria-hidden="true">
        <path d={up ? "M4.5 0 L9 7 L0 7 Z" : "M4.5 9 L0 2 L9 2 Z"} fill="currentColor" />
      </svg>
      {up ? "+" : ""}{value}{suffix}
    </span>
  );
}

/** The same numbers as a table, collapsed so it does not compete with the chart. */
export function DataTable({
  caption, columns, rows,
}: {
  caption: string;
  columns: string[];
  rows: (string | number)[][];
}) {
  const { t } = useT();
  return (
    <details className="disclose datatable">
      <summary>{t("progress.showNumbers")}</summary>
      <div className="datatable__scroll">
        <table className="table">
          <caption className="hint">{caption}</caption>
          <thead>
            <tr>{columns.map((c) => <th key={c} scope="col">{c}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                {row.map((cell, j) => (
                  j === 0 ? <th key={j} scope="row">{cell}</th> : <td key={j}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
