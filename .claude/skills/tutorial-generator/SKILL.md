---
name: tutorial-generator
description: Generate the next lesson in the docs/NN.md series by capturing what was built and the reasoning since the last tutorial. Use when the user says "生成教程", "写新一课", "summarize this into a tutorial", or asks to document the development journey since the previous lesson.
---

# Tutorial Generator Skill

## Goal

Produce the next numbered lesson in the project's docs/ series (e.g., `docs/02.md` after `docs/01.md`), capturing:

- **What was built** since the last lesson
- **The reasoning process** behind each decision (questions asked, alternatives considered)
- **Decisions NOT made**, with reasons
- **Deep insights** surfaced during the work

The reader is **an agent that loads the doc to continue building**, not a human typing along on a keyboard.

## When to invoke

User phrases that should trigger this skill:
- "生成教程"
- "写新一课"
- "summarize the journey into a lesson"
- "把刚才的过程记录一下"
- "把从上次教程到现在的内容写成新一课"

## Steps

1. **Find the latest lesson** in `docs/`:
   ```bash
   ls docs/*.md | sort -V
   ```
   Identify the highest `NN` in `NN.md` naming; the new file is `docs/{NN+1}.md`.

2. **Anchor style**: Read the latest lesson to internalize the established format. Conventions are not invented per-lesson — they evolve incrementally from prior lessons.

3. **Identify the gap**: What's been built/changed since the previous lesson?
   - `git log --since=<date-of-previous-lesson>` for commits
   - Diff of files (added/modified/deleted)
   - Conversation history for the reasoning chain
   - New tests, configs, schemas, doc files

4. **Extract the reasoning chain**, not just the artifacts:
   - What question surfaced the next step?
   - What alternatives were considered?
   - Why was a particular path chosen?
   - What was tried and rolled back?
   - What insights emerged?

5. **Write `docs/{NN+1}.md`** following the conventions established in `docs/01.md`:

   - **Sections by development stage**, in chronological order
   - Each section: 做了什么 (what) / 为什么 (why) / 认知 (insight)
   - A final **"横向总结：做过 / 没做 + 理由"** table
   - **Callout boxes** for deep insights using this exact form:
     ```
     > ★ **关键洞察：**
     > 
     > One to three sentences capturing a non-obvious takeaway.
     ```
   - Cross-link to actual code files in the repo
   - Length: ~250–500 lines (not exhaustive — assume the reader can read files)

6. **Skip these entirely**:
   - API documentation the model already knows
   - "How to install / set up" steps
   - Verbose code snippets (link to files instead)
   - "Try it yourself" tutorial walk-through
   - Restating what `docs/01.md` already said

7. **Open the new lesson with a forward/back pointer** — make it clear what came before and what this continues.

## Writing philosophy (non-negotiable)

These rules are the user's hard requirements. Skill-loaded agents must follow them.

### The reader is an agent, not a tutorial-following human
- Write so that an LLM loading the doc can think through what's next, decide what's missing, and execute on the gaps.
- Don't optimize for "human readability line by line"; optimize for "structure + decisions visible at a glance".

### Process skeleton > technical detail
- The chain of questions and decisions is the value. Code is incidental.
- A reader who already knows Python/HTTP/SQL doesn't need to be re-taught them.

### Always surface what was NOT done
- For every meaningful capability you didn't build in this lesson, write down WHY it was deferred.
- This prevents future agents from re-deciding the same thing without context.

### Insights get callouts
- "I noticed X" or "this surprised me" deserves `> ★` — not buried in paragraphs.

### Decisions are explicit
- "We chose X over Y because Z" — not "we built X".

### Keep it skeletal
- A long doc is a doc no one reads. If you can't fit a stage in 60 lines, split it.

## Output structure template

```
# 第N课：[标题]

> One sentence: what this lesson covers, and what it continues from 第N-1课.

## 引子（可选，若需要破冰）
## 阶段 1：[chrono step name]
### 做了什么
### 为什么
### 这一步的认知
> ★ [callout if applicable]
## 阶段 2：[...]
...
## 横向总结：做过 / 没做 + 理由
| 我们做了 | 为什么 |
| 我们没做 | 为什么本课不做 |
## 写在最后 (optional): hooks for next lesson
```

The "hooks for next lesson" section is **optional and minimal** — do not over-plan. One or two sentences is enough.

## Anti-patterns to avoid

- ❌ Re-teaching things the model already knows (JSON syntax, HTTP basics, SDK usage)
- ❌ Long code excerpts (link to files; trust the reader)
- ❌ "Congratulations, you made it!" conclusions
- ❌ Step-by-step "Now do X, then Y, then Z" instructions
- ❌ Explaining what tools are — unless the lesson's job is meta-discussion of tooling
- ❌ Restating lessons from prior `NN.md` files

## File operations

This skill **writes to `docs/`** in the repo. It does not modify code or config. If the user wants the lesson committed, ask once after writing — but do not push without explicit instruction.
