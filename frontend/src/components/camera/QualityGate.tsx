"use client";

import { useEffect, useRef, useState } from "react";
import "@mediapipe/face_detection";
import "@tensorflow/tfjs-core";
import "@tensorflow/tfjs-backend-webgl";
import * as faceDetection from "@tensorflow-models/face-detection";
import { measureBrightness } from "@/lib/camera";

export interface QualityState {
  lightingOk: boolean;
  faceCentered: boolean;
  stillOk: boolean;
  faceConfidence: number;
  allPassed: boolean;
}

export function useQualityGate(videoRef: React.RefObject<HTMLVideoElement | null>) {
  // Lazily create the offscreen canvas on first render. `document` doesn't
  // exist during server-side prerendering, so it can't be created eagerly
  // as the useRef initial value.
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  if (canvasRef.current === null && typeof document !== "undefined") {
    canvasRef.current = document.createElement("canvas");
  }
  const detectorRef = useRef<faceDetection.FaceDetector | null>(null);
  const lastCenterRef = useRef<{ x: number; y: number } | null>(null);
  const [quality, setQuality] = useState<QualityState>({
    lightingOk: false,
    faceCentered: false,
    stillOk: false,
    faceConfidence: 0,
    allPassed: false,
  });

  useEffect(() => {
    let cancelled = false;

    faceDetection
      .createDetector(faceDetection.SupportedModels.MediaPipeFaceDetector, {
        runtime: "tfjs",
        maxFaces: 1,
        modelType: "short",
      })
      .then((detector) => {
        if (!cancelled) detectorRef.current = detector;
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const interval = setInterval(async () => {
      const video = videoRef.current;
      const detector = detectorRef.current;
      const canvas = canvasRef.current;
      if (!video || !detector || !canvas || video.videoWidth === 0) return;

      const brightness = measureBrightness(video, canvas);
      const lightingOk = brightness > 40 && brightness < 190;

      const faces = await detector.estimateFaces(video, { flipHorizontal: false });

      let faceCentered = false;
      let stillOk = false;
      let faceConfidence = 0;

      if (faces.length > 0) {
        const box = faces[0].box;
        faceConfidence = 1;

        const centerX = box.xMin + box.width / 2;
        const centerY = box.yMin + box.height / 2;
        const videoCenterX = video.videoWidth / 2;
        const videoCenterY = video.videoHeight / 2;

        const offsetX = Math.abs(centerX - videoCenterX) / video.videoWidth;
        const offsetY = Math.abs(centerY - videoCenterY) / video.videoHeight;
        faceCentered = offsetX < 0.15 && offsetY < 0.15;

        if (lastCenterRef.current) {
          const movement = Math.hypot(
            centerX - lastCenterRef.current.x,
            centerY - lastCenterRef.current.y
          );
          stillOk = movement < video.videoWidth * 0.02;
        }
        lastCenterRef.current = { x: centerX, y: centerY };
      } else {
        lastCenterRef.current = null;
      }

      setQuality({
        lightingOk,
        faceCentered,
        stillOk,
        faceConfidence,
        allPassed: lightingOk && faceCentered && stillOk,
      });
    }, 350);

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