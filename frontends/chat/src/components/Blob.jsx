import { useId } from "react";
import { motion } from "framer-motion";

/*
 * Flat cartoon avatar — big googly eyes, thin smile, solid-color silhouette.
 *
 * Eye mechanics (the important part):
 *  - GAZE: pupils (not the eyeball) wander left/right on a slow loop, plus a
 *    per-mood offset (thinking looks up-away, listening looks at you, etc).
 *  - BLINK: each eye squashes around its OWN center (transformBox fill-box),
 *    quick and infrequent — a lid closing, not a flip.
 *
 * mood: idle | listening | thinking | speaking | allow | deny | escalate
 * shape: key of SHAPES ; color: persona accent hex
 */

function burstPoints(cx, cy, spikes, outer, inner, rot = -90) {
  const pts = [];
  for (let i = 0; i < spikes * 2; i++) {
    const r = i % 2 === 0 ? outer : inner;
    const a = (Math.PI * (i / spikes)) + (rot * Math.PI) / 180;
    pts.push(`${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`);
  }
  return pts.join(" ");
}

const petals8 = Array.from({ length: 8 }, (_, i) => i * 45);

/* Each shape: render(color) -> silhouette, face: {x,y} offset so the face
   sits on the shape's visual mass (U's bend, snowman's belly, cone's base). */
export const SHAPES = {
  clover: {
    face: { x: 0, y: 0 },
    render: (c) => (
      <g fill={c}>
        <circle cx="50" cy="27" r="21" /><circle cx="27" cy="50" r="21" />
        <circle cx="73" cy="50" r="21" /><circle cx="50" cy="73" r="21" />
        <circle cx="50" cy="50" r="24" />
      </g>
    ),
  },
  cloud: {
    face: { x: 0, y: 2 },
    render: (c) => (
      <g fill={c}>
        <circle cx="30" cy="58" r="19" /><circle cx="52" cy="42" r="24" />
        <circle cx="73" cy="58" r="17" /><ellipse cx="51" cy="66" rx="30" ry="15" />
      </g>
    ),
  },
  flower: {
    face: { x: 0, y: 0 },
    render: (c) => (
      <g fill={c}>
        {petals8.map((deg) => (
          <ellipse key={deg} cx="50" cy="24" rx="13" ry="17" transform={`rotate(${deg} 50 50)`} />
        ))}
        <circle cx="50" cy="50" r="26" />
      </g>
    ),
  },
  burst: {
    face: { x: 0, y: 0 },
    render: (c) => (
      <g fill={c}>
        <polygon points={burstPoints(50, 50, 12, 47, 33)} />
        <circle cx="50" cy="50" r="33" />
      </g>
    ),
  },
  star: {
    face: { x: 0, y: 2 },
    render: (c) => (
      <g fill={c}>
        <polygon points={burstPoints(50, 52, 6, 45, 24, -90)} />
        <circle cx="50" cy="52" r="25" />
      </g>
    ),
  },
  bubble: {
    face: { x: 0, y: -2 },
    render: (c) => (
      <g fill={c}>
        <circle cx="32" cy="50" r="17" /><circle cx="52" cy="38" r="21" />
        <circle cx="70" cy="52" r="15" /><ellipse cx="51" cy="56" rx="27" ry="14" />
        <polygon points="36,66 26,86 54,68" />
      </g>
    ),
  },
  drop: {
    face: { x: 0, y: 6 },
    render: (c) => (
      <g fill={c}>
        <path d="M 50 10 Q 55 24 68 42 Q 80 60 70 74 Q 58 88 40 82 Q 20 74 24 54 Q 28 38 38 28 Q 46 18 47 12 Q 49 8 50 10 Z" />
      </g>
    ),
  },
  ushape: {
    face: { x: 0, y: 12 },
    render: (c) => (
      <g fill="none" stroke={c} strokeWidth="18" strokeLinecap="round">
        <path d="M 30 22 L 30 48 A 20 20 0 0 0 70 48 L 70 22" />
      </g>
    ),
  },
  ghost: {
    face: { x: 0, y: -4 },
    render: (c) => (
      <g fill={c}>
        <path d="M 27 48 A 23 23 0 0 1 73 48 L 73 60 Q 74 74 63 67 Q 57 63 53 70 Q 50 76 46 70 Q 42 63 36 67 Q 26 74 27 60 Z" />
      </g>
    ),
  },
  duo: {
    face: { x: -2, y: 8 },
    render: (c) => (
      <g fill={c}>
        <circle cx="58" cy="28" r="15" />
        <circle cx="46" cy="58" r="25" />
      </g>
    ),
  },
  bowtie: {
    face: { x: 0, y: 0 },
    render: (c) => (
      <g fill={c}>
        <path d="M 15 30 Q 14 22 23 25 L 46 43 Q 50 46 50 50 Q 50 54 46 57 L 23 75 Q 14 78 15 70 Z" />
        <path d="M 85 30 Q 86 22 77 25 L 54 43 Q 50 46 50 50 Q 50 54 54 57 L 77 75 Q 86 78 85 70 Z" />
        <circle cx="50" cy="50" r="13" />
      </g>
    ),
  },
  cube: {
    face: { x: 0, y: 0 },
    render: (c) => (
      <g fill={c}>
        <rect x="25" y="25" width="50" height="50" rx="13" transform="rotate(4 50 50)" />
      </g>
    ),
  },
  cone: {
    face: { x: 0, y: 10 },
    render: (c) => (
      <g fill={c}>
        <path d="M 45 14 Q 50 6 55 14 L 77 64 Q 82 76 69 76 L 31 76 Q 18 76 23 64 Z" />
      </g>
    ),
  },
  bean: {
    face: { x: -2, y: 2 },
    render: (c) => (
      <g fill={c}>
        <path d="M 30 22 Q 52 12 66 28 Q 76 40 64 50 Q 55 57 61 66 Q 66 78 50 80 Q 26 82 20 58 Q 16 36 30 22 Z" />
      </g>
    ),
  },
};

/* Deterministic default shape per person id — so a fresh household already
   shows silhouette variety before anyone opens the picker. */
export function defaultShape(id) {
  const keys = Object.keys(SHAPES);
  let h = 0;
  for (const ch of String(id)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return keys[h % keys.length];
}

/* body motion per mood — listening BLOBS (asynchronous squash/stretch loop),
   speaking bobs, verdicts burst. */
const BODY = {
  idle:      { anim: { scale: 1, rotate: 0, x: 0, y: 0 }, t: { type: "spring", stiffness: 260, damping: 14 } },
  listening: {
    anim: {
      scaleX: [1, 1.17, 0.86, 1.12, 0.9, 1],
      scaleY: [1, 0.85, 1.16, 0.9, 1.12, 1],
      rotate: [0, 4, -3.5, 2.5, -2, 0],
      y: [0, -5, 2, -4, 1, 0],
    },
    t: { duration: 1.6, repeat: Infinity, ease: "easeInOut" },
  },
  thinking:  { anim: { scale: 0.97, rotate: [-4, -6, -4], y: 2 }, t: { rotate: { duration: 2.4, repeat: Infinity, ease: "easeInOut" }, type: "spring", stiffness: 260, damping: 14 } },
  speaking:  { anim: { y: [0, -4, 0, -2, 0], rotate: [0, 1.5, 0, -1.5, 0], scale: 1.02 }, t: { duration: 1.1, repeat: Infinity } },
  allow:     { anim: { scale: [1, 1.18, 1], y: [0, -15, 0], rotate: [0, 4, 0] }, t: { duration: 0.7 } },
  deny:      { anim: { x: [0, -9, 9, -7, 7, -3, 3, 0], scale: 0.97 }, t: { duration: 0.6 } },
  escalate:  { anim: { rotate: [0, -9, -9, 0], y: [0, -5, -5, 0] }, t: { duration: 1.4 } },
};

/* pupil mood-offset + mouth */
const FACE = {
  idle:      { look: { x: 0, y: 0 },   mouth: "M 41 64 Q 50 71 59 64" },
  listening: { look: { x: 0, y: 2.5 }, mouth: "M 42 63 Q 50 70 58 63" },
  thinking:  { look: { x: 3.5, y: -4 }, mouth: "M 45 66 Q 50 63 55 66" },
  speaking:  { look: { x: 0, y: 0 },   mouth: "M 42 62 Q 50 74 58 62" },
  allow:     { look: { x: 0, y: 0 },   mouth: "M 38 61 Q 50 76 62 61" },
  deny:      { look: { x: 0, y: 3 },   mouth: "M 42 69 Q 50 62 58 69" },
  escalate:  { look: { x: -3.5, y: -3 }, mouth: "M 44 66 Q 50 68 56 64" },
};

function Eye({ cx, look, wander, blinkDelay }) {
  return (
    // blink squashes THIS eye around its own center — a lid, not a flip
    <motion.g
      style={{ transformBox: "fill-box", transformOrigin: "center" }}
      animate={{ scaleY: [1, 1, 0.12, 1, 1] }}
      transition={{ duration: 5.2, times: [0, 0.9, 0.94, 0.98, 1], repeat: Infinity, delay: blinkDelay }}
    >
      <circle cx={cx} cy="47" r="9.5" fill="#fff" />
      {/* saccade: mood look + slow left/right wander — pupils only */}
      <motion.g animate={{ x: look.x, y: look.y }} transition={{ duration: 0.3 }}>
        <motion.circle
          cx={cx} cy="48" r="4.7" fill="#221d1d"
          animate={wander ? { x: [0, -3, -3, 0, 3, 3, 0] } : { x: 0 }}
          transition={{ duration: 7.5, repeat: Infinity, ease: "easeInOut" }}
        />
      </motion.g>
    </motion.g>
  );
}

export default function Blob({ color = "#d97706", shape = "clover", mood = "idle", size = 160 }) {
  const def = SHAPES[shape] ?? SHAPES.clover;
  const body = BODY[mood] ?? BODY.idle;
  const face = FACE[mood] ?? FACE.idle;
  const wander = mood === "idle" || mood === "speaking" || mood === "listening";
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");

  return (
    <motion.div animate={body.anim} transition={body.t} style={{ width: size, height: size }}>
      <motion.svg
        viewBox="0 0 100 100"
        style={{ width: "100%", height: "100%", overflow: "visible" }}
        animate={{ scaleX: [1, 1.035, 0.98, 1], scaleY: [1, 0.965, 1.035, 1] }}
        transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
      >
        {/* goo: heavy blur + alpha-sharpen fuses everything inside like liquid */}
        <defs>
          <filter id={`goo-${uid}`} x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="2.6" result="blur" />
            <feColorMatrix in="blur" mode="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 22 -10" result="goo" />
            <feComposite in="SourceGraphic" in2="goo" operator="atop" />
          </filter>
        </defs>
        <motion.g
          filter={`url(#goo-${uid})`}
          animate={{ skewX: [0, 2, -2, 0] }}
          transition={{ duration: 4.2, repeat: Infinity, ease: "easeInOut" }}
        >
          {def.render(color)}
        </motion.g>

        <g transform={`translate(${def.face.x} ${def.face.y})`}>
          {mood === "allow" ? (
            <g stroke="#221d1d" strokeWidth="3.4" strokeLinecap="round" fill="none">
              <path d="M 33 47 Q 40 41 47 47" />
              <path d="M 53 47 Q 60 41 67 47" />
            </g>
          ) : (
            <>
              <Eye cx="40" look={face.look} wander={wander} blinkDelay={0} />
              <Eye cx="60" look={face.look} wander={wander} blinkDelay={0.04} />
            </>
          )}
          <path d={face.mouth} fill="none" stroke="#221d1d" strokeWidth="3.4" strokeLinecap="round" />
          {mood === "speaking" && (
            <motion.ellipse
              cx="50" cy="67" fill="#221d1d"
              animate={{ rx: [3.5, 7, 4.5, 8, 3.5], ry: [2, 4.5, 3, 5, 2] }}
              transition={{ duration: 0.9, repeat: Infinity }}
            />
          )}
        </g>
      </motion.svg>

      {mood === "thinking" && (
        <div style={{ position: "relative" }}>
          <div style={{ position: "absolute", top: -size - 6, right: -4, display: "flex", gap: 4 }}>
            {[0, 1, 2].map((i) => (
              <motion.div key={i}
                animate={{ y: [0, -7, 0], opacity: [0.35, 1, 0.35] }}
                transition={{ duration: 1, repeat: Infinity, delay: i * 0.18 }}
                style={{ width: 8 + i * 2, height: 8 + i * 2, borderRadius: "50%", background: color, opacity: 0.6 }}
              />
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}
