import { useCallback, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Header } from "./components/Header";
import Start from "./screens/Start";
import Permission from "./screens/Permission";
import Tips from "./screens/Tips";
import Camera from "./screens/Camera";
import Review from "./screens/Review";
import Processing from "./screens/Processing";
import Results from "./screens/Results";
import Profile from "./screens/Profile";
import Recommendations from "./screens/Recommendations";
import Products from "./screens/Products";
import Routine from "./screens/Routine";
import Assistant from "./screens/Assistant";

const FLOW = ["permission", "tips", "camera", "review", "processing", "results", "profile", "recommendations", "products", "routine", "assistant"];
const SCREENS = { start: Start, permission: Permission, tips: Tips, camera: Camera, review: Review, processing: Processing, results: Results, profile: Profile, recommendations: Recommendations, products: Products, routine: Routine, assistant: Assistant };

const variants = {
  enter: (direction) => ({ x: direction > 0 ? 16 : -16, opacity: 0 }),
  center: { x: 0, opacity: 1 },
  exit: (direction) => ({ x: direction < 0 ? 16 : -16, opacity: 0 }),
};

export default function App() {
  const [[screen, direction], setScreenState] = useState(["start", 0]);
  const [photo, setPhoto] = useState(null);
  const [analysis, setAnalysis] = useState(null);

  const go = useCallback((next) => {
    setScreenState((prev) => {
      const prevIndex = FLOW.indexOf(prev[0]);
      const nextIndex = FLOW.indexOf(next);
      const dir = nextIndex > prevIndex ? 1 : nextIndex < prevIndex ? -1 : 1;
      return [next, dir];
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const Screen = SCREENS[screen];
  const needsAnalysis = ["results", "profile", "recommendations", "products", "routine"].includes(screen);
  const isStart = screen === "start";

  const renderScreen = () => {
    if (needsAnalysis && !analysis) {
      return <Start go={go} />;
    }
    return <Screen go={go} photo={photo} setPhoto={setPhoto} analysis={analysis} setAnalysis={setAnalysis} />;
  };

  return (
    <div className="min-h-dvh flex flex-col bg-cream overflow-hidden">
      <Header onHome={() => go("start")} step={FLOW.indexOf(screen) + 1} total={FLOW.length} />
      
      <main className="flex-1 relative flex flex-col">
        <AnimatePresence initial={false} custom={direction} mode="wait">
          <motion.div
            key={screen}
            custom={direction}
            variants={variants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
            className="flex-1 w-full max-w-7xl mx-auto flex flex-col"
          >
            {renderScreen()}
          </motion.div>
        </AnimatePresence>
      </main>
      
      {!isStart && screen !== "assistant" && (
        <footer className="py-6 text-center text-xs text-ink-soft pb-safe">
          No medical diagnosis. For skincare guidance only.
        </footer>
      )}
    </div>
  );
}
