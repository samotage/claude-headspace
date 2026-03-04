## Product Requirements Document (PRD) — Voice App Kebab Menus

**Project:** Claude Headspace
**Scope:** Add kebab menus to the voice app for agent chat and channel chat views
**Author:** Robbo (architect)
**Status:** Draft

---

## Executive Summary

The voice app (`/voice`) is the primary interaction interface for Claude Headspace — it's where users chat with agents and participate in group channel conversations. Despite this, it lacks the contextual action menus (kebab menus) that already exist on the dashboard's agent cards and channel chat panel.

This PRD addresses that gap. Kebab menus must be added to the voice app for both agent chat and channel chat contexts, carrying context-appropriate actions ported from their dashboard equivalents. These menus serve as the UI surface for current and future actions, including the forthcoming transcript download feature.

---

## 1. Context & Purpose

### 1.1 Context
The dashboard currently has kebab menus on agent cards (7 actions including dismiss, chat, attach, context, info, reconcile, handoff) and on the channel chat panel (6 actions including add-member, info, complete, end, copy-slug, leave). The voice app has no equivalent menus, meaning users interacting through the primary chat interface have no access to these actions without switching to the dashboard.

This gap was likely caused by the kebab menus being built in the dashboard context without considering that the voice app is the primary interaction surface.

### 1.2 Target User
The operator — the person actively chatting with agents and participating in group channel conversations through the voice app.

### 1.3 Success Moment
The user is in a voice app conversation and needs to perform an action (e.g., dismiss an agent, leave a channel, download a transcript). They tap the kebab menu and find the action right there, without switching to the dashboard.

---

## 2. Scope

### 2.1 In Scope
- Kebab menu in voice app agent chat view with context-appropriate actions
- Kebab menu in voice app channel chat view with context-appropriate actions
- Actions ported from existing dashboard kebab menus, adapted to voice app context
- Each context (agent chat vs channel chat) has its own set of relevant actions
- Menus are accessible and functional on both desktop and mobile/tablet viewports

### 2.2 Out of Scope
- Modifying or redesigning existing dashboard kebab menus
- Adding new actions beyond what the dashboard already supports (new actions like transcript download will be added by their own PRDs)
- Changes to the dashboard UI
- Voice input or voice-specific actions

---

## 3. Success Criteria

### 3.1 Functional Success Criteria
1. Voice app agent chat view has a kebab menu accessible from the chat header/toolbar
2. Voice app channel chat view has a kebab menu accessible from the chat header/toolbar
3. Agent chat kebab menu contains actions relevant to agent interaction (dismiss, attach, context info, agent info, reconcile, handoff — as appropriate to voice app context)
4. Channel chat kebab menu contains actions relevant to channel participation (add member, channel info, complete, end, copy slug, leave — as appropriate to user's role)
5. Chair-only actions (complete, end) are only visible to the channel chair
6. Destructive actions (dismiss, end channel) require confirmation before executing
7. Menus close when an action is selected or when the user taps/clicks outside

### 3.2 Non-Functional Success Criteria
1. Menus are usable on touch devices (minimum 44px tap targets)
2. Menus do not interfere with chat message scrolling or input

---

## 4. Functional Requirements (FRs)

**FR1:** The voice app agent chat view shall display a kebab menu trigger (three-dot icon) in the chat header area.

**FR2:** Activating the agent chat kebab menu shall display a dropdown with actions relevant to the current agent session, including but not limited to: dismiss agent, attach to session, view context usage, view agent info, trigger reconciliation, and initiate handoff (where applicable).

**FR3:** The voice app channel chat view shall display a kebab menu trigger (three-dot icon) in the chat header area.

**FR4:** Activating the channel chat kebab menu shall display a dropdown with actions relevant to channel participation, including but not limited to: add member, view channel info, mark complete, end/archive channel, copy channel slug, and leave channel.

**FR5:** Actions that are role-restricted (e.g., complete and end channel are chair-only) shall only be visible to users with the appropriate role.

**FR6:** Destructive actions (dismiss agent, end channel, handoff) shall require user confirmation before executing.

**FR7:** The kebab menu shall close when an action is selected, when the user clicks/taps outside the menu, or when the Escape key is pressed.

**FR8:** The kebab menus shall be extensible — additional actions can be added by future features without restructuring the menu component.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** Kebab menu items shall have a minimum tap target of 44px for touch device usability.

**NFR2:** The kebab menu shall not cause layout shifts or interfere with chat message display or input controls.

**NFR3:** Menu appearance and behaviour shall be consistent between agent chat and channel chat contexts (same visual style, same interaction patterns, different action sets).

---

## 6. UI Overview

The kebab menu trigger (three-dot vertical icon) appears in the chat header/toolbar area of both the agent chat and channel chat views within the voice app. Tapping/clicking the trigger opens a dropdown menu positioned below or adjacent to the trigger, listing available actions with icons and labels. Destructive actions are visually differentiated (e.g., red text). A divider separates destructive actions from non-destructive ones. The menu dismisses on action selection, outside click, or Escape key.
