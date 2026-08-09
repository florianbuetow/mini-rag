# Bradley-Terry "Strength" = Latent Difficulty

Note for later. What the strength `s_i` actually represents in the difficulty ranker.

In this Bradley-Terry setup, a task's strength `s_i` is its **latent difficulty** — the single hidden number the model assigns to each task that explains the pairwise comparison data.

## Why it's called "strength"

Bradley-Terry is a general model for paired competitions (originally for ranking sports teams or players), where the winner of each matchup has higher "strength." Here the framing is repurposed: the "winner" of a comparison is the **harder** task. So a task that keeps getting judged harder than its opponents accrues a higher strength — and in this context, **higher strength = harder**.

## Two clarifications so the mapping is precise

- **Strength vs. the reported difficulty score aren't literally the same number.** The raw `s_i` is a positive value the fit produces. The ranker then reports `difficulty_score` as the **centered log-strength** (`log s_i` minus the mean), which rescales the strengths into a tidier, comparable scale centered around zero. Same information, more readable — higher still means harder.
- **It's relative, not absolute.** A strength only has meaning compared to the other tasks in the set. It says "this task is harder than these, easier than those," not "this task is a 7/10 in some universal sense." That's different from the task evaluator's own difficulty score (1–5), which is an independent, self-contained rule/LLM estimate.

## Bottom line

Strength = the model's difficulty parameter for a task, learned from the "which is harder" comparisons, expressed on a relative scale.
