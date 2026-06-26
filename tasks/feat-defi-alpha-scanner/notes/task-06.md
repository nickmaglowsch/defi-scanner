# Task 06: Capital Simulator Context + Provider

- **Decisions**: SSR guard via "initialize to default, hydrate in effect" pattern — avoids the mounted-boolean dance and matches Next.js docs guidance for localStorage. The `CapitalContext` default value uses `DEFAULT_CAPITAL` so any component consuming `useCapital` outside the provider still gets a sane number rather than 0 or undefined.
- **Deviations**: None.
- **Trade-offs**: `CapitalProvider` is a `"use client"` component mounted at the root layout body. This is the standard App Router pattern for wrapping all routes with client state; the layout itself remains a server component.
- **Risks**: `Input` from `@base-ui/react/input` does not natively clamp to `min`; the `onChange` guard (`v >= 0`) prevents negative values from being stored, but the native `min` attribute on the `<input>` only affects form validation UI. Reviewer should verify UX is acceptable for the capital input field.
