import { useId } from "react";
import { PRODUCT_NAME } from "./brand";

export function Logo({ className = "logo", alive = false }: { className?: string; alive?: boolean }) {
  const uid = useId().replace(/:/g, "");
  const metal = `ommMetal-${uid}`;
  const svg = (
    <svg className={className} viewBox="40 70 380 380" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id={metal} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#8E939D">
            {alive ? <animate attributeName="stop-color" values="#8E939D;#D4D7DF;#5A5E67;#8E939D" dur="5s" repeatCount="indefinite" /> : null}
          </stop>
          <stop offset="35%" stopColor="#D4D7DF">
            {alive ? <animate attributeName="stop-color" values="#D4D7DF;#8E939D;#2C3036;#D4D7DF" dur="5s" repeatCount="indefinite" /> : null}
          </stop>
          <stop offset="65%" stopColor="#5A5E67">
            {alive ? <animate attributeName="stop-color" values="#5A5E67;#D4D7DF;#8E939D;#5A5E67" dur="5s" repeatCount="indefinite" /> : null}
          </stop>
          <stop offset="100%" stopColor="#2C3036">
            {alive ? <animate attributeName="stop-color" values="#2C3036;#8E939D;#D4D7DF;#2C3036" dur="5s" repeatCount="indefinite" /> : null}
          </stop>
          {alive ? (
            <animateTransform
              attributeName="gradientTransform"
              type="rotate"
              from="0 0.5 0.5"
              to="360 0.5 0.5"
              dur="9s"
              repeatCount="indefinite"
            />
          ) : null}
        </linearGradient>
      </defs>
      <g className={alive ? "logo-volume" : undefined}>
        <path
          className={alive ? "logo-track logo-track-a" : undefined}
          d="M 250, 100 C 350, 100 400, 200 350, 300 C 300, 400 150, 420 100, 320 C 50, 220 150, 100 250, 100 Z"
          stroke={`url(#${metal})`}
          strokeWidth="14"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          className={alive ? "logo-track logo-track-b" : undefined}
          d="M 200, 150 C 100, 150 80, 280 160, 360 C 240, 440 380, 360 360, 220 C 340, 100 250, 120 200, 150 Z"
          stroke={`url(#${metal})`}
          strokeWidth="14"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <polygon
          className={alive ? "logo-arrow" : undefined}
          points="230,85 270,105 230,125"
          fill={`url(#${metal})`}
          transform="rotate(-25 250 105)"
        />
        <circle className={alive ? "logo-dot d1" : undefined} cx="250" cy="100" r="12" fill={`url(#${metal})`} stroke="#FFFFFF" strokeWidth="3" />
        <circle className={alive ? "logo-dot d2" : undefined} cx="350" cy="300" r="10" fill={`url(#${metal})`} stroke="#FFFFFF" strokeWidth="3" />
        <circle className={alive ? "logo-dot d3" : undefined} cx="100" cy="320" r="10" fill={`url(#${metal})`} stroke="#FFFFFF" strokeWidth="3" />
        <circle className={alive ? "logo-dot d4" : undefined} cx="160" cy="360" r="14" fill={`url(#${metal})`} stroke="#FFFFFF" strokeWidth="3" />
        <circle className={alive ? "logo-dot d5" : undefined} cx="360" cy="220" r="12" fill={`url(#${metal})`} stroke="#FFFFFF" strokeWidth="3" />
        <circle className={alive ? "logo-dot d6" : undefined} cx="200" cy="150" r="10" fill={`url(#${metal})`} stroke="#FFFFFF" strokeWidth="3" />
      </g>
    </svg>
  );
  if (!alive) return svg;
  return (
    <div className="logo-alive-stage">
      <div className="logo-alive-spin">{svg}</div>
    </div>
  );
}

export function BrandLockup({ large = false }: { large?: boolean }) {
  return (
    <span className={large ? "brand-lockup large" : "brand-lockup"}>
      <Logo />
      <span className="brand-name">{PRODUCT_NAME}</span>
    </span>
  );
}
