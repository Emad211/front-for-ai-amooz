# AI-Amooz Frontend Design Contract

## 0. Research Log

- Required references: `design/README.md`, `design/redesign-skill.md`, `perfection/README.md`, `designpowers/README.md`, and `designpowers/lane-c-review.md` were read before implementation.
- Existing-system extraction: reviewed `globals.css`, `tailwind.config.ts`, shadcn Button/Card/Select/Tabs, both advisory route pages, StudyLogForm, AnalyticsTab, StudyPlanCard, StudyFeedCard, GoalCard, MistakeLogCard, and TopicProgressCard.
- Product finding: the established language is semantic HSL tokens, green emphasis, Vazirmatn, soft rounded shadcn surfaces, and RTL-first composition. The redesign therefore changes hierarchy and density without introducing a second visual language.
- External visual research and concept imagery were skipped because this is a scoped redesign of an authenticated operational workflow, not a greenfield or reference-fidelity brief.

## 1. Atmosphere & Identity

AI-Amooz is a calm Persian study command surface: direct enough for a student checking the next task on a phone, and evidence-rich enough for an advisor making a decision on desktop. Its signature is **decision before data**: one emphasized next action, followed by progressively disclosed evidence and existing tools. The interface stays recognizably green/Vazirmatn/shadcn and avoids decorative dashboard density.

## 2. Color

### Palette

| Role | Token | Source | Usage |
|---|---|---|---|
| Page | `background` / `--background` | `globals.css` | App canvas |
| Primary text | `foreground` / `--foreground` | `globals.css` | Titles and body |
| Quiet text | `muted-foreground` / `--muted-foreground` | `globals.css` | Metadata and supporting copy |
| Surface | `card` / `--card` | `globals.css` | Grouped information and forms |
| Soft surface | `muted` / `--muted` | `globals.css` | Secondary controls and evidence rows |
| Action | `primary` / `--primary` | `globals.css` | One primary CTA, selected navigation, links |
| Destructive | `destructive` / `--destructive` | `globals.css` | Errors only |
| Structure | `border` / `--border` | `globals.css` | Dividers and card outlines |
| Focus | `ring` / `--ring` | `globals.css` | Keyboard focus |

### Rules

- Components use semantic Tailwind classes only; no raw hex, RGB, or new color names.
- Primary green indicates the current job or the screen's single primary action, never decoration.
- Status meaning always includes text or an icon; color is never the only signal.
- Dark mode uses the existing `.dark` token mapping. New surfaces must not hardcode light-only backgrounds.

## 3. Typography

### Scale

| Level | Tailwind role | Weight | Usage |
|---|---|---|---|
| Page title | `text-xl md:text-2xl` | 700 | Route heading |
| Section title | `text-base` | 600–700 | Decision and form sections |
| Card title | `text-sm` | 600 | Evidence and compact cards |
| Body | `text-sm` | 400 | Instructions and decisions |
| Supporting | `text-xs` | 400–500 | Evidence metadata and hints |

### Font Stack

- Primary and display: Vazirmatn, then sans-serif.
- Numeric evidence uses `tabular-nums`; no separate display font is introduced.

### Rules

- Product copy is Persian; code and technical documentation are English.
- Body copy uses relaxed leading and a readable measure. Labels stay visible and are not replaced by placeholders.
- Headings follow document order and use balanced wrapping where useful.

## 4. Spacing & Layout

### Base Unit

The existing Tailwind scale is treated as a 4px base system. Advisory work uses `gap-2/3/4/6`, `p-3/4/5/6`, and `space-y-2/3/4/6`; arbitrary visual pixel values are not introduced.

### Grid

- Content width: existing `max-w-6xl` shell; focused advisor records use `max-w-4xl`.
- Mobile: one readable column with 16px-equivalent page gutters.
- Tablet/desktop: two-column groups only when card roles are complementary.
- Primary navigation has at most four job destinations and may horizontally scroll on narrow screens without forcing page overflow.
- Fixed/sticky mobile CTAs reserve bottom space and respect `env(safe-area-inset-bottom)` when used.

### Interaction Size

- Every tab, primary action, select trigger, and icon-only action has a minimum 44px interactive size.
- Adjacent targets keep at least the existing `gap-2` separation.

## 5. Components

### Job Navigation

- **Structure**: Radix Tabs root/list/trigger/content controlled by the query parameter.
- **Variants**: student four-job navigation; advisor student-record four-job navigation.
- **Spacing**: `gap-1`, `p-1`, trigger horizontal `px-4`.
- **States**: active, hover, focus-visible, disabled; content receives a stable id and labelled tabpanel relationship from Radix.
- **Accessibility**: arrow-key semantics come from Radix; triggers are at least 44px; Persian aria labels identify the navigation purpose.
- **Motion**: color/opacity transitions only; no decorative entrance motion.
- **Layout**: horizontal cluster with overflow owned by its immediate wrapper.

### Decision Card

- **Structure**: semantic section/header, recommendation list, evidence references, and one primary action link.
- **Variants**: ready, loading skeleton, inactive, empty, error with retry.
- **Spacing**: outer `p-4/6`, recommendation stack `space-y-3`.
- **States**: distinct copy and iconography for each async state; an error never masquerades as empty.
- **Accessibility**: `aria-live=polite` for asynchronous replacement; links name their destination; recommendations remain readable without color.
- **Motion**: state replacement is immediate and stable; interactive links use existing transitions.
- **Layout**: stack on mobile; recommendation/evidence split may become two columns on large screens.

### Evidence Row

- **Structure**: label, formatted value, optional supporting detail.
- **Variants**: fact, unavailable/null.
- **Spacing**: compact `p-3`, `gap-2`.
- **Accessibility**: data remains text, not chart-only; long values wrap.
- **Layout**: responsive grid with no horizontal scrolling.

### Today Surface

- **Structure**: concise orientation header followed by StudyLogForm; save is the single primary CTA.
- **Variants**: loading, inactive, error, editable, saving, saved status.
- **Progressive disclosure**: supporting planning, analytics, exams, and profile tools live under the other three jobs rather than above today's action.
- **Accessibility**: save scope and latest status are visible text with `aria-live=polite`.

### Existing shadcn Primitives

- Button, Card, Select, Skeleton, Badge, and Radix Tabs remain the shared component layer.
- Their existing semantic token, focus, disabled, and dark-mode behavior is authoritative.

## 6. Motion & Interaction

| Type | Duration | Usage |
|---|---|---|
| Micro | existing `transition-colors` | Hover, focus, selected tabs |
| Async | no blocking animation | Loading to ready/error/empty replacement |
| Saving | existing spinner rotation | In-progress save only |

- Animation communicates state or affordance only.
- GPU-composited properties are the only animated properties.
- Existing `prefers-reduced-motion` handling in `globals.css` is preserved; no required information depends on animation.

## 7. Depth & Surface

The strategy is **mixed, restrained**: existing shadcn cards use a subtle border/shadow, while primary decision surfaces may use `bg-primary/5` plus `border-primary/20` for role emphasis. Nested evidence uses tonal `muted` or `background` shifts instead of additional shadows. Radius follows existing `rounded-xl` for inner controls and `rounded-2xl` for major advisory groups.

## 8. Accessibility Constraints & Accepted Debt

### Constraints

- Target WCAG 2.2 AA: 4.5:1 body text, 3:1 large text and UI boundaries.
- Full keyboard reachability and visible focus rings for tabs, links, selects, and buttons.
- Minimum 44px targets for the redesigned workflow.
- Complete tab semantics are delegated to Radix Tabs, including arrow keys, `aria-controls`, ids, and tabpanels.
- Async loading, empty, inactive, and error states are separate and announced appropriately.
- Layout must reflow at 375px without primary-content horizontal scroll.
- Persian RTL order is the source order; icons use Lucide and never replace labels.

### Personas

- **Student in a hurry**: reaches today's logging action immediately on a phone.
- **Student reviewing progress**: reaches plans, progress, exams, goals, and notes without losing old deep links.
- **Advisor making a decision**: sees deterministic recommendations first, then the facts and existing plan/exam evidence that support them.
- **Keyboard or low-vision user**: can identify current location, traverse tabs, and distinguish failure from absence without relying on color.

### Accepted Debt

| Item | Location | Why accepted | Owner / Exit |
|---|---|---|---|
| Some pre-existing advisory cards have controls below 44px and raw status colors. | Legacy cards grouped under Plan/Progress/Record | This task does not globally redesign unrelated card internals; the new navigation, decision surface, StudyLog selector and CTA meet the contract. | Consolidate during each card's next scoped redesign. |
| `advisory-service.ts` is an existing oversized service module. | `src/services/advisory-service.ts` | The repository mandates this service boundary and the task explicitly asks to add the endpoint there; splitting it would be an unrelated refactor. | Separate advisory service domains in a dedicated maintenance change. |
| Authenticated routes prevent reliable unauthenticated screenshot fidelity checks. | Advisory route QA | Build/type/diagnostic gates remain mandatory; browser QA requires a valid local authenticated fixture. | Exercise with seeded student/advisor accounts in the next integrated QA pass. |
