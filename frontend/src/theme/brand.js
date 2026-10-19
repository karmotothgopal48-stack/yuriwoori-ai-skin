// YuriWoori Brand Book v1.2 tokens (for SVG / inline styles; CSS uses @theme in index.css)
export const BRAND = {
  deepJade: "#006968",
  softJade: "#9DD4CA",
  jadeLine: "#BDDCCD",
  mist: "#E3ECEB",
  sage: "#47705F",
  cream: "#F1F5EB",
  aqua: "#D5EEE7",
  white: "#FFFFFF",
};

// Official logo files live in public/assets (source: yuriwoori.com GREEN_LOGO.png; white/cropped derivatives).
export const IMAGES = {
  // Provided reference visual for the AI Skin Analysis experience (public/assets)
  analysisFace: "/assets/ai-skin-analysis-face.png",
};

// AI Skin Analysis campaign portraits: text-free crops of YuriWoori's own campaign photo
// (yuriwoori.com/cdn/shop/files/570x830-px-for-shopify-2.webp), studio pink background retouched to ivory,
// so every screen shows the same model and look. To swap in a new photo, replace the file and move the
// overlay points/labels (percent of the 4:5 image box) onto the new face.
const CAMPAIGN_ALT = "YuriWoori model with glowing, natural skin";
export const PORTRAITS = {
  hero: {
    src: "/assets/hero-portrait.webp", width: 960, height: 1200, alt: CAMPAIGN_ALT,
    points: [{ x: 64, y: 28 }, { x: 75, y: 44 }, { x: 65, y: 47 }, { x: 63, y: 58 }], // forehead, cheek, nose, chin
    labels: [
      { text: "Texture · Tone", pos: { left: "7%", top: "20%" } },
      { text: "Hydration", pos: { right: "5%", top: "34%" } },
    ],
  },
  permission: {
    src: "/assets/permission-portrait.webp", width: 800, height: 1000, alt: CAMPAIGN_ALT,
    points: [{ x: 57, y: 32 }, { x: 70, y: 52 }, { x: 60, y: 57 }, { x: 57, y: 69 }], // forehead, cheek, nose, chin
    labels: [
      { text: "Hydration", pos: { right: "4%", top: "60%" } },
      { text: "Even tone", pos: { left: "6%", top: "18%" } },
    ],
  },
};

export const LOGO = {
  // Exact logo file supplied by the client (opaque white background: use on white only)
  provided: "/assets/yuriwoori-logo-provided.png",
  lockupGreen: "/assets/yuriwoori-logo-green.png",
  lockupWhite: "/assets/yuriwoori-logo-white.png",
  wordmarkGreen: "/assets/yuriwoori-wordmark-green.png",
  heartGreen: "/assets/yuriwoori-heart-green.png",
  heartWhite: "/assets/yuriwoori-heart-white.png",
};
