"""Generate nifty-analysis-watch.canvas.tsx with full marked candlestick chart."""
from __future__ import annotations

import json
from pathlib import Path

SLIM = Path(r"c:\Users\Priyanka\Agent\prod_live\reports\1y\_analysis_watch_canvas_slim.json")
OUT = Path(
    r"C:\Users\Priyanka\.cursor\projects\c-Users-Priyanka-Agent\canvases\nifty-analysis-watch.canvas.tsx"
)

# Short labels so pattern text fits above candles
PAT_ABBR = {
    "bear_run3": "br3",
    "bull_run3": "bu3",
    "bear_run2": "br2",
    "bull_run2": "bu2",
    "bear_engulf": "be",
    "bull_engulf": "ue",
    "marubozu_bear": "mb",
    "marubozu_bull": "mu",
    "three_outside_dn": "3od",
    "three_outside_up": "3ou",
    "belt_bull": "bbu",
    "belt_bear": "bbe",
    "hammer": "hm",
    "inv_hammer": "ih",
    "hanging_man": "hg",
    "shooting_star": "ss",
    "three_crows": "3c",
    "three_soldiers": "3s",
    "piercing": "pc",
    "dark_cloud": "dc",
    "bull_kicker": "bk",
    "tweezer_top": "tt",
    "tweezer_bot": "tb",
    "falling_3_methods": "f3m",
    "rising_3_methods": "r3m",
    "morning_star": "ms",
}


def main() -> None:
    slim = json.loads(SLIM.read_text(encoding="utf-8"))
    slim["pat_abbr"] = PAT_ABBR
    data_js = json.dumps(slim, separators=(",", ":"))

    canvas = f'''import {{
  Callout,
  Card,
  CardBody,
  CardHeader,
  Grid,
  H1,
  H2,
  Pill,
  Row,
  Stack,
  Stat,
  Table,
  Text,
  useCanvasState,
  useHostTheme,
}} from "cursor/canvas";

const DATA = {data_js} as const;

type Candle = {{
  t: string;
  o: number;
  h: number;
  l: number;
  c: number;
  pattern: string | null;
  expansion: string | null;
  swing_h: boolean;
  swing_l: boolean;
  atr: number;
}};

type Structure = {{ t: string; label: string; px: number; kind: string }};

const WINDOWS: {{ id: string; label: string; start: string; end: string }}[] = [
  {{ id: "full", label: "Full day", start: "09:15", end: "15:30" }},
  {{ id: "open", label: "Open 09:15–11:00", start: "09:15", end: "11:00" }},
  {{ id: "mid", label: "Mid 11:00–13:00", start: "11:00", end: "13:00" }},
  {{ id: "pm", label: "PM 13:00–15:30", start: "13:00", end: "15:30" }},
];

function inWindow(t: string, start: string, end: string) {{
  return t >= start && t <= end;
}}

function MarkedCandleChart() {{
  const theme = useHostTheme();
  const [winId, setWinId] = useCanvasState("win", "open");
  const [showPat, setShowPat] = useCanvasState("pat", true);
  const [showExp, setShowExp] = useCanvasState("exp", true);
  const [showSwing, setShowSwing] = useCanvasState("swing", true);
  const [showSr, setShowSr] = useCanvasState("sr", true);

  const win = WINDOWS.find((w) => w.id === winId) ?? WINDOWS[1];
  const all = DATA.candles_1m as unknown as Candle[];
  const candles = all.filter((c) => inWindow(c.t, win.start, win.end));
  const structure = (DATA.structure as unknown as Structure[]).filter((s) =>
    inWindow(s.t, win.start, win.end)
  );
  const sr = DATA.support_resistance as {{
    day_high: number;
    day_low: number;
    or_high: number;
    or_low: number;
  }};
  const abbr = DATA.pat_abbr as Record<string, string>;

  const W = 860;
  const H = 420;
  const padL = 52;
  const padR = 78;
  const padT = 28;
  const padB = 36;

  const prices = candles.flatMap((c) => [c.h, c.l]);
  const lo = Math.min(...prices, showSr ? sr.day_low : prices[0]) - 8;
  const hi = Math.max(...prices, showSr ? sr.day_high : prices[0]) + 8;
  const n = Math.max(candles.length, 1);
  const slot = (W - padL - padR) / n;
  const bodyW = Math.max(1.2, Math.min(6, slot * 0.62));
  const x = (i: number) => padL + slot * (i + 0.5);
  const y = (p: number) => padT + ((hi - p) / (hi - lo)) * (H - padT - padB);
  const byT: Record<string, number> = {{}};
  candles.forEach((c, i) => {{ byT[c.t] = i; }});

  const bull = theme.accent.primary;
  const bear = theme.text.primary;
  const muted = theme.text.secondary;
  const stroke = theme.stroke.secondary;

  const level = (px: number, label: string, dash: boolean, strong: boolean) => (
    <g key={{label}}>
      <line
        x1={{padL}}
        y1={{y(px)}}
        x2={{W - padR}}
        y2={{y(px)}}
        stroke={{strong ? theme.stroke.primary : stroke}}
        strokeWidth={{strong ? 1.25 : 1}}
        strokeDasharray={{dash ? "5 4" : undefined}}
        opacity={{0.9}}
      />
      <text
        x={{W - padR + 4}}
        y={{y(px) + 3}}
        fill={{muted}}
        fontSize={{9}}
      >
        {{label}} {{px}}
      </text>
    </g>
  );

  const tickEvery = candles.length > 120 ? 30 : candles.length > 60 ? 15 : 10;

  return (
    <Stack gap={{10}}>
      <Row gap={{8}} style={{{{ flexWrap: "wrap" }}}}>
        {{WINDOWS.map((w) => (
          <Pill key={{w.id}} active={{winId === w.id}} onClick={{() => setWinId(w.id)}}>
            {{w.label}}
          </Pill>
        ))}}
      </Row>
      <Row gap={{8}} style={{{{ flexWrap: "wrap" }}}}>
        <Pill active={{showSr}} onClick={{() => setShowSr(!showSr)}}>S/R + OR</Pill>
        <Pill active={{showSwing}} onClick={{() => setShowSwing(!showSwing)}}>HH HL LH LL</Pill>
        <Pill active={{showExp}} onClick={{() => setShowExp(!showExp)}}>Expansions</Pill>
        <Pill active={{showPat}} onClick={{() => setShowPat(!showPat)}}>Candle patterns</Pill>
      </Row>

      <svg
        viewBox={{`0 0 ${{W}} ${{H}}`}}
        width="100%"
        role="img"
        aria-label={{`NIFTY 1m candlesticks ${{DATA.last_day}} ${{win.label}}`}}
      >
        <rect x={{0}} y={{0}} width={{W}} height={{H}} fill={{theme.bg.editor}} />

        {{showSr && (
          <rect
            x={{padL}}
            y={{y(sr.or_high)}}
            width={{W - padL - padR}}
            height={{Math.max(1, y(sr.or_low) - y(sr.or_high))}}
            fill={{theme.fill.tertiary}}
            opacity={{0.55}}
          />
        )}}

        {{showSr && level(sr.day_high, "DayH / R", false, true)}}
        {{showSr && level(sr.day_low, "DayL / S", false, true)}}
        {{showSr && level(sr.or_high, "OR H", true, false)}}
        {{showSr && level(sr.or_low, "OR L", true, false)}}

        {{candles.map((c, i) => {{
          const up = c.c >= c.o;
          const color = up ? bull : bear;
          const yO = y(c.o);
          const yC = y(c.c);
          const top = Math.min(yO, yC);
          const bot = Math.max(yO, yC);
          const bh = Math.max(1, bot - top);
          const cx = x(i);
          return (
            <g key={{`c${{i}}`}}>
              <line
                x1={{cx}}
                y1={{y(c.h)}}
                x2={{cx}}
                y2={{y(c.l)}}
                stroke={{color}}
                strokeWidth={{1}}
              />
              <rect
                x={{cx - bodyW / 2}}
                y={{top}}
                width={{bodyW}}
                height={{bh}}
                fill={{color}}
                opacity={{0.92}}
              />
            </g>
          );
        }})}}

        {{showExp &&
          candles.map((c, i) => {{
            if (!c.expansion) return null;
            const cx = x(i);
            const cy = c.expansion === "BUY" ? y(c.l) + 10 : y(c.h) - 10;
            const fill = c.expansion === "BUY" ? bull : bear;
            const pts =
              c.expansion === "BUY"
                ? `${{cx}},${{cy - 5}} ${{cx - 4}},${{cy + 3}} ${{cx + 4}},${{cy + 3}}`
                : `${{cx}},${{cy + 5}} ${{cx - 4}},${{cy - 3}} ${{cx + 4}},${{cy - 3}}`;
            return <polygon key={{`e${{i}}`}} points={{pts}} fill={{fill}} opacity={{0.95}} />;
          }})}}

        {{showPat &&
          candles.map((c, i) => {{
            if (!c.pattern) return null;
            const cx = x(i);
            const up = c.c >= c.o;
            const label = abbr[c.pattern] ?? c.pattern.slice(0, 4);
            const ty = up ? y(c.h) - 4 : y(c.l) + 10;
            return (
              <text
                key={{`p${{i}}`}}
                x={{cx}}
                y={{ty}}
                textAnchor="middle"
                fill={{muted}}
                fontSize={{7}}
              >
                {{label}}
              </text>
            );
          }})}}

        {{showSwing &&
          structure.map((s, idx) => {{
            const i = byT[s.t];
            if (i == null) return null;
            const cx = x(i);
            const isH = s.kind === "H";
            const ty = isH ? y(s.px) - 12 : y(s.px) + 14;
            return (
              <g key={{`s${{idx}}`}}>
                <circle
                  cx={{cx}}
                  cy={{y(s.px)}}
                  r={{2.4}}
                  fill={{theme.fill.primary}}
                  stroke={{stroke}}
                  strokeWidth={{1}}
                />
                <text
                  x={{cx}}
                  y={{ty}}
                  textAnchor="middle"
                  fill={{theme.text.primary}}
                  fontSize={{9}}
                  fontWeight={{600}}
                >
                  {{s.label}}
                </text>
              </g>
            );
          }})}}

        {{candles.map((c, i) =>
          i % tickEvery === 0 ? (
            <text
              key={{`t${{i}}`}}
              x={{x(i)}}
              y={{H - 10}}
              textAnchor="middle"
              fill={{muted}}
              fontSize={{8}}
            >
              {{c.t}}
            </text>
          ) : null
        )}}

        <text x={{padL}} y={{14}} fill={{muted}} fontSize={{9}}>
          {{DATA.last_day}} · NIFTY 1m · {{win.label}} · {{candles.length}} candles · analysis only
        </text>
      </svg>

      <Row gap={{14}} style={{{{ flexWrap: "wrap" }}}}>
        <Text size="small" tone="secondary">Filled band = opening range</Text>
        <Text size="small" tone="secondary">DayH/DayL = session resistance / support</Text>
        <Text size="small" tone="secondary">△▽ = BUY/SELL expansion</Text>
        <Text size="small" tone="secondary">abbr above/below = textbook pattern</Text>
        <Text size="small" tone="secondary">HH/HL/LH/LL = swing structure</Text>
      </Row>
    </Stack>
  );
}}

export default function AnalysisWatch5d() {{
  const sr = DATA.success_rate_note;
  const checks = DATA.accuracy_checks as Record<string, boolean | number>;
  const sessions = DATA.sessions as unknown as {{
    day: string;
    day_hi: number;
    day_lo: number;
    or_hi: number;
    or_lo: number;
    range: number;
    n: number;
  }}[];
  const pats = Object.entries(DATA.pattern_counts as Record<string, number>);
  const abbr = DATA.pat_abbr as Record<string, string>;
  const struct = DATA.structure as unknown as Structure[];
  const allOk = Object.entries(checks)
    .filter(([k]) => k !== "n_bars_session")
    .every(([, v]) => v === true);

  return (
    <Stack gap={{16}} style={{{{ padding: 16, maxWidth: 920 }}}}>
      <Stack gap={{6}}>
        <H1>NIFTY marked analysis chart</H1>
        <Text tone="secondary">
          1m candles · day S/R · opening range · HH/HL/LH/LL · expansions · textbook patterns · no entries
        </Text>
      </Stack>

      <Grid columns={{4}} gap={{10}}>
        <Stat value={{`${{sr.oos_hit_pct}}%`}} label="Book OOS success (T18)" tone="success" />
        <Stat value={{`+${{sr.oos_exp_R}}R`}} label="Book expectancy OOS" />
        <Stat value={{String(DATA.expansion_bars)}} label={{`Expansions ${{DATA.last_day}}`}} />
        <Stat value={{allOk ? "PASS" : "FAIL"}} label="Annotation accuracy" tone={{allOk ? "success" : "danger"}} />
      </Grid>

      <Card>
        <CardHeader trailing={{<Pill active>{{DATA.last_day}}</Pill>}}>
          Candlesticks with every mark
        </CardHeader>
        <CardBody>
          <MarkedCandleChart />
        </CardBody>
      </Card>

      <Callout tone="info" title="How to read">
        Use Open / Mid / PM windows so pattern labels stay readable. Toggle layers on the chart.
        Book success rate is separate from pattern frequency — this view is watch-only.
      </Callout>

      <H2>Session levels (S/R + OR)</H2>
      <Table
        headers={{["Day", "Bars", "Day H (R)", "Day L (S)", "OR H", "OR L", "Range"]}}
        rows={{sessions.map((s) => [
          s.day,
          String(s.n),
          String(s.day_hi),
          String(s.day_lo),
          String(s.or_hi),
          String(s.or_lo),
          String(s.range),
        ])}}
      />

      <Grid columns={{2}} gap={{12}}>
        <Card>
          <CardHeader>Pattern legend + counts</CardHeader>
          <CardBody>
            <Table
              headers={{["Abbr", "Pattern", "Count"]}}
              rows={{pats.map(([k, v]) => [abbr[k] ?? k.slice(0, 4), k, String(v)])}}
            />
          </CardBody>
        </Card>
        <Card>
          <CardHeader>Swing structure (full session)</CardHeader>
          <CardBody>
            <Table
              headers={{["Time", "Label", "Price"]}}
              rows={{struct.map((s) => [s.t, s.label, String(s.px)])}}
            />
          </CardBody>
        </Card>
      </Grid>

      <H2>Accuracy checks</H2>
      <Table
        headers={{["Check", "Result"]}}
        rows={{Object.entries(checks).map(([k, v]) => [
          k,
          typeof v === "boolean" ? (v ? "OK" : "FAIL") : String(v),
        ])}}
      />
    </Stack>
  );
}}
'''
    OUT.write_text(canvas, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
