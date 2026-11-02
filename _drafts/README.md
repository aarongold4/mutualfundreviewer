# _drafts/ — guides awaiting your Publish/Discard

The daily audit writes each new guide here as `<slug>.html` (same `{#META … META#}`
+ body format as `templates/guides/`). **`build.py` never reads this folder**, so a
draft sitting here is committed to the repo but is NOT on the live site.

Flow (all in Claude — you never touch GitHub):
- **Daily audit** drafts a guide here and alerts you with the rendered draft to read.
- **Publish:** reply "publish" (Claude fires the Write & Publish task) or press *Run now*
  on "mutualfundreviewer.com: Write & Publish Article Ideas". That moves the draft into
  `templates/guides/`, re-verifies its facts, rebuilds, and deploys.
- **Discard:** reply "discard &lt;slug&gt;" — the draft is deleted and the idea marked discarded.

Nothing in here is ever published without that explicit step.
