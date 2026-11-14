---
title: Clock Domain Crossing — The 4 Techniques Interviewers Actually Test
slug: clock-domain-crossing-techniques
keyword: clock domain crossing
hook: Every CDC bug looks like a random glitch. It isn't. It's a timing violation you can predict.
cta: Save this. CDC questions come up in almost every DV and RTL interview.
tags: cdc, timing, interview, verification
date: 2026-11-15
---

## Key takeaways

- A clock domain crossing is unsafe whenever data can change inside the setup-hold window of the capturing flop
- A two-flop synchronizer makes metastability improbable, never impossible
- Never send a multi-bit bus through parallel synchronizers, because the bits can land on different cycles
- Multi-bit crossings use a handshake or an asynchronous FIFO with Gray-coded pointers
- Gray code works because only one bit changes at a time, so a bad sample is always the old value or the new one, never garbage

## What actually happens at a clock boundary

Two flops, two unrelated clocks. Data leaves the first flop whenever it wants and arrives at the
second flop whenever it wants. There is no fixed relationship between the data edge and the
capturing clock edge.

So sometimes the data transition lands inside the setup-hold window. The first latch inside the
capturing flop then has an input that is neither a clean 0 nor a clean 1 while the clock closes.
The flop output may hover, oscillate, or settle late. That is metastability.

It is not a glitch in the simulator. Simulators usually hide it completely, which is exactly why
CDC bugs escape simulation and show up in silicon.

## Technique 1: the two-flop synchronizer

Pass the single bit through two flops clocked by the destination clock, back to back.

The first flop is allowed to go metastable. The second flop does not sample the first flop at the
same instant, so it gives the first flop a full clock period to resolve.

This is the default answer and it is right, with three conditions:

- It only works for one bit at a time
- No combinational logic between the two flops
- Both flops are in the destination clock domain

What it buys you is not correctness, it is probability. The mean time between failures is
exponentially sensitive to how long you allow settling. Adding a third flop multiplies that
margin again. That is why high-reliability designs use three.

If someone asks "can metastability be eliminated", the answer is no. It can only be made
so improbable that the chip dies of old age first.

## Technique 2: the handshake

For a bus, you cannot synchronize every bit and hope. Bit 3 might be captured on this cycle and
bit 7 on the next, and now you have a value that never existed.

Instead you hold the data still and send one control bit:

- Source puts data on the bus and asserts request
- Request crosses through a two-flop synchronizer
- Destination sees request, samples the stable bus, asserts acknowledge
- Acknowledge crosses back through its own synchronizer
- Source drops request, and only then is allowed to change the data

The bus itself needs no synchronizer because it is guaranteed stable while request is high.
This is slower, roughly 4 to 6 destination cycles per transfer, but it is correct.

## Technique 3: the asynchronous FIFO with Gray-coded pointers

When you need throughput, a handshake is too slow. You want a FIFO where the write side runs on
the fast clock and the read side on the slow one, with no shared clock at all.

The trap: the write pointer has to cross into the read domain so the reader knows there is data.
That pointer is multi-bit. So it hits the same incoherence problem.

The fix is Gray code. In a Gray counter, consecutive values differ by exactly one bit. If that
single changing bit is sampled while metastable, it resolves to either the old value or the new
value. Never to a value that never existed.

So the reader might see a pointer that is one entry stale. It will never see a pointer that is
impossible. A one-entry-stale pointer is safe, because the FIFO simply looks slightly less full
than it is.

That single sentence is the answer interviewers are listening for.

## Technique 4: pulse and mux synchronizers

Two more patterns worth knowing:

**Pulse synchronizer.** A slow single-cycle pulse will be missed entirely by a faster destination
clock. Convert it to a toggle, synchronize the toggle, then edge-detect on the far side.

**Mux recirculation.** Feed the crossing signal into a mux that holds its previous value, and
switch only when a synchronized enable says it is safe. Used for data buses where you want to
avoid a full handshake.

## The rules that get you through CDC review

- One bit per synchronizer. Always.
- No logic between the synchronizer flops. Lint tools flag this and they are right.
- Do not synchronize a bus. Use a handshake or a FIFO.
- Reset is a crossing too. Assert asynchronously, deassert synchronously.
- A CDC tool must prove every crossing is either synchronized or intentionally false-pathed.
  "I checked it by eye" is not a signoff.

## How to answer the interview question

If asked "how do you handle clock domain crossing", structure it like this:

- Single bit, slow: two-flop synchronizer
- Single bit, pulse: toggle plus synchronizer plus edge detect
- Multi-bit, low rate: handshake
- Multi-bit, high rate: async FIFO with Gray pointers
- Then add: all of it needs CDC lint signoff, and none of it removes metastability, it only
  reduces the probability to an acceptable MTBF

That last clause is what separates an answer that got memorized from one that understands
the mechanism.

## What to do next

Pick one of these and actually build it: a two-flop synchronizer with a toggle, then a small
async FIFO with Gray pointers. Both fit on EDA Playground in under 60 lines, and both are
directly usable as interview material.

Free VLSI Interview Bank with 120 questions and answers is in the bio.
