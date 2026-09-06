import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  turbopack: {
    resolveAlias: {
      // See src/lib/mediapipe-face-detection-shim.ts for why this is needed.
      "@mediapipe/face_detection": "./src/lib/mediapipe-face-detection-shim.ts",
    },
  },
};

export default nextConfig;
