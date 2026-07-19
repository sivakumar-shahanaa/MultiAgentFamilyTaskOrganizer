import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import Blob, { SHAPES } from "./components/Blob.jsx";
import AvatarPicker from "./components/AvatarPicker.jsx";
import Chat from "./components/Chat.jsx";

/* Phone-first flow:
   #/            join: enter name -> wait for a parent to admit -> pick avatar
                 (returning phones with a saved person_id skip straight to chat)
   #/pick/<id>   avatar picker
   #/chat/<id>   conversation
   #/household   who's-who grid (demo machine)
   #/wall        all windows side-by-side (the demo money shot)              */

function useHash() {
  const [hash, setHash] = useState(window.location.hash || "#/");
  useEffect(() => {
    const fn = () => setHash(window.location.hash || "#/");
    window.addEventListener("hashchange", fn);
    return () => window.removeEventListener("hashchange", fn);
  }, []);
  return hash;
}

/* Deterministic, COLLISION-FREE default shape per person (localStorage pick wins). */
function assignShapes(people) {
  const keys = Object.keys(SHAPES);
  const used = new Set();
  const map = {};
  for (const p of people) {
    let h = 0;
    for (const ch of String(p.id)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
    let i = h % keys.length;
    while (used.has(keys[i]) && used.size < keys.length) i = (i + 1) % keys.length;
    used.add(keys[i]);
    map[p.id] = keys[i];
  }
  return map;
}

function Join({ onJoined }) {
  const [name, setName] = useState("");
  const [reqId, setReqId] = useState(null);
  const [error, setError] = useState(null);

  async function submit() {
    const n = name.trim();
    if (!n) return;
    setError(null);
    try {
      const res = await fetch("/login", {
        method: "POST",
        headers: { "content-type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ name: n }),
      });
      const m = res.url.match(/request_id=(\d+)/);
      if (!m) throw new Error("unexpected response");
      setReqId(m[1]);
    } catch (e) {
      setError(String(e.message || e));
    }
  }

  // poll until a parent admits us on /admin
  useEffect(() => {
    if (!reqId) return;
    const t = setInterval(async () => {
      try {
        const d = await (await fetch(`/access-requests/${reqId}`)).json();
        if (d.person_id) {
          clearInterval(t);
          onJoined(d.person_id);
        }
      } catch { /* keep polling */ }
    }, 1500);
    return () => clearInterval(t);
  }, [reqId, onJoined]);

  if (reqId) {
    return (
      <Center>
        <Blob color="#a8a29e" shape="ghost" mood="listening" size={130} />
        <h1 className="text-xl font-bold text-stone-800 mt-6">Hi {name.trim()}!</h1>
        <p className="text-stone-500 mt-1 text-center">
          Waiting for a parent to let you in…
        </p>
        <motion.div
          animate={{ opacity: [0.4, 1, 0.4] }}
          transition={{ duration: 1.6, repeat: Infinity }}
          className="mt-3 text-xs uppercase tracking-widest font-bold text-stone-400"
        >
          asking the house
        </motion.div>
      </Center>
    );
  }

  return (
    <Center>
      <Blob color="#78716c" shape="clover" mood="idle" size={120} />
      <h1 className="text-2xl font-extrabold text-stone-800 mt-6">Whose House Is It Anyway</h1>
      <p className="text-stone-500 mt-1 mb-6">Tell the house who you are</p>
      <div className="w-full max-w-xs flex flex-col gap-3">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Your name"
          className="px-4 py-3.5 rounded-full bg-white shadow-inner border border-stone-200 outline-none focus:border-stone-400 text-center text-lg"
        />
        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={submit}
          className="py-3.5 rounded-full text-white font-semibold text-lg shadow-lg"
          style={{ background: "#1c1917" }}
        >
          Join the house
        </motion.button>
        {error && <p className="text-rose-600 text-sm text-center">{error}</p>}
        <a href="#/household" className="text-center text-xs text-stone-400 underline mt-2">
          I'm on the demo machine — show everyone
        </a>
      </div>
    </Center>
  );
}

export default function App() {
  const hash = useHash();
  const [people, setPeople] = useState(null);
  const [error, setError] = useState(null);

  const loadPeople = useCallback(() => {
    fetch("/api/people")
      .then((r) => r.json())
      .then(setPeople)
      .catch((e) => setError(String(e)));
  }, []);
  useEffect(() => { loadPeople(); }, [loadPeople]);

  if (error) return <Center><p className="text-rose-600">Backend unreachable: {error}</p></Center>;
  if (!people) return <Center><p className="text-stone-400">Loading household…</p></Center>;

  const shapeMap = assignShapes(people);
  const shapeFor = (p) => localStorage.getItem(`avatar:${p.id}`) || shapeMap[p.id];

  const [, route, id] = hash.slice(1).split("/"); // "", "pick"|"chat"|"wall"|"household", id

  if (route === "wall") {
    return (
      <div className="h-full grid gap-2 p-2 bg-stone-100" style={{ gridTemplateColumns: `repeat(${Math.min(people.length, 4)}, 1fr)` }}>
        {people.slice(0, 4).map((p) => (
          <div key={p.id} className="rounded-2xl overflow-hidden bg-white shadow">
            <Chat person={p} shape={shapeFor(p)} compact />
          </div>
        ))}
      </div>
    );
  }

  const person = id ? people.find((p) => p.id === id) : null;

  if (route === "pick" && person) {
    return (
      <AvatarPicker
        person={person}
        fallbackShape={shapeMap[person.id]}
        onDone={() => (window.location.hash = `#/chat/${person.id}`)}
      />
    );
  }
  if (route === "chat" && person) {
    return <Chat person={person} shape={shapeFor(person)} />;
  }

  if (route === "household") {
    return (
      <Center>
        <div className="text-center mb-8">
          <h1 className="text-3xl font-extrabold text-stone-800">Whose House Is It Anyway</h1>
          <p className="text-stone-500 mt-1">Who's asking? Pick your window.</p>
        </div>
        <div className="flex flex-wrap justify-center gap-6 max-w-2xl">
          {people.map((p) => (
            <button
              key={p.id}
              onClick={() => (window.location.hash = `#/pick/${p.id}`)}
              className="flex flex-col items-center gap-2 p-4 rounded-3xl hover:bg-white hover:shadow-lg transition-all"
            >
              <Blob color={p.accent} shape={shapeFor(p)} mood="idle" size={92} />
              <div className="font-semibold text-stone-700">{p.name}</div>
              <div className="text-[11px] uppercase tracking-wider font-bold" style={{ color: p.accent }}>{p.scope}</div>
            </button>
          ))}
        </div>
        <a href="#/wall" className="mt-10 text-sm text-stone-400 hover:text-stone-600 underline">
          demo wall — all windows side by side →
        </a>
      </Center>
    );
  }

  // default route "#/": returning phone -> straight to chat; else join flow
  const savedId = localStorage.getItem("person_id");
  const saved = savedId && people.find((p) => p.id === savedId);
  if (saved) {
    window.location.hash = `#/chat/${saved.id}`;
    return null;
  }
  return (
    <Join
      onJoined={(personId) => {
        localStorage.setItem("person_id", personId);
        loadPeople(); // the new person isn't in our list yet
        window.location.hash = `#/pick/${personId}`;
      }}
    />
  );
}

function Center({ children }) {
  return <div className="min-h-full flex flex-col items-center justify-center p-8 bg-stone-50">{children}</div>;
}
