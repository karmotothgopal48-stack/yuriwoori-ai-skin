import { useEffect, useRef, useState } from "react";
import { Loader2, AlertCircle, Upload, RefreshCcw, ChevronLeft } from "lucide-react";
import { Eyebrow } from "../components/Button";
import { captureFrame, describeCameraError, measureBrightness, openCamera, readFileAsDataUrl, stopStream } from "../services/camera";
import { motion, AnimatePresence } from "framer-motion";

const NOT_FOUND = "Please position your face or hand inside the frame.";

function StatusPill({ ok, text }) {
  return (
    <motion.div 
      initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }}
      className={`inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] backdrop-blur-md shadow-soft transition-colors ${ok ? "bg-white/90 text-jade" : "bg-[#0f2b2a]/55 text-white/90"}`}
    >
      <span className="relative flex h-1.5 w-1.5">
        {ok && <span className="absolute inline-flex h-full w-full rounded-full bg-jade opacity-60 motion-safe:animate-ping" />}
        <span className={`relative inline-flex h-1.5 w-1.5 rounded-full ${ok ? "bg-jade" : "bg-white/70"}`} />
      </span>
      {text}
    </motion.div>
  );
}

export default function Camera({ go, setPhoto, setBodyPart }) {
  const videoRef = useRef(null);
  const probeRef = useRef(null);
  const [state, setState] = useState("starting"); // starting | live | error
  const [error, setError] = useState("");
  // On-device checks: the mean brightness of the live frame, and which supported body part is in
  // view (MediaPipe face + hand detectors, services/bodyPart.js). The server detects that body part
  // again after capture (POST /scans/{id}/analyze) before measuring anything.
  const [light, setLight] = useState(null); // null | "ok" | "dark" | "bright"
  const detectionRef = useRef(null); // { api, detectors } once loaded
  const [detector, setDetector] = useState("loading"); // loading | ready | unavailable
  const [part, setPart] = useState(null); // null | "face" | "hand"
  // For a face: null when it passes the full-face checks, otherwise what to fix (services/bodyPart.js)
  const [faceIssue, setFaceIssue] = useState(null);
  const [uploadError, setUploadError] = useState("");
  const [facingMode, setFacingMode] = useState("user");
  const [flash, setFlash] = useState(false);

  // The open stream is kept here, not read back from the <video>: on unmount React clears videoRef before the
  // effect cleanup runs, so the camera would otherwise stay on (and stay locked for other apps).
  const streamRef = useRef(null);
  // Each start gets a number; a start that has been superseded (camera flipped, Try again, React StrictMode's
  // second mount, or leaving the screen) releases its stream and reports nothing.
  const requestRef = useRef(0);

  const stopCamera = () => {
    requestRef.current += 1;
    stopStream(streamRef.current);
    streamRef.current = null;
  };

  const startCamera = async (mode = "user") => {
    stopCamera(); // release the current camera first: a camera can't be opened twice on Windows
    const request = requestRef.current;
    const current = () => request === requestRef.current;
    setState("starting");
    setError("");
    try {
      const stream = await openCamera({ facingMode: mode, width: { ideal: 1280 }, height: { ideal: 1280 } });
      if (!current() || !videoRef.current) { stopStream(stream); return; }
      streamRef.current = stream;
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      if (current()) setState("live");
    } catch (e) {
      if (!current()) return; // e.g. play() interrupted because a newer start replaced the stream
      stopCamera();
      console.warn("Camera could not be opened:", e);
      setError(describeCameraError(e));
      setState("error");
    }
  };

  useEffect(() => {
    startCamera(facingMode);
    return stopCamera;
  }, [facingMode]);

  useEffect(() => {
    if (state !== "live") return;
    const id = setInterval(() => {
      const v = videoRef.current;
      if (v?.videoWidth) { 
        const b = measureBrightness(v, probeRef.current);
        setLight(b <= 70 ? "dark" : b >= 215 ? "bright" : "ok");
      }
    }, 500);
    return () => clearInterval(id);
  }, [state]);

  // MediaPipe is loaded only on this step (its own chunk), not with the rest of the app.
  const loadDetection = () => import("../services/bodyPart");

  useEffect(() => {
    let alive = true;
    loadDetection()
      .then(async (api) => {
        const detectors = await api.loadDetectors();
        if (alive) { detectionRef.current = { api, detectors }; setDetector("ready"); }
      })
      .catch(() => { if (alive) setDetector("unavailable"); });
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    if (state !== "live" || detector !== "ready") return;
    let last = null, streak = 0;
    const id = setInterval(() => {
      let result;
      const { api, detectors } = detectionRef.current;
      const v = videoRef.current;
      // "In frame" means inside the visible preview, which crops the video to the box's shape
      try { result = api.detectInVideo(detectors, v, performance.now(), v.clientWidth / v.clientHeight); } catch { return; }
      if (!result) return;
      // The label only changes after two matching frames in a row, so it doesn't flicker
      const key = `${result.part}|${result.face?.message ?? ""}`;
      streak = key === last ? streak + 1 : 1;
      last = key;
      if (streak >= 2) { setPart(result.part); setFaceIssue(result.face?.message ?? null); }
    }, 250);
    return () => { clearInterval(id); setPart(null); setFaceIssue(null); };
  }, [state, detector]);

  const switchCamera = () => {
    setFacingMode(prev => prev === "user" ? "environment" : "user");
  };

  const upload = async (e) => {
    const f = e.target.files?.[0];
    e.target.value = ""; // the same file can be chosen again after an error
    if (!f) return;
    setUploadError("");
    const photo = await readFileAsDataUrl(f);
    // Detectors unavailable (or the file can't be decoded here): fall back to a face scan, which the
    // server's face check still verifies, as before this step existed.
    let found = "face";
    if (detector !== "unavailable") {
      let result = { part: "face", face: null };
      try { result = await (await loadDetection()).detectInImage(photo); } catch { /* keep the face fallback */ }
      if (result.part === "face" && result.face && !result.face.ok) {
        setUploadError(`This photo can't be used: ${result.face.message.toLowerCase()}. Please choose a clear, straight-on photo of your full face.`);
        return;
      }
      found = result.part;
    }
    if (!found) {
      setUploadError("We couldn't find a face or hand in that photo. Please choose a clear photo of your face or the back of your hand.");
      return;
    }
    setBodyPart(found);
    setPhoto(photo);
    go("review");
  };

  const lightOk = light === "ok";
  // A face must pass every full-face check and have good light; a hand must be detected. If the
  // detectors can't load, capture behaves as before (face, checked by the server after capture).
  const faceReady = part === "face" && faceIssue === null && lightOk;
  const canCapture = state === "live" && (faceReady || part === "hand" || detector === "unavailable");

  const handleCapture = () => {
    if (!canCapture) return;
    const captured = part ?? "face";
    setFlash(true);
    setTimeout(() => {
      setPhoto(captureFrame(videoRef.current));
      setBodyPart(captured);
      go("review");
    }, 150);
  };

  const locked = canCapture && lightOk;
  const detectText = detector === "loading" ? "Starting face and hand detection..."
    : part === "face" ? "Face detected" : part === "hand" ? "Hand detected" : "Looking for a face or hand...";
  const guidance = detector === "unavailable" ? "Centre one face in the frame"
    // Light first: in poor light the face landmarks (and so the other checks) are unreliable
    : part === "face" ? (!lightOk ? "Please improve the lighting" : faceIssue ?? "Keep still, then capture.")
    : part === "hand" ? "Back of your hand to the camera, fingers relaxed, then capture."
    : NOT_FOUND;

  return (
    <div className="flex-1 flex flex-col items-center justify-center w-full max-w-md mx-auto px-4 py-4 sm:py-6">
      <Eyebrow className="mb-3 text-jade tracking-[0.14em]">Step 3 &middot; Camera</Eyebrow>

      {/* Viewfinder Container */}
      <div className="relative w-full max-w-[380px] aspect-[3/4] max-h-[64vh] overflow-hidden rounded-[2rem] bg-[#16302f] shadow-float ring-[6px] ring-white outline outline-1 outline-sage-light">
        
        {/* Flash overlay */}
        <AnimatePresence>
          {flash && (
            <motion.div 
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} 
              className="absolute inset-0 z-50 bg-white"
            />
          )}
        </AnimatePresence>

        <video 
          ref={videoRef} 
          playsInline 
          muted 
          className={`absolute inset-0 h-full w-full object-cover transition-transform duration-300 ${facingMode === "user" ? "-scale-x-100" : ""}`} 
        />
        <canvas ref={probeRef} className="hidden" />

        {/* Loading State */}
        {state === "starting" && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-black/40 backdrop-blur-md text-white">
            <Loader2 className="animate-spin mb-3 text-jade-soft" size={32} />
            <p className="text-sm font-semibold tracking-wide">Starting camera...</p>
          </div>
        )}

        {/* Error State */}
        {state === "error" && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-5 p-8 text-center bg-cream">
            <div className="w-16 h-16 bg-[#fcf4f3] rounded-full flex items-center justify-center border border-[#f0dedd]">
              <AlertCircle size={28} className="text-[#8a2e2e]" />
            </div>
            <div>
              <p className="text-lg font-display text-ink mb-2">Camera unavailable</p>
              <p className="text-sm text-ink-soft leading-relaxed">{error}</p>
            </div>
            <label className="mt-2 inline-flex cursor-pointer items-center justify-center gap-2 rounded-pill bg-white px-7 py-3.5 text-sm font-semibold text-jade shadow-soft border border-mist transition hover:bg-mist">
              <Upload size={18} strokeWidth={1.5} /> Upload Photo
              <input type="file" accept="image/*" className="sr-only" onChange={upload} />
            </label>
            <button onClick={() => startCamera(facingMode)} className="text-xs font-semibold uppercase tracking-widest text-jade">Try again</button>
          </div>
        )}

        {/* Live UI Overlay */}
        {state === "live" && (
          <>
            {/* Darkened outside, clear frame inside (a rounded frame fits a face or a hand) */}
            <svg viewBox="0 0 300 400" className="pointer-events-none absolute inset-0 h-full w-full z-10" preserveAspectRatio="xMidYMid slice">
              <defs>
                <mask id="frame">
                  <rect width="300" height="400" fill="white" />
                  <rect x="50" y="62" width="200" height="266" rx="30" fill="black" />
                </mask>
              </defs>
              <rect width="300" height="400" fill="rgba(15,43,42,0.45)" mask="url(#frame)" />
              <rect x="50" y="62" width="200" height="266" rx="30" fill="none" stroke={locked ? "#9DD4CA" : "rgba(255,255,255,0.55)"} strokeWidth="1" strokeDasharray="3 6" />
              {[[150, 62], [250, 195], [150, 328], [50, 195]].map(([x, y]) => (
                <circle key={`${x}-${y}`} cx={x} cy={y} r="2.6" fill={locked ? "#9DD4CA" : "rgba(255,255,255,0.8)"} />
              ))}
              
              {/* Animated glowing brackets */}
              <motion.g 
                stroke={locked ? "#9DD4CA" : "rgba(255,255,255,0.45)"} 
                strokeWidth="2" 
                fill="none" 
                strokeLinecap="round"
                animate={{ 
                  scale: locked ? [1, 1.02, 1] : 1, 
                  opacity: locked ? [0.6, 1, 0.6] : 1 
                }}
                transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                style={{ transformOrigin: "150px 195px" }}
              >
                {/* Top Left */}
                <path d="M 80 62 Q 50 62 50 92" />
                {/* Top Right */}
                <path d="M 220 62 Q 250 62 250 92" />
                {/* Bottom Left */}
                <path d="M 50 298 Q 50 328 80 328" />
                {/* Bottom Right */}
                <path d="M 250 298 Q 250 328 220 328" />
              </motion.g>
            </svg>

            {/* Top Status: on-device body-part detection and lighting check */}
            <div className="absolute top-5 inset-x-0 z-20 flex flex-col items-center gap-2">
              {detector !== "unavailable" && <StatusPill ok={faceReady || part === "hand"} text={detectText} />}
              <StatusPill
                ok={lightOk}
                text={light === "dark" ? "Too dark - find more light" : light === "bright" ? "Too bright - avoid direct light" : lightOk ? "Lighting looks good" : "Checking lighting..."}
              />
            </div>

            {/* Bottom Guidance */}
            <div className="absolute bottom-5 inset-x-0 z-20 text-center px-6">
              <p className="text-white/95 font-medium text-sm drop-shadow-md" role="status" aria-live="polite">{guidance}</p>
              <p className="mt-1 text-[11px] text-white/70 drop-shadow-md">
                {detector === "unavailable" ? "Your face is checked after you capture." : "Face or hand: it is checked again after you capture."}
              </p>
            </div>
          </>
        )}
      </div>

      {uploadError && (
        <p role="alert" className="mt-4 w-full max-w-[380px] flex items-start gap-2 rounded-xl bg-[#fcf4f3] border border-[#f0dedd] p-3 text-sm text-[#8a2e2e]">
          <AlertCircle size={16} className="shrink-0 mt-0.5" /> {uploadError}
        </p>
      )}

      {/* Controls Area */}
      <div className="w-full max-w-[380px] flex items-center justify-between mt-6 px-2">
        <button 
          onClick={() => go("tips")} 
          className="h-12 min-w-[3rem] px-3 flex items-center justify-center gap-1 rounded-full bg-white text-ink-soft border border-hairline shadow-soft hover:bg-mist hover:text-jade transition-colors"
          aria-label="Back"
        >
          <ChevronLeft size={18} strokeWidth={1.75} /><span className="text-[11px] font-semibold uppercase tracking-[0.12em] pr-1">Back</span>
        </button>

        {/* Big Capture Button */}
        <button 
          onClick={handleCapture}
          disabled={!canCapture}
          className="relative group w-20 h-20 flex items-center justify-center rounded-full disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label="Capture photo"
        >
          <div className={`absolute inset-0 rounded-full border-2 transition-colors duration-300 ${locked ? "border-jade" : "border-jade-line"} group-hover:scale-105 group-active:scale-95 transition-transform`} />
          <div className="absolute inset-[5px] bg-white rounded-full group-active:scale-95 transition-transform duration-300 shadow-float flex items-center justify-center">
            <div className="w-[52px] h-[52px] rounded-full bg-[radial-gradient(circle_at_35%_30%,#1b7a7a,#005C5D_60%,#004647)] shadow-inner group-hover:scale-95 transition-transform duration-300" />
          </div>
        </button>

        <button 
          onClick={switchCamera} 
          disabled={state !== "live"}
          className="w-12 h-12 flex items-center justify-center rounded-full bg-white text-ink-soft border border-hairline shadow-soft hover:text-jade hover:bg-mist transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label="Switch camera"
        >
          <RefreshCcw size={18} strokeWidth={1.75} />
        </button>
      </div>

      <p className="mt-4 text-center text-[12px] text-ink-soft">Your photo is not stored and is deleted after analysis.</p>

      {state === "live" && (
        <label className="mt-5 inline-flex cursor-pointer items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-jade underline-offset-4 hover:underline hover:text-[#004647]">
          <Upload size={14} strokeWidth={2} /> Upload a photo instead
          <input type="file" accept="image/*" className="sr-only" onChange={upload} />
        </label>
      )}
    </div>
  );
}
