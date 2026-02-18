# Objective

The Objective feature lets you set a global priority that influences how agents are ranked on the dashboard.

## What is an Objective?

An objective is a short statement describing your current focus. For example:

- "Ship the authentication feature"
- "Fix critical bugs before release"
- "Refactor the database layer"

## Setting an Objective

1. Click **Objective** in the navigation
2. Enter your objective text in the input field
3. Click **Save** or press Enter

The objective is saved to `config.yaml` and used to calculate agent priority scores.

## How Objectives Affect Priority

Agents whose commands align with the objective receive higher priority scores. This means:

- Relevant agents appear higher in the priority-sorted view
- The recommended next agent reflects your current focus
- You can quickly identify which agents are working on your priority

## Clearing an Objective

To clear the objective, simply delete the text and save. Without an objective, agents are sorted by their base priority (activity level).

## Best Practices

- Keep objectives short and specific
- Update regularly as your focus changes
- Use action-oriented language ("Ship", "Fix", "Implement")
