"use client";

import { useEffect, useRef, useState } from "react";
import { measureBrightness } from "@/lib/camera";

export interface QualityState {
  lightingOk: boolean;
  faceCentered: boolean; // real detection wired in Step 8
  stillOk: boolean;
  allPassed: boolean;
}

export function useQualityGate(videoRef: React.RefObject<HTMLVideoElement>) {
  const canvasRef = useRef<HTMLCanvasElement>(document.createElement("canvas"));
  const [quality, setQuality] = useState<QualityState>({
    lightingOk: false,
    faceCentered: false,
    stillOk: false,
    allPassed: false,
  });

  useEffect(() => {
    const interval = setInterval(() => {
      const video = videoRef.current;
      if (!video) return;

      const brightness = measureBrightness(video, canvasRef.current);
      const lightingOk = brightness > 40 && brightness < 220 * 0.86; // simple usable-range check

      // Placeholder until Step 8 wires the real CV face-detection service:
      const faceCentered = true;
      const stillOk = true;

      const next = {
        lightingOk,
        faceCentered,
        stillOk,
        allPassed: lightingOk && faceCentered && stillOk,
      };
      setQuality(next);
    }, 400);

    return () => clearInterval(interval);
  }, [videoRef]);

  return quality;
}

export function StatusPills({ quality }: { quality: QualityState }) {
  const pills = [
    { label: "Lighting good", ok: quality.lightingOk },
    { label: "Face centered", ok: quality.faceCentered },
    { label: "Hold still", ok: quality.stillOk },
  ];

  return (
    <div className="absolute top-[118px] left-[22px] right-[22px] flex flex-col gap-2 z-10">
      {pills.map((p) => (
        <span
          key={p.label}
          className="self-start bg-white/10 border border-white/15 text-[#EDEBE3] text-xs px-3.5 py-1.5 rounded-full flex items-center gap-2 backdrop-blur-md"
        >
          <span className={p.ok ? "text-brand-mint" : "text-white/30"}>●</span>
          {p.label}
        </span>
      ))}
    </div>
  );
}