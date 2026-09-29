# Testing Rules

## General Principles
- Write tests alongside code — not as an afterthought
- Follow the **Testing Pyramid**: many unit tests, fewer integration tests, few E2E tests
- Tests must be **deterministic** — never depend on external APIs or random data in unit tests
- Use **mock data** and **factories** for test isolation

## Unit Tests (Vitest)
- Test file location: `src/components/<Name>/<Name>.test.jsx` or `src/utils/<name>.test.js`
- Every utility function must have unit tests covering:
  - Happy path (expected input)
  - Edge cases (empty, null, boundary values)
  - Error cases
- Use `describe` blocks to group related tests
- Use `it` or `test` with descriptive names: `it('should return empty array when input is null')`

## Component Tests (Vitest + React Testing Library)
- Test components through the **user's perspective** — query by role, label, text
- Preferred query order: `getByRole` → `getByLabelText` → `getByPlaceholderText` → `getByText`
- Never query by `className` or `id` — tests should be implementation-agnostic
- Test user interactions with `userEvent` (not `fireEvent`)
- Mock API calls — never make real network requests in component tests

## Integration Tests
- Test complete user flows (e.g., form fill → submit → success state)
- Use React Testing Library's `render` with a full provider tree (Router, QueryClient, etc.)

## E2E Tests (Playwright)
- E2E test location: `e2e/` at the project root
- Cover critical user journeys only:
  - User registration / login
  - Core product workflows
  - Checkout or conversion paths
- Use `data-testid` attributes on interactive elements for E2E selectors
- Run E2E tests against a staging environment, not production

## Coverage Targets
- **Unit/Integration**: ≥ 80% line coverage for utility functions
- **Components**: cover all interactive states (loading, error, empty, success)
- Run coverage with: `npx vitest run --coverage`

## Test Commands
```bash
npx vitest              # watch mode
npx vitest run          # single run (CI)
npx vitest run --coverage   # with coverage report
npx playwright test     # E2E tests
npx playwright test --ui    # E2E with visual runner
```
