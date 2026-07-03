export function Logo({ size = 36 }: { size?: number }) {
  // The MODA mark: a thin line-drawn M, as in the wireframes.
  return (
    <svg width={size} height={size * 0.72} viewBox="0 0 50 36" fill="none" aria-label="MODA" role="img">
      <path
        d="M2 34 L14 2 L25 26 L36 2 L48 34"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
