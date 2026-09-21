import { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import { HeartMark } from "../components/Logo";
import { SUGGESTED_QUESTIONS } from "../data/mock";
import { askYuri } from "../services/skinAnalysis";

export default function Assistant({ go }) {
  const [msgs, setMsgs] = useState([{ role: "ai", text: "Hi, I'm Yuri, your skincare assistant. Ask me about your routine or products." }]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const end = useRef(null);
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [msgs, typing]);

  const send = async (text) => {
    const q = text.trim();
    if (!q || typing) return;
    setMsgs((m) => [...m, { role: "user", text: q }]); setInput(""); setTyping(true);
    let a;
    try { a = await askYuri(q); } catch (e) { a = `Sorry, I couldn't answer that. ${e.message}`; }
    setMsgs((m) => [...m, { role: "ai", text: a }]); setTyping(false);
  };

  return (
    <div className="yw-enter mx-auto flex h-[calc(100vh-4.5rem)] max-w-2xl flex-col px-5 py-6">
      <div className="flex items-center gap-3 border-b border-mist pb-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-full bg-jade"><HeartMark reversed className="h-5" /></div>
        <div className="flex-1"><h2 className="text-2xl leading-none text-jade">Yuri AI</h2><p className="mt-1 text-[11px] text-ink-soft">General skincare guidance, not medical advice</p></div>
        <button onClick={() => go("start")} className="text-xs font-medium text-ink-soft hover:text-jade">Close</button>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto py-5">
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : ""}`}>
            <div className={`max-w-[82%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${m.role === "user" ? "rounded-br-sm bg-jade text-white" : "rounded-bl-sm bg-mist text-ink"}`}>{m.text}</div>
          </div>
        ))}
        {typing && <div className="flex"><div className="flex gap-1 rounded-2xl rounded-bl-sm bg-mist px-4 py-3">{[0, 1, 2].map((i) => <span key={i} className="h-1.5 w-1.5 animate-bounce rounded-full bg-jade" style={{ animationDelay: `${i * 0.15}s` }} />)}</div></div>}
        {msgs.length === 1 && (
          <div className="flex flex-wrap gap-2 pt-2">
            {SUGGESTED_QUESTIONS.map((q) => <button key={q} onClick={() => send(q)} className="rounded-full border border-jade-line px-3.5 py-2 text-xs font-medium text-jade hover:bg-mist">{q}</button>)}
          </div>
        )}
        <div ref={end} />
      </div>
      <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="flex items-center gap-2 border-t border-mist pt-4">
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask Yuri anything about your skin…" className="flex-1 rounded-full bg-mist px-5 py-3 text-sm outline-none focus:ring-2 focus:ring-jade-soft" />
        <button type="submit" aria-label="Send" className="flex h-11 w-11 items-center justify-center rounded-full bg-jade text-white"><Send size={16} /></button>
      </form>
    </div>
  );
}
