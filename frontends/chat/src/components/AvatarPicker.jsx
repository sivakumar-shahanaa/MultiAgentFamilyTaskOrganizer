import { useState } from "react";
import { motion } from "framer-motion";
import Blob, { SHAPES } from "./Blob.jsx";

/* "Choose your avatar" — pick the blob shape for this person.
   Color comes from persona identity (accent); shape is self-expression.
   Choice persists in localStorage per person (no backend change needed). */
export default function AvatarPicker({ person, fallbackShape, onDone }) {
  const [shape, setShape] = useState(localStorage.getItem(`avatar:${person.id}`) || fallbackShape || Object.keys(SHAPES)[0]);

  return (
    <div className="min-h-full flex flex-col items-center justify-center gap-8 p-8">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-stone-800">Choose your avatar</h1>
        <p className="text-stone-500 mt-1">
          Express yourself, {person.name} — your color is your identity
        </p>
      </div>

      <Blob color={person.accent} shape={shape} mood="idle" size={150} />

      <div className="grid grid-cols-4 gap-4 max-w-md">
        {Object.keys(SHAPES).map((key) => (
          <motion.button
            key={key}
            whileHover={{ scale: 1.08 }}
            whileTap={{ scale: 0.92 }}
            onClick={() => setShape(key)}
            className="rounded-full p-2.5 transition-shadow"
            style={{
              background: `${person.accent}18`,
              boxShadow: shape === key ? `0 0 0 3px ${person.accent}` : "none",
            }}
          >
            <Blob color={person.accent} shape={key} mood="idle" size={56} />
          </motion.button>
        ))}
      </div>

      <motion.button
        whileTap={{ scale: 0.97 }}
        onClick={() => {
          localStorage.setItem(`avatar:${person.id}`, shape);
          onDone(shape);
        }}
        className="w-72 py-3.5 rounded-full text-white font-semibold text-lg shadow-lg"
        style={{ background: "#1c1917" }}
      >
        Continue
      </motion.button>
    </div>
  );
}
