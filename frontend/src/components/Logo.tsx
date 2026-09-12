/** The mark is the product's own signature element: a quoted passage with a
 *  verdict rule down its left edge. It is what every claim in the app looks
 *  like, reduced to four strokes — a document that has been marked up, rather
 *  than a generic speech bubble or magnifying glass.
 *
 *  The rule is the only coloured element, which is the same rule the interface
 *  follows: colour means judgement. */
export function Logo({ size = 22 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      role="img"
      aria-label="Interview Coach"
      focusable="false"
    >
      {/* the verdict rule */}
      <rect x="1" y="3" width="3" height="18" rx="1.2" fill="var(--strong)" />
      {/* the quoted lines, longest first, trailing off like real text */}
      <rect x="8" y="4.5" width="15" height="2.6" rx="1.3" fill="currentColor" />
      <rect x="8" y="10.7" width="15" height="2.6" rx="1.3" fill="currentColor" />
      <rect x="8" y="16.9" width="9" height="2.6" rx="1.3" fill="currentColor" opacity="0.45" />
    </svg>
  );
}
