import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, MotionConfig, motion } from "framer-motion";
import { Header } from "./components/Header";
import Start from "./screens/Start";
import AboutYou from "./screens/AboutYou";
import Signup from "./screens/Signup";
import Permission from "./screens/Permission";
import Tips from "./screens/Tips";
import Camera from "./screens/Camera";
import Review from "./screens/Review";
import Processing from "./screens/Processing";
import Profile from "./screens/Profile";
import Routine from "./screens/Routine";
import Assistant from "./screens/Assistant";
import { CartButton, CartDrawer } from "./components/Cart";
import { CartProvider } from "./services/cart";
import AdminApp from "./admin/AdminApp";
import Report from "./screens/Report";
import { fetchMe } from "./services/skinAnalysis";
import { getUserToken, setUserToken } from "./services/session";
import { sessionRejected } from "./services/apiErrors";
import { releaseReportPhoto, reportPhotoFor } from "./services/reportPhoto";

// Numbered steps shown in the header. Start and the Ask Yuri chat sit outside the flow. The routine is the
// only place products are recommended (morning + evening, each with Add to cart); there is no separate
// products page. The cart (header button + drawer) is shared by the whole app.
const FLOW = ["about", "permission", "tips", "camera", "review", "processing", "profile", "routine"];
const STEP_LABELS = { about: "Your details", permission: "Permission", tips: "Tips", camera: "Camera", review: "Review", processing: "Analysis",
  profile: "Skin profile", routine: "Your routine" };
const SCREENS = { start: Start, about: AboutYou, permission: Permission, tips: Tips, camera: Camera, review: Review, processing: Processing, profile: Profile, routine: Routine, assistant: Assistant };
const NEEDS_ANALYSIS = ["profile", "routine"];
const SHORT_DISCLAIMER_SCREENS = ["routine"];
// Name + WhatsApp + email + consent (Signup) are asked at the start of the analysis, and again before the
// upload (the first call that needs a session) if the session has gone in between.
const NEEDS_SIGNUP = ["about", "processing"];

const variants = {
  enter: (direction) => ({ x: direction > 0 ? 16 : -16, opacity: 0 }),
  center: { x: 0, opacity: 1 },
  exit: (direction) => ({ x: direction < 0 ? 16 : -16, opacity: 0 }),
};

export default function App() {
  // The admin area is a separate, protected app at /admin (no user flow, no shared state).
  const path = window.location.pathname.replace(/\/+$/, "");
  if (path === "/admin") return <AdminApp />;
  // A customer's report from its secure link (/report#t=<token>): standalone, no session needed.
  if (path === "/report") return <Report />;
  return <CartProvider><SkinAnalysisApp /></CartProvider>;
}

function SkinAnalysisApp() {
  const [[screen, direction], setScreenState] = useState(["start", 0]);
  const [photo, setPhoto] = useState(null);
  // Body part in the photo ("face" | "hand"), detected on the camera step; picks the analysis flow
  const [bodyPart, setBodyPart] = useState("face");
  const [analysis, setAnalysis] = useState(null);
  // The selfie shown on this scan's report: an in-memory object URL bound to its scan, never stored (services/reportPhoto.js).
  // Revoked whenever it is replaced or cleared, and when the app unmounts.
  const [reportPhoto, setReportPhoto] = useState(null);
  useEffect(() => () => releaseReportPhoto(reportPhoto), [reportPhoto]);
  // Step 1 answers ({ gender, age }); frontend-only until the flow needs them
  const [about, setAbout] = useState(null);
  // undefined = still checking a saved session, null = not signed up, object = signed-up user
  const [user, setUser] = useState(getUserToken() ? undefined : null);

  // Checking the saved session: it is dropped only when the server rejects it. If the server can't be reached
  // (or errors), the session is kept and checked again every few seconds, so the app reconnects by itself.
  const [sessionAttempt, setSessionAttempt] = useState(0);
  // true while the saved session can't be checked because the server didn't answer (Start says so)
  const [serverUnreachable, setServerUnreachable] = useState(false);
  useEffect(() => {
    if (user !== undefined) return;
    let alive = true;
    let retry;
    fetchMe()
      .then((u) => { if (alive) { setServerUnreachable(false); setUser(u); } })
      .catch((e) => {
        if (!alive) return;
        if (sessionRejected(e.status)) { setServerUnreachable(false); setUserToken(null); setUser(null); }
        else { setServerUnreachable(true); retry = setTimeout(() => setSessionAttempt((n) => n + 1), 5000); }
      });
    return () => { alive = false; clearTimeout(retry); };
  }, [user, sessionAttempt]);

  const go = useCallback((next) => {
    setScreenState((prev) => {
      const prevIndex = FLOW.indexOf(prev[0]);
      const nextIndex = FLOW.indexOf(next);
      const dir = nextIndex > prevIndex ? 1 : nextIndex < prevIndex ? -1 : 1;
      return [next, dir];
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const signOut = useCallback(() => { setUserToken(null); setUser(null); setAnalysis(null); setPhoto(null); setReportPhoto(null); go("start"); }, [go]);

  // Leaving the report (home, or a new scan starting) lets go of its photo
  useEffect(() => { if (["start", "about", "camera"].includes(screen)) setReportPhoto(null); }, [screen]);

  const Screen = SCREENS[screen];
  const isStart = screen === "start";

  const renderScreen = () => {
    if (NEEDS_ANALYSIS.includes(screen) && !analysis) return <Start go={go} user={user} signOut={signOut} serverUnreachable={serverUnreachable} />;
    // a session from before WhatsApp was asked for counts as missing details: the form asks once more
    if (NEEDS_SIGNUP.includes(screen) && (!user || !user.whatsapp)) return <Signup setUser={setUser} />;
    return <Screen go={go} serverUnreachable={serverUnreachable} about={about} setAbout={setAbout} photo={photo} setPhoto={setPhoto} bodyPart={bodyPart} setBodyPart={setBodyPart} analysis={analysis} setAnalysis={setAnalysis} setReportPhoto={setReportPhoto} reportPhotoUrl={reportPhotoFor(reportPhoto, analysis)} user={user} setUser={setUser} signOut={signOut} />;
  };

  return (
    <MotionConfig reducedMotion="user">
    <div className="min-h-dvh flex flex-col bg-cream overflow-hidden">
      <Header onHome={() => go("start")} step={FLOW.indexOf(screen) + 1} total={FLOW.length} label={STEP_LABELS[screen]} actions={<CartButton />} />
      <CartDrawer />

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

      {/* Disclaimer placement: the full version on Start and on the main result page (Profile);
          this short line on the other result pages; none on the capture steps. */}
      {SHORT_DISCLAIMER_SCREENS.includes(screen) && (
        <footer className="py-6 text-center text-xs text-ink-soft pb-safe">
          This analysis is for skincare guidance and is not a medical diagnosis.
        </footer>
      )}
    </div>
    </MotionConfig>
  );
}
