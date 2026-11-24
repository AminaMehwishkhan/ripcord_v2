const pptxgen = require("pptxgenjs");

// Ocean Gradient palette, tuned to match Ripcord's own product UI (cyan/navy).
const NAVY = "0B1220";
const MIDNIGHT = "21295C";
const DEEPBLUE = "065A82";
const TEAL = "1C7293";
const CYAN = "34D9D9";
const LIGHT_BG = "F4F7FB";
const TEXT_DARK = "111827";
const MUTED = "5B6B85";
const WHITE = "FFFFFF";
const RED = "E0546B";
const GREEN = "2FBF8F";
const AMBER = "E8A93D";

function newPres() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.3 x 7.5
  return pres;
}

function darkSlide(pres) {
  const s = pres.addSlide();
  s.background = { color: NAVY };
  return s;
}
function lightSlide(pres) {
  const s = pres.addSlide();
  s.background = { color: LIGHT_BG };
  return s;
}

function kicker(s, text, x, y, color) {
  s.addText(text.toUpperCase(), {
    x, y, w: 6, h: 0.35, isTextBox: true, margin: 0,
    fontFace: "Calibri", fontSize: 12, bold: true, color: color || CYAN,
    charSpacing: 2,
  });
}

const pres = newPres();

// ---------- Slide 1: Title ----------
{
  const s = darkSlide(pres);
  s.addShape(pres.ShapeType.rect, { x: 0, y: 0, w: 13.33, h: 7.5, fill: { color: NAVY } });
  s.addShape(pres.ShapeType.ellipse, { x: 9.6, y: -2.2, w: 7, h: 7, fill: { color: MIDNIGHT }, line: { type: "none" } });
  s.addShape(pres.ShapeType.ellipse, { x: 11.2, y: -0.6, w: 4, h: 4, fill: { color: DEEPBLUE }, line: { type: "none" } });

  s.addText("RIPCORD", {
    x: 0.9, y: 2.35, w: 9.5, h: 1.5, isTextBox: true, margin: 0,
    fontFace: "Cambria", fontSize: 60, bold: true, color: WHITE, charSpacing: 1,
  });
  s.addText("Real-Time Self-Repair for Voice Agents", {
    x: 0.95, y: 3.55, w: 9, h: 0.6, isTextBox: true, margin: 0,
    fontFace: "Calibri", fontSize: 24, color: CYAN, bold: true,
  });
  s.addText("Catch the misunderstanding before it becomes an action.", {
    x: 0.95, y: 4.15, w: 8.5, h: 0.5, isTextBox: true, margin: 0,
    fontFace: "Calibri", fontSize: 16, italic: true, color: "AEB9D4",
  });

  s.addText("AssemblyAI Voice Agent Hackathon 2026  ·  lablab.ai", {
    x: 0.95, y: 6.05, w: 8, h: 0.4, isTextBox: true, margin: 0,
    fontFace: "Calibri", fontSize: 13, color: "AEB9D4",
  });
  s.addText("Built by [Your Name]  ·  Solo entry", {
    x: 0.95, y: 6.45, w: 8, h: 0.4, isTextBox: true, margin: 0,
    fontFace: "Calibri", fontSize: 13, color: "AEB9D4",
  });
}

// ---------- Slide 2: Problem ----------
{
  const s = lightSlide(pres);
  kicker(s, "The problem", 0.7, 0.55, TEAL);
  s.addText("Voice agents fail without crashing", {
    x: 0.7, y: 0.9, w: 11.5, h: 0.8, isTextBox: true, margin: 0,
    fontFace: "Cambria", fontSize: 34, bold: true, color: TEXT_DARK,
  });
  s.addText(
    "The dangerous failure isn't a crash — it's an agent that responds smoothly, sounds confident, and quietly acts on the wrong number.",
    { x: 0.7, y: 1.65, w: 7.6, h: 0.9, isTextBox: true, margin: 0, fontFace: "Calibri", fontSize: 15, color: MUTED }
  );

  const rows = [
    ["Nothing crashes", "The call flows naturally end to end — no error, no red flag."],
    ["The transcript looks fine", "\u201cOne five eight zero\u201d becomes \u201cone five zero.\u201d Plausible either way."],
    ["The wrong action executes", "Wrong order looked up, wrong booking confirmed — nobody notices until later."],
  ];
  let ry = 2.85;
  rows.forEach(([title, body], i) => {
    s.addShape(pres.ShapeType.ellipse, { x: 0.7, y: ry, w: 0.5, h: 0.5, fill: { color: [DEEPBLUE, TEAL, RED][i] }, line: { type: "none" } });
    s.addText(String(i + 1), { x: 0.7, y: ry, w: 0.5, h: 0.5, isTextBox: true, margin: 0, align: "center", valign: "middle", fontFace: "Calibri", fontSize: 16, bold: true, color: WHITE });
    s.addText(title, { x: 1.4, y: ry - 0.05, w: 6.8, h: 0.4, isTextBox: true, margin: 0, fontFace: "Calibri", fontSize: 16, bold: true, color: TEXT_DARK });
    s.addText(body, { x: 1.4, y: ry + 0.35, w: 6.8, h: 0.5, isTextBox: true, margin: 0, fontFace: "Calibri", fontSize: 12.5, color: MUTED });
    ry += 1.15;
  });

  // Big stat callout, right side
  s.addShape(pres.ShapeType.roundRect, { x: 8.7, y: 2.0, w: 3.9, h: 3.7, fill: { color: MIDNIGHT }, line: { type: "none" }, rectRadius: 0.12 });
  s.addText("1 / 10", { x: 8.9, y: 2.3, w: 3.5, h: 1.1, isTextBox: true, margin: 0, align: "center", fontFace: "Cambria", fontSize: 56, bold: true, color: CYAN });
  s.addText("critical order numbers silently misheard", { x: 9.0, y: 3.35, w: 3.3, h: 0.7, isTextBox: true, margin: 0, align: "center", fontFace: "Calibri", fontSize: 13, color: WHITE });
  s.addText("in our authored test corpus — with no reliability layer to catch it.", { x: 9.05, y: 4.15, w: 3.2, h: 1.2, isTextBox: true, margin: 0, align: "center", fontFace: "Calibri", fontSize: 11, italic: true, color: "AEB9D4" });
}

// ---------- Slide 3: Solution ----------
{
  const s = darkSlide(pres);
  kicker(s, "The solution", 0.7, 0.5);
  s.addText("Verify before you act", {
    x: 0.7, y: 0.85, w: 10, h: 0.8, isTextBox: true, margin: 0,
    fontFace: "Cambria", fontSize: 32, bold: true, color: WHITE,
  });
  s.addText(
    "Ripcord treats every critical numeric entity as unverified until proven otherwise — scored on explainable signals, never a black box.",
    { x: 0.7, y: 1.55, w: 10.5, h: 0.6, isTextBox: true, margin: 0, fontFace: "Calibri", fontSize: 14, color: "AEB9D4" }
  );

  // Flow diagram
  const boxY = 2.7, boxH = 1.0;
  const steps = [
    { x: 0.7, w: 2.3, label: "Critical entity\ncaptured", color: DEEPBLUE },
    { x: 3.5, w: 2.5, label: "Risk engine\n(explainable score)", color: TEAL },
  ];
  steps.forEach((st) => {
    s.addShape(pres.ShapeType.roundRect, { x: st.x, y: boxY, w: st.w, h: boxH, fill: { color: st.color }, line: { type: "none" }, rectRadius: 0.08 });
    s.addText(st.label, { x: st.x, y: boxY, w: st.w, h: boxH, isTextBox: true, margin: 0, align: "center", valign: "middle", fontFace: "Calibri", fontSize: 13, bold: true, color: WHITE });
  });
  s.addShape(pres.ShapeType.rightArrow, { x: 3.05, y: boxY + 0.35, w: 0.4, h: 0.3, fill: { color: CYAN }, line: { type: "none" } });

  // Split into VERIFIED / UNCERTAIN
  s.addShape(pres.ShapeType.rightArrow, { x: 6.35, y: boxY + 0.35, w: 0.5, h: 0.3, fill: { color: CYAN }, line: { type: "none" } });
  s.addShape(pres.ShapeType.roundRect, { x: 7.15, y: 2.15, w: 2.5, h: 0.75, fill: { color: GREEN }, line: { type: "none" }, rectRadius: 0.08 });
  s.addText("VERIFIED \u2192 Execute", { x: 7.15, y: 2.15, w: 2.5, h: 0.75, isTextBox: true, margin: 0, align: "center", valign: "middle", fontFace: "Calibri", fontSize: 13, bold: true, color: NAVY });
  s.addShape(pres.ShapeType.roundRect, { x: 7.15, y: 3.15, w: 2.5, h: 0.75, fill: { color: AMBER }, line: { type: "none" }, rectRadius: 0.08 });
  s.addText("UNCERTAIN \u2192 Clarify", { x: 7.15, y: 3.15, w: 2.5, h: 0.75, isTextBox: true, margin: 0, align: "center", valign: "middle", fontFace: "Calibri", fontSize: 13, bold: true, color: NAVY });

  s.addShape(pres.ShapeType.rightArrow, { x: 9.85, y: 3.5, w: 0.5, h: 0.3, fill: { color: CYAN }, line: { type: "none" } });
  s.addShape(pres.ShapeType.roundRect, { x: 10.55, y: 3.15, w: 2.1, h: 0.75, fill: { color: DEEPBLUE }, line: { type: "none" }, rectRadius: 0.08 });
  s.addText("Verify \u2192 Execute", { x: 10.55, y: 3.15, w: 2.1, h: 0.75, isTextBox: true, margin: 0, align: "center", valign: "middle", fontFace: "Calibri", fontSize: 12, bold: true, color: WHITE });

  s.addText("\u201cJust to confirm, was your order number one-five-eight-zero?\u201d", {
    x: 0.7, y: 4.4, w: 11.5, h: 0.6, isTextBox: true, margin: 0,
    fontFace: "Calibri", fontSize: 18, italic: true, color: CYAN, align: "center",
  });

  s.addShape(pres.ShapeType.roundRect, { x: 0.7, y: 5.35, w: 11.9, h: 1.5, fill: { color: MIDNIGHT }, line: { type: "none" }, rectRadius: 0.1 });
  s.addText("Never guesses. Never silently corrects. The action layer physically refuses to run on an unverified entity \u2014 enforced in code, not just UI convention.", {
    x: 1.1, y: 5.55, w: 11.1, h: 1.1, isTextBox: true, margin: 0, valign: "middle",
    fontFace: "Calibri", fontSize: 15, color: WHITE,
  });
}

// ---------- Slide 4: Why AssemblyAI ----------
{
  const s = lightSlide(pres);
  kicker(s, "Application of technology", 0.7, 0.55, TEAL);
  s.addText("Built on AssemblyAI's real-time signals", {
    x: 0.7, y: 0.9, w: 11, h: 0.8, isTextBox: true, margin: 0,
    fontFace: "Cambria", fontSize: 30, bold: true, color: TEXT_DARK,
  });
  s.addText("Not a transcription wrapper — Ripcord's entire premise depends on data a plain \u201cgive me the transcript\u201d call throws away.", {
    x: 0.7, y: 1.65, w: 11, h: 0.5, isTextBox: true, margin: 0, fontFace: "Calibri", fontSize: 14, color: MUTED,
  });

  const items = [
    ["Per-word confidence", "Streaming v3 Turn messages expose word-level confidence \u2014 the single biggest input to the risk score."],
    ["end_of_turn_confidence", "Blended with word confidence: a turn can sound clear word-by-word yet still be a turn ASR itself wasn't sure about."],
    ["keyterms_prompt", "Boosts recognition of this workflow's exact vocabulary \u2014 \u201corder number,\u201d \u201cbooking reference\u201d \u2014 with no custom model."],
    ["agent_context", "Feeds the agent's own last question back into the ASR, improving accuracy on short replies like a bare \u201cyes\u201d or a restated digit."],
  ];
  let gx = 0.7, gy = 2.6;
  items.forEach(([title, body], i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = gx + col * 5.9, y = gy + row * 2.0;
    s.addShape(pres.ShapeType.roundRect, { x, y, w: 5.6, h: 1.75, fill: { color: WHITE }, line: { color: "DDE3EE", width: 1 }, rectRadius: 0.08, shadow: { type: "outer", color: "9AA7C2", opacity: 0.25, blur: 6, offset: 2, angle: 90 } });
    s.addShape(pres.ShapeType.ellipse, { x: x + 0.25, y: y + 0.25, w: 0.5, h: 0.5, fill: { color: DEEPBLUE }, line: { type: "none" } });
    s.addText(String(i + 1), { x: x + 0.25, y: y + 0.25, w: 0.5, h: 0.5, isTextBox: true, margin: 0, align: "center", valign: "middle", fontFace: "Calibri", fontSize: 15, bold: true, color: WHITE });
    s.addText(title, { x: x + 0.95, y: y + 0.2, w: 4.4, h: 0.45, isTextBox: true, margin: 0, fontFace: "Calibri", fontSize: 15, bold: true, color: TEXT_DARK });
    s.addText(body, { x: x + 0.25, y: y + 0.8, w: 5.15, h: 0.85, isTextBox: true, margin: 0, fontFace: "Calibri", fontSize: 11.5, color: MUTED });
  });
}

// ---------- Slide 5: Architecture ----------
{
  const s = darkSlide(pres);
  kicker(s, "How it works", 0.7, 0.5);
  s.addText("End-to-end data flow", {
    x: 0.7, y: 0.85, w: 10, h: 0.7, isTextBox: true, margin: 0,
    fontFace: "Cambria", fontSize: 30, bold: true, color: WHITE,
  });

  const flow = [
    ["\uD83C\uDF99", "Mic", DEEPBLUE],
    ["\u2194", "Browser\nWebSocket", TEAL],
    ["\u2699", "Ripcord\nbackend", TEAL],
    ["\u2601", "AssemblyAI\nStreaming v3", DEEPBLUE],
    ["\u26A0/\u2705", "Risk +\nClarify", AMBER],
    ["\uD83D\uDD12", "Workflow\nguard", GREEN],
  ];
  const fw = 1.75, gap = 0.35, startX = 0.7, fy = 2.3;
  flow.forEach((f, i) => {
    const x = startX + i * (fw + gap);
    s.addShape(pres.ShapeType.roundRect, { x, y: fy, w: fw, h: 1.3, fill: { color: f[2] }, line: { type: "none" }, rectRadius: 0.1 });
    s.addText(f[0], { x, y: fy + 0.12, w: fw, h: 0.5, isTextBox: true, margin: 0, align: "center", fontFace: "Calibri", fontSize: 22, color: WHITE });
    s.addText(f[1], { x, y: fy + 0.6, w: fw, h: 0.6, isTextBox: true, margin: 0, align: "center", fontFace: "Calibri", fontSize: 11.5, bold: true, color: WHITE });
    if (i < flow.length - 1) {
      s.addShape(pres.ShapeType.rightArrow, { x: x + fw + 0.03, y: fy + 0.5, w: 0.28, h: 0.3, fill: { color: CYAN }, line: { type: "none" } });
    }
  });

  s.addText("Audio never reaches AssemblyAI straight from the browser \u2014 it's proxied through Ripcord's backend, which holds the API key and runs the risk engine on every Turn message before the dashboard ever sees it.", {
    x: 0.7, y: 4.1, w: 11.5, h: 0.7, isTextBox: true, margin: 0, fontFace: "Calibri", fontSize: 13, color: "AEB9D4",
  });

  s.addShape(pres.ShapeType.roundRect, { x: 0.7, y: 5.0, w: 11.9, h: 1.8, fill: { color: MIDNIGHT }, line: { type: "none" }, rectRadius: 0.1 });
  const resItems = [
    ["Auto-reconnect", "Backend retries AssemblyAI with backoff if the stream drops mid-call."],
    ["Mock mode", "Full pipeline replay for UI dev \u2014 zero API credits, clearly separated from the real client."],
    ["25 passing tests", "Entity detection, risk scoring, workflow guard, and all 10 scenarios covered."],
  ];
  resItems.forEach((r, i) => {
    const x = 1.0 + i * 3.85;
    s.addText(r[0], { x, y: 5.2, w: 3.6, h: 0.4, isTextBox: true, margin: 0, fontFace: "Calibri", fontSize: 14, bold: true, color: CYAN });
    s.addText(r[1], { x, y: 5.6, w: 3.6, h: 1.0, isTextBox: true, margin: 0, fontFace: "Calibri", fontSize: 11.5, color: WHITE });
  });
}

// ---------- Slide 6: Results ----------
{
  const s = lightSlide(pres);
  kicker(s, "Proof, not slideware", 0.7, 0.55, TEAL);
  s.addText("Real numbers from the real pipeline", {
    x: 0.7, y: 0.9, w: 11, h: 0.7, isTextBox: true, margin: 0,
    fontFace: "Cambria", fontSize: 30, bold: true, color: TEXT_DARK,
  });
  s.addText("Computed live by backend/app/evaluation.py against demo/scenarios.json \u2014 never hand-typed.", {
    x: 0.7, y: 1.6, w: 11, h: 0.5, isTextBox: true, margin: 0, fontFace: "Calibri", fontSize: 13, italic: true, color: MUTED,
  });

  s.addChart(
    pres.ChartType.bar,
    [
      {
        name: "Entity errors accepted",
        labels: ["Without Ripcord", "With Ripcord"],
        values: [1, 0],
      },
    ],
    {
      x: 0.7, y: 2.3, w: 5.6, h: 3.9,
      barDir: "col",
      showTitle: true, title: "Errors out of 10 scripted scenarios", titleFontSize: 13,
      showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 14, dataLabelColor: TEXT_DARK,
      chartColors: [RED],
      showLegend: false,
      catAxisLabelColor: MUTED, valAxisLabelColor: MUTED,
      valAxisMinVal: 0, valAxisMaxVal: 2,
      valGridLine: { color: "E2E8F0", size: 1 },
      catGridLine: { style: "none" },
    }
  );

  const stats = [
    ["10 / 10", "entities verified correctly", GREEN],
    ["1 / 1", "Mode-A errors recovered via one clarifying question", DEEPBLUE],
    ["0 / 10", "false clarifications on clean captures", TEAL],
  ];
  let sy = 2.4;
  stats.forEach(([n, label, color]) => {
    s.addShape(pres.ShapeType.roundRect, { x: 6.9, y: sy, w: 5.7, h: 1.05, fill: { color: WHITE }, line: { color: "DDE3EE", width: 1 }, rectRadius: 0.08 });
    s.addText(n, { x: 7.15, y: sy, w: 1.8, h: 1.05, isTextBox: true, margin: 0, valign: "middle", fontFace: "Cambria", fontSize: 26, bold: true, color });
    s.addText(label, { x: 9.0, y: sy, w: 3.4, h: 1.05, isTextBox: true, margin: 0, valign: "middle", fontFace: "Calibri", fontSize: 13, color: TEXT_DARK });
    sy += 1.3;
  });

  s.addText("A small, hand-authored corpus \u2014 read as proof the mechanism works end to end, not a statistically powered accuracy claim.", {
    x: 0.7, y: 6.55, w: 11.5, h: 0.5, isTextBox: true, margin: 0, fontFace: "Calibri", fontSize: 11, italic: true, color: MUTED,
  });
}

// ---------- Slide 7: Business Value ----------
{
  const s = darkSlide(pres);
  kicker(s, "Business value", 0.7, 0.5);
  s.addText("Where this fits in the market", {
    x: 0.7, y: 0.85, w: 10, h: 0.7, isTextBox: true, margin: 0,
    fontFace: "Cambria", fontSize: 30, bold: true, color: WHITE,
  });

  const cols = [
    ["Target user", "Teams shipping voice agents for transactional flows \u2014 order support, logistics dispatch, appointment booking, fintech onboarding \u2014 where a misheard number has a real, costly downstream effect."],
    ["Market angle", "Voice-agent tooling today competes mostly on latency and naturalness. Almost none of it competes on correctness under uncertainty \u2014 a distinct, underserved axis as voice agents move into higher-stakes workflows."],
    ["Revenue model", "Usage-based middleware pricing per verified transaction, or a per-seat enterprise license for teams embedding Ripcord's guard layer directly into their existing agent stack."],
  ];
  let cx = 0.7;
  cols.forEach(([title, body]) => {
    s.addShape(pres.ShapeType.roundRect, { x: cx, y: 1.85, w: 3.75, h: 4.6, fill: { color: MIDNIGHT }, line: { type: "none" }, rectRadius: 0.1 });
    s.addText(title, { x: cx + 0.3, y: 2.25, w: 3.15, h: 0.5, isTextBox: true, margin: 0, fontFace: "Calibri", fontSize: 17, bold: true, color: CYAN });
    s.addText(body, { x: cx + 0.3, y: 2.8, w: 3.15, h: 3.4, isTextBox: true, margin: 0, fontFace: "Calibri", fontSize: 12.5, color: WHITE, lineSpacingMultiple: 1.15 });
    cx += 4.05;
  });
}

// ---------- Slide 8: Roadmap ----------
{
  const s = lightSlide(pres);
  kicker(s, "What's next", 0.7, 0.55, TEAL);
  s.addText("Roadmap", {
    x: 0.7, y: 0.9, w: 8, h: 0.7, isTextBox: true, margin: 0,
    fontFace: "Cambria", fontSize: 32, bold: true, color: TEXT_DARK,
  });

  const road = [
    ["Now", "Single entity type (order ID), deterministic risk engine, full mock + real AssemblyAI pipeline, 25 passing tests.", DEEPBLUE],
    ["Next", "Extend the same detector \u2192 risk \u2192 clarify \u2192 guard pattern to more entity types \u2014 phone numbers, confirmation codes, dates.", TEAL],
    ["Later", "Calibrated confidence models from real usage data, still gated behind the same deterministic guard. Speaker-aware handling for multi-party calls.", MIDNIGHT],
  ];
  let ry = 2.3;
  road.forEach(([tag, body, color]) => {
    s.addShape(pres.ShapeType.roundRect, { x: 0.7, y: ry, w: 1.4, h: 0.5, fill: { color }, line: { type: "none" }, rectRadius: 0.06 });
    s.addText(tag, { x: 0.7, y: ry, w: 1.4, h: 0.5, isTextBox: true, margin: 0, align: "center", valign: "middle", fontFace: "Calibri", fontSize: 13, bold: true, color: WHITE });
    s.addText(body, { x: 2.35, y: ry - 0.05, w: 9.8, h: 0.9, isTextBox: true, margin: 0, valign: "middle", fontFace: "Calibri", fontSize: 14, color: TEXT_DARK });
    ry += 1.35;
  });
}

// ---------- Slide 9: Close ----------
{
  const s = darkSlide(pres);
  s.addShape(pres.ShapeType.ellipse, { x: -2, y: 4.5, w: 6, h: 6, fill: { color: MIDNIGHT }, line: { type: "none" } });
  s.addText("Ripcord turns voice uncertainty into a controlled verification step \u2014 before the mistake becomes an action.", {
    x: 1.2, y: 2.2, w: 10.9, h: 1.6, isTextBox: true, margin: 0,
    fontFace: "Cambria", fontSize: 26, bold: true, color: WHITE, align: "center",
  });

  const links = [
    ["GitHub", "github.com/[your-username]/ripcord"],
    ["Live demo", "[your-deployed-url]"],
    ["Contact", "[your-email]"],
  ];
  let lx = 2.2;
  links.forEach(([label, val]) => {
    s.addText(label.toUpperCase(), { x: lx, y: 4.7, w: 3, h: 0.35, isTextBox: true, margin: 0, align: "center", fontFace: "Calibri", fontSize: 11, bold: true, color: CYAN, charSpacing: 1.5 });
    s.addText(val, { x: lx, y: 5.05, w: 3, h: 0.4, isTextBox: true, margin: 0, align: "center", fontFace: "Calibri", fontSize: 12.5, color: WHITE });
    lx += 3.1;
  });

  s.addText("AssemblyAI Voice Agent Hackathon 2026 \u00b7 lablab.ai", {
    x: 0, y: 6.7, w: 13.33, h: 0.4, isTextBox: true, margin: 0, align: "center", fontFace: "Calibri", fontSize: 12, color: "AEB9D4",
  });
}

pres.writeFile({ fileName: "/home/claude/ripcord-deck/ripcord.pptx" }).then(() => {
  console.log("written");
});
