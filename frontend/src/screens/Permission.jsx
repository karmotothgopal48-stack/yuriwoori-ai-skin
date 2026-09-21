import { useState } from "react";
import { Camera, Upload, AlertCircle, ScanFace, Sun, Eye, ShieldCheck } from "lucide-react";
import { Button, Eyebrow } from "../components/Button";
import { IMAGES } from "../theme/brand";
import { readFileAsDataUrl } from "../services/camera";

const BEFORE_SCAN = [
  { icon: ScanFace, text: "Face the camera directly" },
  { icon: Sun, text: "Use natural, even lighting" },
  { icon: Eye, text: "Keep your face clearly visible" },
];

/* Triggers the real browser permission prompt, then releases the camera.
   The Camera screen re-opens it (permission is remembered by the browser). */
export default function Permission({ go, setPhoto }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const allow = async () => {
    setBusy(true); setError("");
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: true });
      s.getTracks().forEach((t) => t.stop());
      go("tips");
    } catch (e) {
      setError(e.name === "NotAllowedError"
        ? "Camera access was blocked. Allow it in your browser's address bar, or upload a photo instead."
        : "No camera could be opened on this device. You can upload a photo instead.");
    } finally { setBusy(false); }
  };

  const upload = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setPhoto(await readFileAsDataUrl(f));
    go("review");
  };

  return (
    <div className="yw-enter mx-auto grid max-w-5xl grid-cols-1 items-center gap-8 px-5 py-8 sm:px-10 md:grid-cols-2 md:gap-12 md:py-14">
      {/* Visual */}
      <div className="relative mx-auto w-full max-w-md overflow-hidden rounded-[2rem] bg-mist shadow-lg shadow-jade/10 md:max-w-none">
        <img
          src={IMAGES.analysisFace} alt="AI skin analysis illustration"
          className="aspect-[5/4] w-full object-cover object-top md:aspect-[462/540]"
        />
        <div className="absolute inset-x-4 bottom-4 rounded-2xl bg-white/95 px-4 py-3 shadow-sm">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-jade">AI Skin Analysis</p>
          <p className="text-sm text-ink-soft">Personalized to your skin</p>
        </div>
      </div>

      {/* Content */}
      <div className="mx-auto w-full max-w-md md:max-w-none">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-mist"><Camera size={24} className="text-jade" /></div>
        <h2 className="mt-5 text-3xl text-jade sm:text-4xl">Allow camera access</h2>
        <p className="mt-3 text-sm leading-relaxed text-ink-soft">
          Yuri needs your camera to guide your face capture, so we can read your skin in the right light and position.
        </p>

        {error && (
          <p role="alert" className="mt-5 flex items-start gap-2 rounded-xl bg-[#fbeeee] p-3 text-xs text-[#8a2e2e]">
            <AlertCircle size={15} className="mt-0.5 shrink-0" /> {error}
          </p>
        )}

        <div className="mt-6 flex flex-col gap-3">
          <Button full onClick={allow} disabled={busy} icon={Camera}>{busy ? "Waiting for permission…" : "Allow camera"}</Button>
          <label className="inline-flex w-full cursor-pointer items-center justify-center gap-2 rounded-full border border-jade px-7 py-3.5 text-sm font-semibold text-jade transition hover:bg-mist">
            <Upload size={16} /> Upload a photo instead
            <input type="file" accept="image/*" className="sr-only" onChange={upload} />
          </label>
          <button onClick={() => go("start")} className="self-center text-xs font-medium text-ink-soft hover:text-jade">Not now</button>
        </div>

        <p className="mt-4 flex items-center gap-2 text-xs text-ink-soft">
          <ShieldCheck size={14} className="shrink-0 text-jade" /> Your photo stays in your browser during this prototype.
        </p>

        <div className="mt-7 border-t border-mist pt-6">
          <Eyebrow>Before you scan</Eyebrow>
          <ul className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-3">
            {BEFORE_SCAN.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-3 rounded-2xl bg-cream px-3.5 py-3 sm:flex-col sm:items-start sm:gap-2">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white"><Icon size={16} className="text-jade" /></span>
                <span className="text-xs font-medium leading-snug text-ink">{text}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
