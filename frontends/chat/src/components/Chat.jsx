import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import Blob from "./Blob.jsx";

const CHIP = {
  allow:    { label: "allowed",  icon: "✓", cls: "bg-emerald-100 text-emerald-700" },
  deny:     { label: "denied",   icon: "✗", cls: "bg-rose-100 text-rose-700" },
  escalate: { label: "asking a parent", icon: "⤴", cls: "bg-amber-100 text-amber-700" },
};

/* One person's chat window: blob avatar on top emoting with the pipeline,
   messages below, decision chips on assistant turns that carried an action. */
export default function Chat({ person, shape, compact = false }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [mood, setMood] = useState("idle");
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const recorder = useRef(null);
  const scroller = useRef(null);
  const moodTimer = useRef(null);

  /* Mic: record -> POST /api/transcribe (local Whisper on the house server,
     zero egress) -> transcript lands in the input for review/send.
     Requires a secure context (the HTTPS tunnel or localhost). */
  async function toggleMic() {
    if (recording) {
      recorder.current?.stop();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/mp4";
      const rec = new MediaRecorder(stream, { mimeType: mime });
      const chunks = [];
      rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setRecording(false);
        setTranscribing(true);
        setMood("thinking");
        try {
          const fd = new FormData();
          fd.append("audio", new Blob(chunks, { type: mime }), mime.includes("mp4") ? "clip.mp4" : "clip.webm");
          const res = await fetch("/api/transcribe", { method: "POST", body: fd });
          if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
          const d = await res.json();
          if (d.text) {
            setInput((prev) => (prev ? prev + " " : "") + d.text);
            setMood("listening");
          } else {
            setMood("idle");
          }
        } catch {
          setMood("idle");
        } finally {
          setTranscribing(false);
        }
      };
      rec.start();
      recorder.current = rec;
      setRecording(true);
      setMood("listening"); // the avatar leans in while you talk
    } catch {
      setMood("idle"); // mic denied/unavailable
    }
  }

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text }]);
    setBusy(true);
    setMood("thinking");
    clearTimeout(moodTimer.current);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ person_id: person.id, message: text }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
      const data = await res.json();

      const verdictMood = data.action === "none" ? "speaking" : ({ allow: "allow", deny: "deny", escalate: "escalate" }[data.decision] || "speaking");
      setMood(verdictMood);
      setMessages((m) => [...m, {
        role: "assistant",
        text: data.reply,
        action: data.action !== "none" ? data.action : null,
        decision: data.action !== "none" ? data.decision : null,
      }]);
      // linger on the verdict emote, then settle back to idle
      moodTimer.current = setTimeout(() => setMood("idle"), 2600);
    } catch (err) {
      setMood("deny");
      setMessages((m) => [...m, { role: "assistant", text: `⚠ ${err.message}` }]);
      moodTimer.current = setTimeout(() => setMood("idle"), 2000);
    } finally {
      setBusy(false);
    }
  }

  const blobSize = compact ? 110 : 150;

  return (
    <div className="h-full flex flex-col" style={{ background: `linear-gradient(180deg, ${person.accent}14, transparent 40%)` }}>
      {/* header + avatar */}
      <div className="flex flex-col items-center pt-5 pb-2 gap-2">
        <Blob color={person.accent} shape={shape} mood={mood} size={blobSize} />
        <div className="text-center leading-tight">
          <div className="font-bold text-stone-800">{person.name}</div>
          <div className="text-xs uppercase tracking-wide font-semibold" style={{ color: person.accent }}>
            {person.scope}
          </div>
        </div>
      </div>

      {/* messages */}
      <div ref={scroller} className="flex-1 overflow-y-auto px-4 py-3 space-y-2.5">
        <AnimatePresence initial={false}>
          {messages.map((m, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 10, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              className={`max-w-[85%] ${m.role === "user" ? "ml-auto" : ""}`}
            >
              <div
                className={`px-3.5 py-2.5 text-[15px] rounded-2xl whitespace-pre-wrap ${
                  m.role === "user" ? "text-white rounded-br-md" : "bg-white shadow-sm rounded-bl-md text-stone-800"
                }`}
                style={m.role === "user" ? { background: person.accent } : {}}
              >
                {m.text}
              </div>
              {m.decision && (
                <div className={`inline-flex items-center gap-1.5 mt-1.5 px-2.5 py-1 rounded-full text-xs font-bold ${CHIP[m.decision]?.cls || "bg-stone-100 text-stone-600"}`}>
                  <span>{CHIP[m.decision]?.icon}</span>
                  <span>{m.action} · {CHIP[m.decision]?.label}</span>
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
        {busy && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-sm text-stone-400 italic">
            {person.name}'s assistant is thinking…
          </motion.div>
        )}
      </div>

      {/* input */}
      <div className="p-3 flex gap-2">
        <input
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
            if (!busy) setMood(e.target.value ? "listening" : "idle");
          }}
          onBlur={() => !busy && !input && setMood("idle")}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder={busy ? "…" : recording ? "listening to you…" : transcribing ? "transcribing…" : "Ask your house anything"}
          disabled={busy}
          className="flex-1 px-4 py-2.5 rounded-full bg-white shadow-inner border border-stone-200 outline-none focus:border-stone-400 text-[15px]"
        />
        <motion.button
          whileTap={{ scale: 0.9 }}
          onClick={toggleMic}
          disabled={busy || transcribing}
          animate={recording ? { scale: [1, 1.12, 1] } : { scale: 1 }}
          transition={recording ? { duration: 0.9, repeat: Infinity } : {}}
          className="w-11 h-11 rounded-full font-semibold disabled:opacity-40 flex items-center justify-center text-lg"
          style={{
            background: recording ? "#dc2626" : "#f5f5f4",
            color: recording ? "#fff" : "#57534e",
            boxShadow: recording ? "0 0 0 5px rgba(220,38,38,0.25)" : "none",
          }}
          title={recording ? "stop and transcribe" : "speak instead of typing"}
        >
          {recording ? "■" : "🎤"}
        </motion.button>
        <motion.button
          whileTap={{ scale: 0.92 }}
          onClick={send}
          disabled={busy}
          className="px-5 rounded-full text-white font-semibold disabled:opacity-40"
          style={{ background: person.accent }}
        >
          ➤
        </motion.button>
      </div>
    </div>
  );
}
