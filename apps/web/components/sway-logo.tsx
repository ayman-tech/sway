export function SwayLogo({ size = 28 }: { size?: number }) {
  // eslint-disable-next-line @next/next/no-img-element
  return <img src="/icons/sway-mark.svg" alt="" aria-hidden="true" width={size} height={size} className="shrink-0" />;
}
