# submission/

> **Note:** this file describes the original hackathon version (v1: hand-tuned rules, 10 authored scenarios). It was not rewritten for v2, so numbers like "22 tests" and "1/10 → 0/10" are out of date. Current results: [`docs/evaluation.md`](../docs/evaluation.md) and the top-level README.

Assets for the lablab.ai submission form. See [`../docs/submission.md`](../docs/submission.md) for the copy-paste form fields and pre-submit checklist.

- **`ripcord-pitch-deck.pptx`** — editable source. Fill in the bracketed placeholders (name, GitHub URL, live demo URL, email) on the title and close slides before exporting.
- **`ripcord-pitch-deck.pdf`** — the PDF lablab.ai's form expects. Regenerate after editing the `.pptx`:
  ```bash
  soffice --headless --convert-to pdf ripcord-pitch-deck.pptx
  ```
  (Or, from a fresh checkout without LibreOffice installed globally: `python3 /mnt/skills/public/pptx/scripts/office/soffice.py --headless --convert-to pdf ripcord-pitch-deck.pptx` if you have this skill's scripts on hand — otherwise any PowerPoint/Keynote/LibreOffice "Export as PDF" works.)
- **`build-deck.js`** — the `pptxgenjs` script that generated the deck from scratch. Useful if you want to change colors, add a slide, or regenerate after a bigger edit than swapping placeholder text. Requires Node with `pptxgenjs` installed (`npm install pptxgenjs`), then `node build-deck.js`.
