---
title: Latch vs Flip-Flop — Why "A Latch Is Just a Bad Flip-Flop" Fails Interviews
slug: latch-vs-flip-flop
keyword: latch vs flip flop
hook: If you call a latch a bad flip-flop in an interview, the rest of your answer stops mattering.
cta: Save this. It is asked in almost every RTL and STA interview.
tags: latch, flip-flop, interview, rtl, timing
date: 2026-11-16
---

## Key takeaways

- A latch is level-sensitive and transparent while its enable is high, a flip-flop samples only at a clock edge
- A flip-flop is built from two latches in series, master then slave, which is why it is edge-triggered
- Latches are smaller, faster and lower power, but much harder to do timing analysis on
- Latch-based design allows time borrowing, which can rescue a setup violation
- The most common real-world latch problem is an accidental one inferred by an incomplete if-else

## The difference in one sentence

A latch listens whenever the door is open. A flip-flop only looks at the exact moment the door
closes.

That is level-sensitive versus edge-triggered, and everything else follows from it.

## What a latch actually does

A latch has a data input, an enable, and an output. While enable is high, the output follows the
input continuously. There is no clock edge involved. When enable goes low, the last value is held.

Because it is transparent, anything at the input passes straight through to the output in the same
cycle. That is useful and dangerous at the same time.

## What a flip-flop actually does

A flip-flop is two latches back to back:

- Master latch is transparent while the clock is low
- Slave latch is transparent while the clock is high
- They are never transparent at the same time

The result is that the input is only captured at one instant, the clock edge. Between edges the
output is stable no matter what the input does. That isolation is what makes synchronous design
analyzable.

## Why designers overwhelmingly use flip-flops

Not because latches are bad. Because flip-flops make static timing analysis simple and
predictable.

With flip-flops, every path starts at one edge and ends at the next. Setup and hold checks are
well defined. You can hand a netlist to a timing tool and it will tell you the truth.

With latches, a path can start in one cycle and end two cycles later, depending on when the latch
opened. Timing analysis becomes a loop-breaking problem. Testability also suffers, because scan
insertion into a latch-based design is significantly more awkward.

So the honest answer to "why not use latches" is: they are not wrong, they are expensive
to verify.

## The one place latches earn their keep

Time borrowing.

If logic arrives late, a latch can absorb the lateness by staying open a little longer. The
downstream stage pays for it. In high-speed datapaths and some processor designs this is a
deliberate, carefully analyzed technique that buys real frequency.

The keyword is carefully. Latch-based design is a specialist choice, not a default.

## The interview question hiding inside this

Here is the one that actually gets asked:

```verilog
always @(*) begin
    if (sel)
        y = a;
end
```

What does this infer? A latch. Because when sel is 0, y is never assigned, so it has to
remember its old value. The tool warns you, most people ignore the warning, and then the design
has a latch nobody planned for.

The fix is a complete assignment, either an else branch or a default value at the top of the
block.

This single code snippet explains why "always assign every output on every path" is rule one of
combinational logic.

## Latch vs flip-flop, side by side

- Sensitivity: level versus edge
- Transparent: yes versus no
- Built from: one storage element versus two in series
- Area: smaller versus larger
- Power: lower versus higher
- Timing analysis: complex versus straightforward
- Scan insertion: awkward versus standard
- Typical use: datapath time borrowing versus everything else

## How to answer it well

Say the level versus edge difference, then say a flip-flop is two latches in series, then say
why industry prefers edge-triggered logic, then mention time borrowing as the legitimate
exception, then mention accidental latch inference.

That order shows you understand the mechanism, the tradeoff, and the practical failure mode.
Three of those four things are usually missing from a fresher's answer.

## What to do next

Write the incomplete if-else above in any simulator, run lint, and read the warning. Then fix it
with a default assignment and run again. Seeing the warning disappear is worth more than reading
about it.

Free VLSI Interview Bank with 120 questions and answers is in the bio.
