import { useEffect, useRef, useState } from "react";
import { Send, Sparkles, X } from "lucide-react";
import { HeartMark } from "../components/Logo";
import { SUGGESTED_QUESTIONS } from "../data/mock";
import { askYuri } from "../services/skinAnalysis";
import { motion, AnimatePresence } from "framer-motion";

const msgVariants = {
  hidden: { opacity: 0, y: 10, scale: 0.98 },
  show: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.3, ease: "easeOut" } }
};

export default function Assistant({ go }) {
  const [msgs, setMsgs] = useState([{ role: "ai", text: "Hi, I'm Yuri, your skincare assistant. Ask me about your routine or products." }]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const end = useRef(null);
  
  useEffect(() => { 
    if (end.current) {
      end.current.scrollIntoView({ behavior: "smooth", block: "end" }); 
    }
  }, [msgs, typing]);

  const send = async (text) => {
    const q = text.trim();
    if (!q || typing) return;
    setMsgs((m) => [...m, { role: "user", text: q }]); setInput(""); setTyping(true);
    let a;
    try { a = await askYuri(q); } catch (e) { a = `Sorry, I couldn't answer that. ${e.message}`; }
    setMsgs((m) => [...m, { role: "ai", text: a }]); setTyping(false);
  };

  return (
    <div className="flex flex-col h-[dvh] w-full max-w-3xl mx-auto bg-white shadow-xl sm:border-x sm:border-hairline">
      
      {/* Header */}
      <div className="flex items-center gap-4 px-6 py-4 border-b border-hairline bg-white/80 backdrop-blur-md z-10 shrink-0">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-jade text-white shadow-soft">
          <HeartMark reversed className="h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="font-display text-2xl text-ink truncate">Yuri AI</h2>
          <p className="text-[11px] font-medium text-ink-soft/80 flex items-center gap-1.5 truncate">
            <Sparkles size={12} className="text-jade" />
            General skincare guidance, not medical advice
          </p>
        </div>
        <button 
          onClick={() => go("start")} 
          className="h-10 w-10 flex items-center justify-center rounded-full bg-mist hover:bg-jade/10 text-ink hover:text-jade transition-colors shrink-0"
          aria-label="Close chat"
        >
          <X size={20} strokeWidth={2} />
        </button>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-6 scroll-smooth">
        <div className="space-y-6">
          <AnimatePresence initial={false}>
            {msgs.map((m, i) => (
              <motion.div 
                key={i} 
                variants={msgVariants}
                initial="hidden"
                animate="show"
                className={`flex w-full ${m.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {m.role === "ai" && (
                  <div className="w-8 h-8 rounded-full bg-jade/10 flex items-center justify-center shrink-0 mr-3 mt-auto mb-1">
                    <HeartMark className="h-3 text-jade" />
                  </div>
                )}
                
                <div className={`max-w-[75%] px-5 py-3.5 text-[15px] leading-relaxed shadow-sm ${
                  m.role === "user" 
                    ? "rounded-[24px] rounded-br-sm bg-jade text-white" 
                    : "rounded-[24px] rounded-bl-sm bg-mist text-ink border border-hairline"
                }`}>
                  {m.text}
                </div>
              </motion.div>
            ))}

            {typing && (
              <motion.div variants={msgVariants} initial="hidden" animate="show" className="flex w-full justify-start">
                <div className="w-8 h-8 rounded-full bg-jade/10 flex items-center justify-center shrink-0 mr-3 mt-auto mb-1">
                  <HeartMark className="h-3 text-jade" />
                </div>
                <div className="px-5 py-4 rounded-[24px] rounded-bl-sm bg-mist border border-hairline flex gap-1.5 items-center">
                  {[0, 1, 2].map((i) => (
                    <motion.div 
                      key={i} 
                      className="w-1.5 h-1.5 rounded-full bg-jade/60"
                      animate={{ y: [0, -4, 0] }}
                      transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15, ease: "easeInOut" }}
                    />
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          
          {/* Suggested Questions */}
          {msgs.length === 1 && (
            <motion.div 
              initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
              className="flex flex-wrap gap-2 pt-4 pl-11"
            >
              {SUGGESTED_QUESTIONS.map((q) => (
                <button 
                  key={q} 
                  onClick={() => send(q)} 
                  className="rounded-full border border-jade/20 bg-white px-4 py-2 text-xs font-semibold text-jade hover:bg-jade/5 hover:border-jade/40 transition-colors text-left"
                >
                  {q}
                </button>
              ))}
            </motion.div>
          )}
          <div ref={end} className="h-4" />
        </div>
      </div>

      {/* Input Area */}
      <div className="p-4 sm:p-6 bg-white border-t border-hairline shrink-0 pb-safe">
        <form 
          onSubmit={(e) => { e.preventDefault(); send(input); }} 
          className="relative flex items-center bg-mist rounded-[24px] border border-hairline focus-within:border-jade/30 focus-within:ring-2 focus-within:ring-jade/10 transition-all shadow-inner-soft p-1.5"
        >
          <input 
            value={input} 
            onChange={(e) => setInput(e.target.value)} 
            placeholder="Ask Yuri anything about your skin…" 
            className="flex-1 bg-transparent px-4 py-3 text-[15px] outline-none text-ink placeholder:text-ink-soft" 
            disabled={typing}
          />
          <button 
            type="submit" 
            disabled={!input.trim() || typing}
            aria-label="Send message" 
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-jade text-white shadow-sm hover:bg-[#004647] disabled:opacity-50 disabled:hover:bg-jade transition-colors ml-2"
          >
            <Send size={18} strokeWidth={2.5} className="ml-0.5" />
          </button>
        </form>
      </div>
    </div>
  );
}
