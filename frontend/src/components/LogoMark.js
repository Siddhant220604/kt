export default function LogoMark({ className = 'h-10 w-10', ...props }) {
  return (
    <svg
      viewBox="0 0 140 140"
      className={className}
      role="img"
      aria-label="Kiran Traders"
      {...props}
    >
      <circle cx="70" cy="70" r="58" fill="#EFE4D6" stroke="#241E19" strokeWidth="2" />
      <g stroke="#241E19" strokeWidth="2">
        <path d="M70 4 L70 12" />
        <path d="M70 128 L70 136" />
        <path d="M128 70 L136 70" />
        <path d="M4 70 L12 70" />
      </g>
      <g stroke="#241E19" strokeWidth="6.5" fill="none" strokeLinecap="butt" strokeLinejoin="miter">
        <path d="M44.25 48 L44.25 76" />
        <path d="M66 48 L47 62 L66 76" />
        <path d="M87 48 L87 76" />
        <path d="M75 51.25 L99 51.25" />
      </g>
      <rect x="46" y="86" width="48" height="6" fill="#F59F0A" />
    </svg>
  );
}
