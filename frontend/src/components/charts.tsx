/** Data display.
 *
 *  Hand-rolled SVG rather than a charting library: there are two chart shapes in
 *  this product and both are twenty lines, where Recharts is ~90kB of bundle and
 *  a second design system to override. More importantly, the house rule —
 *  colour means judgement — has to hold inside the charts too, and every library
 *  ships a categorical palette that breaks it on the first render.
 *
 *  So: the line, the axes and the grid are achromatic. The only coloured marks
 *  are the data points themselves, because each one *is* a verdict about the
 *  candidate, coloured on the same three-step scale as every verdict elsewhere.
 */

import { useId, useState } from "react";

import { toneForScore } from "./bits";

/* --- shared geometry ----------------------------------------------------- */

const PAD = { top: 14, right: 14, bottom: 26, left: 30 };

/** The two thresholds where the readiness verdict changes. Drawing them turns
 *  the y-axis into a legend: the reader can see which band a point sits in
 *  without decoding the colour. */
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

/**
 * Readiness across sessions.
 *
 * Deliberately not rendered below three points: a line through two dots asserts
 * a direction the data does not support. The caller shows figures instead.
 */
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

        <path d={area} className="chart__area" />
        <path d={line} className="chart__line" />

        {points.map((p, i) => (
          <g key={`${p.label}-${i}`}>
            <circle
              cx={x(i)} cy={y(p.value)} r={active === i ? 6 : 4.5}
              className="chart__dot"
              style={{ fill: `var(--${toneForScore(p.value, max)})` }}
            />
            {/* A generous transparent target: 4.5px of dot is not a hit area. */}
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

        {/* The axis is session order, not elapsed time: points are evenly
            spaced whether they were a day or a month apart, so numbering them
            states what is actually being plotted. The identity of each point
            lives in the readout, where there is room for it. */}
        {points.map((_, i) => (
          <text key={`l-${i}`} x={x(i)} y={height - 8} className="chart__xlabel"
                textAnchor="middle">
            {i + 1}
          </text>
        ))}
      </svg>

      {/* The value readout is text, not a floating tooltip: it stays in one
          place, works on touch, and is announced without a hover event. */}
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

/** A line small enough to sit inside a table row. No axes, no interaction —
 *  it carries shape only, and the figures beside it carry the values. */
export function Sparkline({ values, max = 5 }: { values: number[]; max?: number }) {
  if (values.length < 2) return null;
  const w = 68;
  const h = 20;
  const step = w / (values.length - 1);
  const y = (v: number) => h - 2 - (Math.min(v, max) / max) * (h - 4);
  const d = values.map((v, i) => `${i === 0 ? "M" : "L"} ${i * step} ${y(v)}`).join(" ");

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="spark" aria-hidden="true">
      <path d={d} className="spark__line" />
      <circle cx={w} cy={y(values[values.length - 1])} r="2.5"
              style={{ fill: `var(--${toneForScore(values[values.length - 1], max)})` }} />
    </svg>
  );
}

/** A headline figure. `tone` is opt-in: most stats are counts, and a count is
 *  not a judgement, so it stays achromatic. */
export function Stat({
  label, value, suffix, tone, note,
}: {
  label: string;
  value: string | number;
  suffix?: string;
  tone?: string;
  note?: string;
}) {
  return (
    <div className="stat">
      <span className="label">{label}</span>
      <p className="stat__v num" style={tone ? { color: `var(--${tone})` } : undefined}>
        {value}
        {suffix ? <span className="stat__suffix">{suffix}</span> : null}
      </p>
      {note ? <span className="hint stat__note">{note}</span> : null}
    </div>
  );
}

/** A change, carrying its direction as a glyph as well as a colour — the same
 *  reason the charts label their bands: colour alone is not a channel everyone
 *  receives. */
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

/** The readiness score as a ring.
 *
 *  A ring rather than a bar because this number is the page's subject, not one
 *  row in a comparison — and because a full circle makes "out of 100" legible
 *  without a second axis. */
export function Ring({
  value, max = 100, size = 132, label,
}: { value: number; max?: number; size?: number; label?: string }) {
  const stroke = 9;
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const filled = (Math.min(value, max) / max) * circumference;
  const tone = toneForScore(value, max);

  return (
    <div className="ring" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke="var(--rule)" strokeWidth={stroke}
        />
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke={`var(--${tone})`} strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          className="ring__fill"
        />
      </svg>
      <div className="ring__mid">
        <span className="num ring__v" style={{ color: `var(--${tone})` }}>{value}</span>
        <span className="ring__d">/ {max}</span>
      </div>
      {label ? <span className="ring__label label">{label}</span> : null}
    </div>
  );
}

/** The accessible fallback every chart on this page shares: the same numbers as
 *  a real table, collapsed by default so it does not compete with the graphic. */
export function DataTable({
  caption, columns, rows,
}: {
  caption: string;
  columns: string[];
  rows: (string | number)[][];
}) {
  return (
    <details className="disclose datatable">
      <summary>Show the numbers</summary>
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
