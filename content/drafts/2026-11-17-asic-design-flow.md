---
title: The ASIC Design Flow — And Which Stage Owns Timing Closure
slug: asic-design-flow
keyword: asic design flow
hook: Anyone can list the ASIC flow. Almost nobody can say which stage owns timing closure.
cta: Bookmark this. It is the map for the next two years of your career.
tags: asic, rtl, physical-design, sta, dft
date: 2026-11-17
---

## Key takeaways

- The flow runs spec, RTL, verification, synthesis, DFT insertion, floorplan, placement, CTS, routing, signoff
- Front-end means RTL and verification, back-end means netlist to GDSII
- Timing closure is not one stage, it is a negotiation that repeats at synthesis, placement, CTS and routing
- Scan insertion happens after synthesis and before placement, not at the end
- Each handoff has a fixed set of files, and knowing them is what makes you look experienced

## The one-paragraph version

You write hardware in Verilog, you prove it works, you turn it into gates, you place and wire
those gates on silicon, and you prove the result meets timing, power and manufacturing rules.
Then someone spends a lot of money to build it.

Everything below is detail on that sentence.

## Front-end: RTL to netlist

**1. Specification.** What the chip does, what interfaces it has, what frequency it must hit.
This is where cost is decided and where most projects quietly go wrong.

**2. Architecture.** Block diagram, clock domains, memory map, data widths, pipeline depth.
A good architecture document prevents six months of RTL rewrites.

**3. RTL design.** Verilog or SystemVerilog. Written to be synthesizable, testable, and
timing-aware. A designer who ignores timing here just moves the pain to the back-end team.

**4. Functional verification.** Simulation with directed and constrained-random tests,
assertions, coverage closure, formal checks, lint, and CDC analysis. In most companies this is
the largest team on the project.

**5. Synthesis.** RTL plus a standard cell library plus timing constraints becomes a gate-level
netlist. Constraints live in an SDC file: clock definitions, input and output delays, false
paths, multicycle paths.

**6. DFT insertion.** Scan chains are stitched into the netlist so the manufactured chip can be
tested. This happens after synthesis and before placement. If you think DFT is a final-step
afterthought, you will learn otherwise the first time scan insertion breaks your timing.

## Back-end: netlist to GDSII

**7. Floorplanning.** Die size, IO ring, macro placement, power grid. Bad floorplan equals
weeks of unclosable timing. This is the highest-leverage decision in physical design.

**8. Placement.** Standard cells get positions. Congestion and timing are both watching.

**9. Clock tree synthesis.** Build a balanced clock distribution network. CTS is where hold
problems are born, because the clock now arrives at different flops at slightly different times.

**10. Routing.** Global then detailed. Wires add capacitance and resistance, so timing measured
before routing is optimistic.

**11. Parasitic extraction and signoff STA.** Real RC values go back into timing analysis across
process, voltage and temperature corners. This is where the chip is actually declared good.

**12. Physical verification.** DRC checks manufacturing rules, LVS checks that the layout matches
the netlist, antenna checks catch charge damage during fabrication, IR drop and electromigration
checks catch power problems.

**13. GDSII and tapeout.** The database goes to the foundry. Then fabrication, packaging, and
production test.

## So which stage owns timing closure

None of them, and that is the point.

Timing is measured at synthesis and it is wrong, because wire delays are estimates. It is
measured again after placement and it is closer. It is measured after CTS and hold appears. It is
measured after routing and setup degrades further. Each round you fix some paths and break others.

That is why experienced engineers say timing closure is a loop, not a step. Setup is fought early,
in synthesis and placement, while there is still room to restructure logic. Hold is fought last,
after CTS, using delay insertion, because every hold fix costs setup margin.

Anyone who tells you "timing gets fixed in STA" has never owned a tapeout.

## The handoff files

If you want to sound like you have done this before, know these:

- RTL: `.v` and `.sv` sources plus the file list
- Constraints: `.sdc`
- Library: `.lib` for timing, `.db` for the tool
- Physical: `.lef` for abstract, `.gds` for full layout
- Power intent: `UPF`
- Extracted parasitics: `SPEF`
- Final database: `.gds`

Every one of these is a contract between two teams. Half of all project delays are a broken
contract at one of these boundaries.

## Who does what

- RTL designer: microarchitecture and synthesizable logic
- Verification engineer: proving it works, and finding the corner where it does not
- DFT engineer: scan, compression, memory BIST, ATPG
- Physical design engineer: floorplan through routing, area, congestion, power
- STA engineer: signoff timing across corners
- Layout engineer: analog and custom blocks
- CAD engineer: the tool flow everyone else depends on

When you pick a specialization, you are really picking which of these problems you want to
think about for the next decade.

## What to do next

Draw this flow from memory, once a week, until you can annotate each box with its input file,
output file, and the one thing that goes wrong there. That single exercise covers more interview
ground than any course chapter.

Free VLSI Interview Bank with 120 questions and answers is in the bio.
