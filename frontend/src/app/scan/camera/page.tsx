"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getCameraStream, stopCameraStream, captureFrame } from "@/lib/camera";
import { FaceTracker } from "@/components/camera/FaceTracker";
import { useQualityGate, StatusPills } from "@/components/camera/QualityGate";
import { useCountdown, CountdownDisplay } from "@/components/camera/CountdownCapture";

type Angle = "front" | "left" | "right";
const ANGLES: { key: Angle; caption: string }[] = [
  { key: "front", caption: "Look straight at the camera" },
  { key: "left", caption: "Turn slightly left" },
  { key: "right", caption: "Turn slightly right" },
];

export default function CameraPage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [angleIndex, setAngleIndex] = useState(0);
  const [captures, setCaptures] = useState<Record<Angle, string | null>>({
    front: null,
    left: null,
    right: null,
  });

  const quality = useQualityGate(videoRef);
  const currentAngle = ANGLES[angleIndex];
  const capturingActive = quality.allPassed && !captures[currentAngle.key];

  const handleCapture = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return;
    const dataUrl = captureFrame(videoRef.current, canvasRef.current);
    setCaptures((prev) => ({ ...prev, [currentAngle.key]: dataUrl }));
    setAngleIndex((prev) => Math.min(prev + 1, ANGLES.length - 1));
  }, [currentAngle.key]);

  const count = useCountdown(capturingActive, handleCapture);

  useEffect(() => {
    let stream: MediaStream | null = null;
    getCameraStream()
      .then((s) => {
        stream = s;
        if (videoRef.current) videoRef.current.srcObject = s;
      })
      .catch(() => setError("Camera access denied. Please allow camera permission and reload."));

    return () => stopCameraStream(stream);
  }, []);

  const allCaptured = ANGLES.every((a) => captures[a.key]);

  return (
    <div className="min-h-screen bg-[#15140F] flex flex-col">
      <div className="flex-1 relative overflow-hidden">
        <video ref={videoRef} autoPlay playsInline muted className="absolute inset-0 w-full h-full object-cover scale-x-[-1]" />
        <canvas ref={canvasRef} className="hidden" />

        <div className="absolute top-[52px] left-0 right-0 flex justify-between px-[22px] z-10">
          <span className="text-[#F7F4EE] text-sm tracking-widest uppercase">YuriWoori</span>
        </div>

        <StatusPills quality={quality} />
        <FaceTracker locked={quality.allPassed} />
        <CountdownDisplay count={count} />

        {!allCaptured && (
          <div className="absolute bottom-[120px] left-0 right-0 text-center z-10">
            <p className="font-display italic text-[22px]" style={{ color: "#F3F1EA" }}>
              {currentAngle.caption}
            </p>
          </div>
        )}

        {error && (
          <div className="absolute inset-0 flex items-center justify-center px-8 text-center text-white">
            {error}
          </div>
        )}
      </div>

      <div className="p-6 pb-10 text-center">
        <div className="flex justify-center gap-2 mb-3">
          {ANGLES.map((a) => (
            <span
              key={a.key}
              className={`w-2 h-2 rounded-full ${captures[a.key] ? "bg-brand-mint" : "bg-white/20"}`}
            />
          ))}
        </div>
        <p className="text-[#B8B3A6] text-xs">
          {allCaptured ? "All angles captured" : `${angleIndex + 1} of ${ANGLES.length} angles`}
        </p>
      </div>
    </div>
  );
}