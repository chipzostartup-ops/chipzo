---
title: Setup Time vs Hold Time — The Difference That Decides Your Interview
slug: setup-time-vs-hold-time
keyword: setup time and hold time
hook: 9 out of 10 VLSI interviews start with this question. Most answers fail at sentence 3.
cta: Save this before your next interview.
tags: sta, timing, interview, setup, hold
date: 2026-11-14
---

## The one-line difference

Setup time is a **promise made before** the clock edge. Hold time is a **promise
kept after** it.

That's it. Everything else is consequences.

## Key takeaways

- Setup time is a promise made before the clock edge, hold time is a promise kept after it
- Setup depends on the longest data path, hold depends on the shortest data path
- Slowing the clock fixes setup violations but can never fix hold violations
- Fix setup during synthesis and placement, then fix hold at the very end
- Every hold fix, like adding delay or buffers, costs you setup margin

## Setup time

Setup time is the minimum time the data input must be **stable before** the
active clock edge arrives.

If data changes too close to the edge, the first latch inside the flop may not
resolve in time, and you get metastability — an output that is neither 0 nor 1
for an unpredictable amount of time.

The requirement comes from the first transmission gate in the master latch. It
needs its input settled for the time it takes to charge that node.

## Hold time

Hold time is the minimum time the data must **stay stable after** the active
clock edge.

Here's the counterintuitive part: a hold violation is worse than a setup
violation. You can fix setup by slowing the clock down. You cannot fix hold by
slowing the clock, because hold depends on the *shortest* data path, not the
longest.

## The two inequalities

Setup check, for a path from launch flop to capture flop:

- Required arrival time = T_clk - T_setup - T_skew
- Actual arrival time = T_clk-to-Q + T_logic + T_wire
- Slack = required - actual, and it must be >= 0

Hold check, for the same path:

- Required arrival time = T_hold + T_skew
- Actual arrival time = T_clk-to-Q + T_logic + T_wire
- Slack = actual - required, and it must be >= 0

Notice the asymmetry. Setup compares against the *next* clock edge and depends
on the long path. Hold compares against the *same* edge and depends on the
short path.

## Why they pull in opposite directions

Any technique that fixes setup tends to hurt hold:

- Upsizing a cell: faster, helps setup, can violate hold
- Adding buffers: adds delay, helps hold, hurts setup
- Reducing clock skew: depends which way the skew goes
- Lowering the clock frequency: only helps setup

This is why timing closure is a negotiation, not a checklist. You fix setup
during synthesis and placement, then fix hold at the very end with delay
insertion, because you don't want to fight hold violations again after routing.

## The interview answer that gets you hired

Say this, in this order:

- Setup is checked at the next active edge, hold at the current one
- Setup depends on the longest path, hold on the shortest
- Setup is fixed by making data faster or the clock slower
- Hold is fixed by making data slower, which is why it is done last
- Hold violations cannot be fixed by reducing frequency

If you can add "and that is why we fix hold after CTS, not before", you are
ahead of most candidates with two years of experience.

## Quick sanity check

A flop has setup 0.1 ns, hold 0.05 ns, clock-to-Q 0.12 ns. The combinational
logic between two flops takes 0.6 ns and the clock period is 1.0 ns with zero
skew.

- Setup slack = (1.0 - 0.1) - (0.12 + 0.6) = 0.18 ns, passing
- Hold slack = (0.12 + 0.6) - 0.05 = 0.67 ns, passing easily

Now make the logic faster, 0.02 ns. Setup slack is 0.76 ns, great. Hold slack is
0.04 ns, and you just failed.

That is the entire setup-versus-hold tradeoff in one number.

## What to do next

If this made sense, the next thing to learn is how clock skew shifts both
checks, and why useful skew is a design technique rather than a bug. That is the
natural follow-up question in almost every STA interview.

Free VLSI Interview Bank with 120 questions and answers is in the bio.
