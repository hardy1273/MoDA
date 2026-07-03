# MODA Frontend

Next.js 14 (App Router) + Tailwind CSS, built from the Figma wireframes.
Mobile-first phone canvas (430px) framed on a dark backdrop, like the artboards.

## Run

```bash
npm install
cp .env.local.example .env.local   # points at http://localhost:8000
npm run dev                        # http://localhost:3000
```

Works in two modes:

- **Live** — MODA backend running at `NEXT_PUBLIC_API_URL`: quiz posts to
  `/quiz`, the feed comes from `/recommendations`, likes/saves fire `/feedback`
  so the taste vector actually moves, closet reads `/saved`.
- **Demo** — backend unreachable: an 8-item demo catalog renders with mock
  explanations and a notice banner, so the UI is always demoable.

## Pages (mapped to wireframes)

| Route | Wireframe | Notes |
|---|---|---|
| `/` | iPhone 16-6 | Splash: M mark, tagline, Get started |
| `/signup` | 16-7 | Creates user via `POST /users`; password fields are visual stubs (no auth in MVP backend) |
| `/quiz` | 16-8, 16-9 | 4 steps (aesthetic, fit, layering, color) → editable summary → `POST /quiz`. "Layering: yes" maps to a `layered` fit on the backend |
| `/feed` | 16-4 | recommended-for-you grid, suggested theme, theme chips, like/save/add-to-cart per card |
| `/outfit/[id]` | 16-5 | back-to-feed, sizes (selected = oxblood, per the wireframe), Add to cart + price, like/save, **Why this design?** block |
| `/closet` | bottom nav | Saved pieces (backend `/saved` merged with local saves) |
| `/cart` | cart icon | Client-side cart; checkout button intentionally disabled ("coming soon") — commerce is stubbed per MVP scope |
| `/explore` | bottom nav | Full catalog without personalization |
| `/profile` | bottom nav | Username, taste profile quote, liked/saved counts, retake quiz, sign out |

## Design system

- **Colors:** ink `#0A0A0A` on paper white, mist `#F3F2EF` surfaces, hairline
  `#DCDAD4`, one signal color — oxblood `#7A1F1F` — reserved for liked hearts
  and the selected size (echoing the red size box in the wireframe).
- **Type:** Cormorant Garamond italic for editorial display moments
  ("Style profile", "Why this design?", the profile quote); Inter for UI.
- **Signature:** the line-drawn M logomark (inline SVG) and the editorial
  "Why this design?" block.
- Reduced motion respected; visible keyboard focus; aria-pressed on toggles.

## Wiring details

- Session, cart, likes, and saves persist in `localStorage`
  (`lib/store.tsx`); like/save also POST `/feedback` when a real user exists.
- `lib/api.ts` is the single integration point — every call degrades to demo
  mode, so backend-down never blanks the UI.
- Prices are a commerce stub (`outfit.price` is optional and defaulted) since
  the backend has no pricing yet; when you add a `price` column it flows
  straight through.

## Next steps

- Real auth (backend JWT + login page — the "Login." link is ready for it)
- Infinite scroll on the feed (paginate `k` + exclude seen)
- Dislike gesture (swipe-away) wired to `interaction_type: "dislike"`
- Checkout flow when commerce graduates from stub to feature
