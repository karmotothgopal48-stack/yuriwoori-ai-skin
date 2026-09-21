import { useEffect, useRef, useState } from "react";
import { Check, Loader2, AlertCircle, Upload } from "lucide-react";
import { Button } from "../components/Button";
import { captureFrame, measureBrightness, readFileAsDataUrl } from "../services/camera";
import { detectFace } from "../services/skinAnalysis";

function Pill({ ok, children }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium backdrop-blur ${ok ? "border-jade-soft/60 bg-white/15 text-white" : "border-white/20 bg-black/25 text-white/70"}`}>
      {ok ? <Check size={13} className="text-jade-soft" /> : <Loader2 size={13} className="animate-spin" />} {children}
    </span>
  );
}

export default function Camera({ go, setPhoto }) {
  const videoRef = useRef(null);
  const probeRef = useRef(null);
  const [state, setState] = useState("starting"); // starting | live | error
  const [error, setError] = useState("");
  const [faceOk, setFaceOk] = useState(false);
  const [lightOk, setLightOk] = useState(false);
  const [count, setCount] = useState(null);

  // Open the real camera, release it on exit.
  useEffect(() => {
    let stream, cancelled = false;
    // Deferred start: React StrictMode (dev) mounts, cleans up and re-mounts synchronously,
    // and two overlapping getUserMedia calls can disturb the live stream. Cleanup cancels the first.
    const start = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 1280 } } });
        if (cancelled) return stream.getTracks().forEach((t) => t.stop());
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setState("live");
        // Face lock is a UI demonstration for now — see detectFace() in services/skinAnalysis.js.
        detectFace(videoRef.current).then((r) => !cancelled && setFaceOk(r.detected && r.centered));
      } catch (e) {
        setError(e.name === "NotAllowedError" ? "Camera access is blocked for this site." : "No camera is available on this device.");
        setState("error");
      }
    };
    const timer = setTimeout(start, 0);
    return () => { cancelled = true; clearTimeout(timer); stream?.getTracks().forEach((t) => t.stop()); };
  }, []);

  // Real lighting check from the live frame.
  useEffect(() => {
    if (state !== "live") return;
    const id = setInterval(() => {
      const v = videoRef.current;
      if (v?.videoWidth) { const b = measureBrightness(v, probeRef.current); setLightOk(b > 70 && b < 215); }
    }, 500);
    return () => clearInterval(id);
  }, [state]);

  // Lock → countdown → auto capture. Breaking the lock resets the countdown.
  const locked = state === "live" && faceOk && lightOk;
  useEffect(() => {
    if (!locked) { setCount(null); return; }
    setCount(3);
    let n = 3;
    const id = setInterval(() => {
      n -= 1;
      if (n > 0) return setCount(n);
      clearInterval(id);
      setPhoto(captureFrame(videoRef.current));
      go("review");
    }, 900);
    return () => clearInterval(id);
  }, [locked]); // eslint-disable-line react-hooks/exhaustive-deps

  const upload = async (e) => {
    const f = e.target.files?.[0];
    if (f) { setPhoto(await readFileAsDataUrl(f)); go("review"); }
  };
  const captureNow = () => { setPhoto(captureFrame(videoRef.current)); go("review"); };

  return (
    <div className="yw-enter mx-auto flex max-w-md flex-col items-center px-5 py-8">
      <div className="relative aspect-[3/4] w-full overflow-hidden rounded-[2rem] bg-ink">
        <video ref={videoRef} playsInline muted className="absolute inset-0 h-full w-full -scale-x-100 object-cover" />
        <canvas ref={probeRef} className="hidden" />

        {state === "starting" && <div className="absolute inset-0 flex items-center justify-center text-sm text-white/80"><Loader2 className="mr-2 animate-spin" size={18} /> Opening camera…</div>}

        {state === "error" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 p-8 text-center text-white">
            <AlertCircle size={28} className="text-jade-soft" />
            <p className="text-sm">{error}</p>
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-full bg-white px-6 py-3 text-sm font-semibold text-jade">
              <Upload size={16} /> Upload a photo instead
              <input type="file" accept="image/*" className="sr-only" onChange={upload} />
            </label>
          </div>
        )}

        {state === "live" && (
          <>
            <svg viewBox="0 0 300 400" className="pointer-events-none absolute inset-0 h-full w-full" preserveAspectRatio="xMidYMid slice">
              <defs>
                <mask id="oval"><rect width="300" height="400" fill="white" /><ellipse cx="150" cy="190" rx="98" ry="128" fill="black" /></mask>
              </defs>
              <rect width="300" height="400" fill="rgba(15,43,42,0.55)" mask="url(#oval)" />
              <ellipse cx="150" cy="190" rx="98" ry="128" fill="none" strokeWidth="2.5" strokeDasharray={locked ? "0" : "8 7"} stroke={locked ? "#9DD4CA" : "rgba(255,255,255,.8)"} />
            </svg>
            {!locked && <div className="absolute left-[16%] w-[68%] rounded-full bg-jade-soft" style={{ height: 2, animation: "yw-scan 2.4s ease-in-out infinite" }} />}
            <div className="absolute inset-x-0 top-4 flex flex-col items-center gap-2">
              <Pill ok={faceOk}>{faceOk ? "Face detected" : "Looking for your face"}</Pill>
              <Pill ok={lightOk}>{lightOk ? "Lighting good" : "Find softer, even light"}</Pill>
            </div>
            <div className="absolute inset-x-0 bottom-6 text-center text-white">
              {count ? <span className="font-display text-6xl">{count}</span> : <span className="font-display text-xl italic">Align your face inside the outline</span>}
            </div>
          </>
        )}
      </div>

      <p className="mt-4 text-center text-xs text-ink-soft">
        Reads visible skin texture and tone only. Lighting is measured live; face lock is a UI demonstration in this prototype.
      </p>
      <div className="mt-5 flex w-full flex-col gap-3">
        <Button variant="soft" icon={null} full disabled={state !== "live"} onClick={captureNow}>Capture now</Button>
        <button onClick={() => go("tips")} className="text-xs font-medium text-ink-soft hover:text-jade">Back to tips</button>
      </div>
    </div>
  );
}
