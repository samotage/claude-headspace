---
name: 'SOP 01: workshop'
description: 'Reusable instruction block for collaborative workshop process'
---

# SOP 01: Workshop (Reusable Instruction Block)

**Purpose:** This is a reusable instruction block to embed into prompts or chat sessions. It guides a collaborative workshop process to refine instructions, requirements, or specifications, reducing assumptions and ensuring completeness before proceeding.

**Usage:** Copy and paste this entire block into your prompt or chat when you want to workshop and refine content with the AI assistant.

---

## Workshop Instruction Block

**Before proceeding with any implementation, planning, or analysis, follow this structured workshop process:**

### Phase 1: Understanding & Restatement

1. **Restate your understanding** of what is being requested in your own words. Be explicit about:

   - What is clearly stated
   - What is implied or inferred
   - What appears ambiguous or unclear

2. **Present this restatement** and ask: `CHECKPOINT 1: Does this restatement accurately capture your intent? [y,n]`

3. **If the answer is n**, incorporate corrections and repeat until understanding is confirmed.

### Phase 2: Assumption Identification

1. **Explicitly list all assumptions** you are making, organized by category:

   - **Technical assumptions**: About implementation approach, technologies, constraints
   - **Business logic assumptions**: About how the system should behave, rules, workflows
   - **User behavior assumptions**: About how users will interact, expectations, edge cases
   - **Context assumptions**: About existing code, dependencies, environment
   - **Scope assumptions**: About what is/isn't included, boundaries, priorities

2. **Present this assumption list** in a clear, structured format and ask: `CHECKPOINT 2: Please review these assumptions. Which are correct, which need correction, and what assumptions am I missing?`

3. **Update assumptions** based on feedback and confirm: `CHECKPOINT 3: Are all assumptions now correct and complete? [y,n]`

### Phase 3: Gap Analysis

1. **Identify missing details** by asking structured questions about:

   - **Edge cases**: What should happen in unusual or error scenarios?
   - **Constraints**: Are there performance, security, or compatibility requirements?
   - **Validation**: What should be validated, and how?
   - **Dependencies**: What other parts of the system are involved?
   - **Testing**: What tests need to exist or be updated?
   - **Documentation**: What documentation needs to be created or updated?

2. **Present your gap analysis** as a structured list of questions and areas needing clarification.

3. **Iteratively refine** through Q&A until all critical gaps are addressed.

4. Confirm: `CHECKPOINT 4: Have all critical gaps been addressed? [y,n]`

### Phase 4: Completeness Validation

1. **Summarize the refined understanding** including:

   - Clear requirements/instructions
   - Validated assumptions
   - Resolved gaps
   - Scope boundaries
   - Success criteria

2. **Present a completeness checklist**:

   - [ ] All assumptions identified and validated
   - [ ] All critical gaps addressed
   - [ ] Edge cases considered
   - [ ] Constraints identified
   - [ ] Scope clearly defined
   - [ ] Success criteria established

3. **Ask for final confirmation**: `CHECKPOINT 5: Is this understanding complete and accurate? [y,n]`

### Phase 5: Final Refined Output

1. **Present the final refined version** in a clearly marked, reusable format that can be:

   - Copied into future prompts
   - Saved as documentation
   - Used as the basis for implementation

2. Format the output as:

```
## Refined [Type of Content - e.g., Instructions/Requirements/Specification]

[The complete, refined content with all assumptions validated and gaps filled]

### Validated Assumptions
- [Category]: [Assumption 1]
- [Category]: [Assumption 2]
...

### Resolved Gaps
- [Gap 1]: [Resolution]
- [Gap 2]: [Resolution]
...

### Scope Boundaries
- Included: [What is in scope]
- Excluded: [What is out of scope]

### Success Criteria
- [Criterion 1]
- [Criterion 2]
...
```

3. Only after presenting the refined output and receiving confirmation, proceed with any implementation, planning, or analysis.

---

## Guidelines for the Workshop Process

- **Be explicit, not inferential**: State assumptions clearly rather than silently assuming
- **Ask specific questions**: "What should happen when X?" rather than "Is everything clear?"
- **Iterate until complete**: Don't proceed with incomplete understanding
- **Document assumptions**: Keep a clear record of what was assumed/validated
- **Prioritize clarity**: Better to ask too many questions than make incorrect assumptions

## When to Use This Block

- Before starting implementation of a new feature or change
- When refining requirements or specifications
- When reviewing instructions that seem ambiguous
- Before creating detailed plans or proposals
- Whenever you want to ensure complete understanding before proceeding

---

**Note:** This instruction block should be embedded into your prompt or chat context. The AI assistant should follow this process before proceeding with any substantive work.

---

**SOP 01 complete.**
