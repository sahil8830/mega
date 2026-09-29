# Frontend Performance Rules

## Images
- Always use `loading="lazy"` on images below the fold
- Use `width` and `height` attributes on `<img>` to prevent layout shift (CLS)
- Use modern formats: **WebP** for photos, **SVG** for icons and illustrations
- Use `srcset` and `sizes` for responsive images
- Compress images before including them — target < 200KB for hero images

## Code Splitting & Lazy Loading
- Lazy-load route-level components with React's `React.lazy()` + `Suspense`
- Never import entire libraries when only one function is needed:
  - ❌ `import _ from 'lodash'`
  - ✅ `import debounce from 'lodash/debounce'`
- Dynamically import heavy components (modals, charts, editors) that aren't needed on load

## CSS Performance
- Avoid `@import` in CSS — use `<link>` tags instead
- Minimize use of universal selectors (`*`) in hot paths
- Use `will-change: transform` only when animating — remove after animation ends
- Prefer `transform` and `opacity` for animations — they are GPU-accelerated
- Avoid layout-triggering CSS properties in animations: `width`, `height`, `margin`, `top`, `left`

## JavaScript Performance
- Debounce scroll and resize event handlers
- Use `useCallback` and `useMemo` in React only when there's a measurable performance benefit
- Avoid inline object/array literals in JSX that cause unnecessary re-renders
- Use `React.memo` for pure components that receive stable props

## Rendering
- Avoid blocking the main thread — move heavy computation to Web Workers
- Use virtualization (`react-window` or `react-virtual`) for lists with > 100 items
- Minimize DOM nodes — target < 1500 total DOM elements per page

## Web Vitals Targets (Core Web Vitals)
- **LCP** (Largest Contentful Paint): < 2.5 seconds
- **FID** (First Input Delay): < 100ms
- **CLS** (Cumulative Layout Shift): < 0.1
- **FCP** (First Contentful Paint): < 1.8 seconds
- **TTFB** (Time to First Byte): < 800ms

## Fonts
- Always use `font-display: swap` for web fonts
- Preconnect to font origins: `<link rel="preconnect" href="https://fonts.googleapis.com">`
- Limit font weights — load only the weights actually used

## Network
- Enable HTTP/2 on the server
- Use CDN for static assets
- Set appropriate Cache-Control headers for immutable assets
- Preload critical assets: `<link rel="preload" as="font" ...>`
