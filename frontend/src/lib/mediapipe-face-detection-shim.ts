// Compatibility shim for "@mediapipe/face_detection".
//
// @tensorflow-models/face-detection unconditionally does
// `import { FaceDetection } from "@mediapipe/face_detection"` at module
// scope, even though that class is only ever instantiated when the caller
// selects `runtime: "mediapipe"`. The published @mediapipe/face_detection
// package is a UMD build with no real ES module exports, so Turbopack's
// static export-existence check fails the build with:
//   "Export FaceDetection doesn't exist in target module"
//
// This app only ever uses `runtime: "tfjs"` (see
// src/components/camera/QualityGate.tsx), so the mediapipe runtime path —
// and this class — is never exercised. This shim (aliased in
// next.config.ts) satisfies the static import without pulling in the
// incompatible UMD build. It throws if something ever actually tries to
// use it, so a real regression fails loudly instead of silently no-oping.
export class FaceDetection {
  constructor() {
    throw new Error(
      "@mediapipe/face_detection ('mediapipe' runtime) is not supported in this app — use runtime: 'tfjs'."
    );
  }
}
