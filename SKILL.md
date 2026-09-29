---
name: new-frontend-project
description: >-
  Scaffolds a new React + Vite frontend project with a premium design system,
  Google Fonts, CSS variables, and folder structure. Use when the user wants
  to start a new frontend app or website from scratch.
---

# New Frontend Project Workflow

## Steps

1. **Run Vite scaffold** in the target directory:
   ```bash
   npx -y create-vite@latest ./ --template react
   npm install
   ```

2. **Set up Google Fonts** in `index.html`:
   ```html
   <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
   ```

3. **Replace `src/index.css`** with a full design system:
   - CSS custom properties (colors, spacing, typography, shadows, radii)
   - Dark mode via `[data-theme="dark"]`
   - CSS reset and base styles
   - Utility classes

4. **Create folder structure:**
   ```
   src/
   ├── components/     ← reusable UI components
   ├── pages/          ← page-level components
   ├── hooks/          ← custom React hooks
   ├── assets/         ← images, icons
   └── utils/          ← helper functions
   ```

5. **Update `App.jsx`** with the design system and routing structure

6. **Run dev server:**
   ```bash
   npm run dev
   ```

## Design System Tokens (index.css starter)

```css
:root {
  --font-primary: 'Inter', sans-serif;
  --font-display: 'Outfit', sans-serif;

  --color-bg: #0a0a0f;
  --color-surface: #13131a;
  --color-surface-2: #1e1e2e;
  --color-border: rgba(255, 255, 255, 0.08);
  --color-primary: #6c63ff;
  --color-primary-glow: rgba(108, 99, 255, 0.3);
  --color-accent: #ff6b9d;
  --color-text: #e8e8f0;
  --color-text-muted: #8888aa;

  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-6: 1.5rem;
  --space-8: 2rem;
  --space-12: 3rem;
  --space-16: 4rem;

  --radius-sm: 6px;
  --radius-md: 12px;
  --radius-lg: 20px;
  --radius-full: 9999px;

  --shadow-sm: 0 2px 8px rgba(0,0,0,0.3);
  --shadow-md: 0 4px 24px rgba(0,0,0,0.4);
  --shadow-lg: 0 8px 40px rgba(0,0,0,0.5);
  --shadow-glow: 0 0 40px var(--color-primary-glow);
}
```
