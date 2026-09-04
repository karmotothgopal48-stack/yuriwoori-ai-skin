# System Architecture

Seven layers, each with a single responsibility. Full narrative and diagrams in /docs.

1. **Frontend** — Next.js PWA, camera-first, mobile-first. Talks to backend only over HTTPS; never talks to CV/AI layers directly.
2. **Backend (FastAPI)** — orchestration, auth, session state, request routing. The only thing the frontend trusts.
3. **Computer Vision** — face detection/alignment/skin-region segmentation, lighting correction. Stateless inference service.
4. **AI / Modeling** — CNN/ViT skin-attribute models. Stateless, versioned, produces a structured Skin Profile only.
5. **Knowledge System** — product DB, ingredient DB, vector DB for RAG. Source of truth for Yuri AI and recommendations.
6. **Generative AI** — LLM layer for Yuri AI, routine explanations, shopping agent. Never invents product facts — always grounded via RAG.
7. **Business / Commerce** — Shopify Storefront API for product data, cart, checkout.

Cross-cutting: AWS infra, auth, storage, analytics, privacy controls wrap every layer.

See `/docs/diagrams/diagram-01-system-architecture.svg` for the visual, and `/docs/YuriWoori_AI_Skin_Intelligence.docx` for the full proposal.

## Design tokens
See `/docs/THEME.md` — all colors used anywhere in the app must come from that table.