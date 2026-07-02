---
description: تشکیل حلقه مشورتی تیم ایجنتیک روی یک موضوع (۳–۵ ایجنت موازی + جمع‌بندی — هزینه توکن دارد)
argument-hint: <موضوع یا سوال>
---

The user has EXPLICITLY convened the agent-team council on: **$ARGUMENTS**

You (the main session) are the facilitator. Follow this protocol exactly:

1. **Prepare.** Read `.claude/agents/README.md` (roster + consult matrix). Gather the concrete context
   the council needs (relevant file paths, recent commits, the feature doc if one exists) — councilors
   must receive pointers, not vague prose.
2. **Select 3–5 members** whose specialty matches the topic. `tech-lead` always participates and chairs
   (pure product topics: `product-manager` chairs instead). If the topic demands more than 5, STOP and
   ask the user before scaling up (token cost).
3. **Launch them IN PARALLEL** (one message, multiple Agent calls, `subagent_type` = the agent name).
   Each prompt contains: the topic, the gathered context/paths, that role's specific question, and the
   instruction to end with the team's standard handoff block (Decisions/Files/Docs/Risks/Consult next).
4. **Synthesize** (you, as facilitator):
   - **Agreements** → state as the team position.
   - **Disagreements** → name the exact trade-off; the chair's reasoning decides; record the dissent honestly.
   - **Unknowns** → what nobody could verify; how to find out.
5. **Deliver a decision memo to the user in Persian:** تصمیم، چرایی، مخالفت‌های ثبت‌شده، و اقدام بعدی هر نقش.
6. **Record.** If the decision is architectural or hard to reverse: write `docs/adr/ADR-NNNN-<slug>.md`
   (next free number, from `docs/adr/TEMPLATE.md`, Status: Accepted) BEFORE finishing, and mention the
   ADR path in the memo. Otherwise append the decision to the relevant `docs/features/<slug>.md`.

Never skip step 6 — an undocumented council decision violates the team's documentation law.
