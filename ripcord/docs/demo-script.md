# 90-second demo

**Before you start:** backend running (`MOCK_MODE=true` is fine, no mic and no API key needed), dashboard open at `http://localhost:8000` (or `:5173` in dev mode).

The dashboard has four tabs: **Live demo**, **Side by side**, **Benchmark**, **Playground**.

---

**0:00–0:10 — Hook** (any tab)
> "Voice agents can fail without crashing. One misheard number quietly becomes the wrong action."

**0:10–0:40 — Side by side** (tab 2)
- Pick a clip from the *recorded* group, for example **"Heard wrong in noise, caught and fixed"**.
- Press **Run both**.
- Left column (no checks): it accepts the wrong number and carries on. Right column (Ripcord): the digit strip shows which digits were weak, the risk bar crosses the threshold tick, and the workflow pauses with one targeted question.
> "Same audio, same recogniser. The left agent acts on the wrong number. The right one asks one question first."
- The caller's real recorded reply plays and the number is fixed.

**0:40–1:00 — Show it can fail honestly** (tab 2 again)
- Pick **"Heard wrong and Ripcord did NOT catch it (a miss)"** and press **Run both**.
> "A confidence check can't see a mistake the recogniser is sure about. We show these too."

**1:00–1:20 — Benchmark** (tab 3)
- Point at the headline numbers: wrong numbers acted on (plain agent vs Ripcord), mishearings caught, needless questions.
> "Held-out voices and held-out numbers, scored once. Confidence intervals are shown. The speech is synthetic and the recogniser is open-source, and the page says so."

**1:20–1:30 — Why it decides what it decides** (tab 4)
- In **Playground**, click **One shaky digit** and drag a confidence slider.
> "Every decision comes with its reasons, and no LLM makes the call."

---

**If you have an AssemblyAI key:** set `MOCK_MODE=false`, open the **Live demo** tab and press **Use real mic**. Say an order number and watch the same pipeline run on real streaming output.
