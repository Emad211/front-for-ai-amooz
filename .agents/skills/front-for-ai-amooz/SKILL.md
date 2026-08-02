```markdown
# front-for-ai-amooz Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches the core development conventions and workflows used in the `front-for-ai-amooz` TypeScript codebase. The repository focuses on building a frontend (without a major framework) and emphasizes pixel-perfect alignment with Figma designs, consistent code style, and maintainable structure. You'll learn file naming, import/export patterns, commit conventions, and how to align UI with design specs.

## Coding Conventions

### File Naming
- **Pattern:** kebab-case
- **Example:**  
  `hero-section.tsx`, `why-us-section.tsx`

### Import Style
- **Pattern:** Use alias imports for modules.
- **Example:**
  ```typescript
  import { HeroSection } from '@/components/landing/sections/hero-section';
  ```

### Export Style
- **Pattern:** Named exports (avoid default exports).
- **Example:**
  ```typescript
  // hero-section.tsx
  export const HeroSection = () => { /* ... */ };
  ```

### Commit Messages
- **Pattern:** Conventional commits, mostly using the `fix` prefix.
- **Example:**  
  `fix: align hero section with latest Figma design`

## Workflows

### Align Landing Section with Figma
**Trigger:** When updating a landing page section to match the latest Figma design  
**Command:** `/align-landing-section-figma`

1. Open the relevant section component in `frontend/src/components/landing/sections/`.
2. Adjust layout, styles, and structure to match the Figma artboards.
3. Test responsiveness and visual fidelity across devices.
4. Commit your changes with a message referencing Figma alignment (e.g., `fix: align hero section with Figma`).

**Files commonly involved:**
- `hero-section.tsx`
- `why-us-section.tsx`
- `features-section.tsx`
- `testimonial-section.tsx`
- `teacher-cta-section.tsx`

**Example:**
```typescript
// Adjusting the Hero Section to match Figma
export const HeroSection = () => (
  <section className="hero">
    <h1 className="hero-title">Welcome to AI Amooz</h1>
    {/* ... */}
  </section>
);

// Commit message:
fix: align hero section with latest Figma design
```

## Testing Patterns

- **Framework:** Not explicitly detected.
- **File Pattern:** Test files are named with `.test.` in the filename.
- **Example:**  
  `hero-section.test.tsx`

**Typical Test File:**
```typescript
import { render } from '@testing-library/react';
import { HeroSection } from '@/components/landing/sections/hero-section';

test('renders hero section title', () => {
  const { getByText } = render(<HeroSection />);
  expect(getByText('Welcome to AI Amooz')).toBeInTheDocument();
});
```

## Commands

| Command                       | Purpose                                                        |
|-------------------------------|----------------------------------------------------------------|
| /align-landing-section-figma  | Align a landing page section with the latest Figma artboards   |
```
