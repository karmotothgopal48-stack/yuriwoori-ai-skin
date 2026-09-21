import { useCallback, useState } from "react";
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

// Journey order — drives the step indicator. Screens not listed show no progress.
const FLOW = ["permission", "tips", "camera", "review", "processing", "results", "profile", "recommendations", "products", "routine", "assistant"];

const SCREENS = { start: Start, permission: Permission, tips: Tips, camera: Camera, review: Review, processing: Processing, results: Results, profile: Profile, recommendations: Recommendations, products: Products, routine: Routine, assistant: Assistant };

export default function App() {
  const [screen, setScreen] = useState("start");
  const [photo, setPhoto] = useState(null);       // captured/uploaded face photo, sent to the backend for analysis
  const [analysis, setAnalysis] = useState(null);

  const go = useCallback((next) => { setScreen(next); window.scrollTo(0, 0); }, []);
  const Screen = SCREENS[screen];
  const needsAnalysis = ["results", "profile", "recommendations", "products", "routine"].includes(screen);

  return (
    <div className="min-h-screen bg-white">
      <Header onHome={() => go("start")} onChat={() => go("assistant")} step={FLOW.indexOf(screen) + 1} total={FLOW.length} />
      <main>
        {needsAnalysis && !analysis
          ? <Start go={go} />
          : <Screen go={go} photo={photo} setPhoto={setPhoto} analysis={analysis} setAnalysis={setAnalysis} />}
      </main>
    </div>
  );
}
