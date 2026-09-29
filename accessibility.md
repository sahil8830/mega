# Accessibility Rules (WCAG 2.1 AA)

## Semantic HTML — Always Required
- Use semantic elements: `<header>`, `<nav>`, `<main>`, `<section>`, `<article>`, `<footer>`, `<aside>`
- Every page must have exactly **one `<h1>`** with a proper heading hierarchy (h1 → h2 → h3)
- Never skip heading levels (e.g., h1 → h3 is NOT allowed)
- Use `<button>` for actions and `<a>` for navigation — never use `<div>` or `<span>` as clickable elements

## ARIA Labels
- Every interactive element must have an accessible name via:
  - Visible label text, OR
  - `aria-label="..."`, OR
  - `aria-labelledby="..."`
- Icon-only buttons MUST have `aria-label` (e.g., `<button aria-label="Close menu">`)
- Use `aria-expanded`, `aria-haspopup`, `aria-controls` for dropdowns and modals
- Use `role="alert"` or `aria-live="polite"` for dynamic content updates

## Color & Contrast
- Text contrast ratio must be **≥ 4.5:1** (normal text) or **≥ 3:1** (large text, ≥18px bold)
- Never convey information with color alone — always add an icon, label, or pattern
- Focus indicators must be clearly visible — never use `outline: none` without a custom focus style

## Keyboard Navigation
- ALL interactive elements must be reachable via Tab key
- Use logical `tabindex` — prefer `tabindex="0"` and avoid positive values
- Modals must trap focus when open and return focus on close
- Dropdown menus must support arrow key navigation

## Images & Media
- Every `<img>` must have an `alt` attribute:
  - Decorative images: `alt=""`
  - Informative images: descriptive alt text
- Videos must have captions or transcripts
- Avoid auto-playing audio or video with sound

## Forms
- Every `<input>`, `<select>`, and `<textarea>` must have an associated `<label>`
- Use `aria-describedby` for hint text and error messages
- Error messages must be programmatically associated with the field
- Required fields must be marked with `aria-required="true"` or `required`

## Motion & Animation
- Respect `prefers-reduced-motion` media query — wrap all animations:
  ```css
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      transition-duration: 0.01ms !important;
    }
  }
  ```
