import { useEffect, useRef, useState } from "react";
import { Loader2, AlertCircle, Upload, RefreshCcw, Camera as CameraIcon } from "lucide-react";
import { Button } from "../components/Button";
import { captureFrame, measureBrightness, readFileAsDataUrl } from "../services/camera";
import { detectFace } from "../services/skinAnalysis";
import { motion, AnimatePresence } from "framer-motion";

function StatusPill({ ok, text }) {
  return (
    <motion.div 
      initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }}
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider backdrop-blur-md shadow-sm transition-colors ${ok ? "bg-white/90 text-jade" : "bg-black/40 text-white/90"}`}
    >
      <div className={`w-1.5 h-1.5 rounded-full ${ok ? "bg-jade" : "bg-white/60"}`} />
      {text}
    </motion.div>
  );
}

export default function Camera({ go, setPhoto }) {
  const videoRef = useRef(null);
  const probeRef = useRef(null);
  const [state, setState] = useState("starting"); // starting | live | error
  const [error, setError] = useState("");
  const [faceOk, setFaceOk] = useState(false);
  const [lightOk, setLightOk] = useState(false);
  const [facingMode, setFacingMode] = useState("user");
  const [flash, setFlash] = useState(false);

  const startCamera = async (mode = "user") => {
    setState("starting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        video: { facingMode: mode, width: { ideal: 1280 }, height: { ideal: 1280 } } 
      });
      if (videoRef.current) {
        if (videoRef.current.srcObject) {
          videoRef.current.srcObject.getTracks().forEach((t) => t.stop());
        }
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setState("live");
        detectFace(videoRef.current).then((r) => setFaceOk(r.detected && r.centered));
      } else {
        stream.getTracks().forEach((t) => t.stop());
      }
    } catch (e) {
      setError(e.name === "NotAllowedError" ? "Camera access is blocked for this site." : "No camera is available on this device.");
      setState("error");
    }
  };

  useEffect(() => {
    startCamera(facingMode);
    return () => {
      if (videoRef.current && videoRef.current.srcObject) {
        videoRef.current.srcObject.getTracks().forEach((t) => t.stop());
      }
    };
  }, [facingMode]);

  useEffect(() => {
    if (state !== "live") return;
    const id = setInterval(() => {
      const v = videoRef.current;
      if (v?.videoWidth) { 
        const b = measureBrightness(v, probeRef.current); 
        setLightOk(b > 70 && b < 215); 
      }
    }, 500);
    return () => clearInterval(id);
  }, [state]);

  const switchCamera = () => {
    setFacingMode(prev => prev === "user" ? "environment" : "user");
  };

  const upload = async (e) => {
    const f = e.target.files?.[0];
    if (f) { setPhoto(await readFileAsDataUrl(f)); go("review"); }
  };

  const handleCapture = () => {
    if (state !== "live") return;
    setFlash(true);
    setTimeout(() => {
      setPhoto(captureFrame(videoRef.current));
      go("review");
    }, 150);
  };

  const locked = state === "live" && faceOk && lightOk;

  return (
    <div className="flex-1 flex flex-col items-center justify-center w-full max-w-md mx-auto px-4 py-4 sm:py-8 h-[dvh]">
      
      {/* Viewfinder Container */}
      <div className="relative w-full aspect-[3/4] max-h-[70vh] overflow-hidden rounded-[32px] bg-[#1a1a1a] shadow-float border-4 border-white/20">
        
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
            {/* Darkened outside, clear oval inside */}
            <svg viewBox="0 0 300 400" className="pointer-events-none absolute inset-0 h-full w-full z-10" preserveAspectRatio="xMidYMid slice">
              <defs>
                <mask id="oval">
                  <rect width="300" height="400" fill="white" />
                  <ellipse cx="150" cy="195" rx="95" ry="135" fill="black" />
                </mask>
              </defs>
              <rect width="300" height="400" fill="rgba(15,43,42,0.6)" mask="url(#oval)" />
              
              {/* Animated glowing brackets */}
              <motion.g 
                stroke={locked ? "#9DD4CA" : "rgba(255,255,255,0.4)"} 
                strokeWidth="2.5" 
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
                <path d="M 75 90 Q 55 90 55 110" />
                {/* Top Right */}
                <path d="M 225 90 Q 245 90 245 110" />
                {/* Bottom Left */}
                <path d="M 55 280 Q 55 300 75 300" />
                {/* Bottom Right */}
                <path d="M 245 280 Q 245 300 225 300" />
              </motion.g>
            </svg>

            {/* Top Status */}
            <div className="absolute top-5 inset-x-0 z-20 flex flex-col items-center gap-2">
              <StatusPill ok={state === "live"} text="Camera Ready" />
              {(!faceOk || !lightOk) && (
                <div className="flex gap-2 mt-1">
                  {!faceOk && <StatusPill ok={false} text="Center Face" />}
                  {faceOk && !lightOk && <StatusPill ok={false} text="Improve Lighting" />}
                </div>
              )}
            </div>

            {/* Bottom Guidance */}
            <div className="absolute bottom-6 inset-x-0 z-20 text-center px-6">
              <p className="text-white/90 font-medium text-sm drop-shadow-md">
                {locked ? "Perfect. Ready to capture." : "Center your face in the oval"}
              </p>
            </div>
          </>
        )}
      </div>

      {/* Controls Area */}
      <div className="w-full flex items-center justify-between mt-8 px-6">
        <button 
          onClick={() => go("tips")} 
          className="w-12 h-12 flex items-center justify-center rounded-full bg-white text-ink-soft shadow-soft hover:bg-mist transition-colors"
          aria-label="Back"
        >
          <span className="text-xs font-semibold uppercase tracking-widest">Back</span>
        </button>

        {/* Big Capture Button */}
        <button 
          onClick={handleCapture}
          disabled={state !== "live"}
          className="relative group w-20 h-20 flex items-center justify-center rounded-full disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label="Capture photo"
        >
          <div className="absolute inset-0 bg-white/30 rounded-full group-hover:scale-105 group-active:scale-95 transition-transform duration-300" />
          <div className="absolute inset-2 bg-white rounded-full group-hover:scale-95 group-active:scale-90 transition-transform duration-300 shadow-float flex items-center justify-center">
            <div className="w-12 h-12 bg-jade rounded-full shadow-inner" />
          </div>
        </button>

        <button 
          onClick={switchCamera} 
          disabled={state !== "live"}
          className="w-12 h-12 flex items-center justify-center rounded-full bg-white text-ink-soft shadow-soft hover:text-jade hover:bg-mist transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label="Switch camera"
        >
          <RefreshCcw size={20} strokeWidth={2} />
        </button>
      </div>
    </div>
  );
}
