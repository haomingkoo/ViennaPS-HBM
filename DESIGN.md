# Design system

## Theme

A light-first technical field notebook with an optional dark instrument mode.
Surfaces are cool, lightly tinted neutrals. Copper marks material/process
geometry, teal marks controlled evidence, green marks passing gates, and amber
marks misses, retractions, and hard failures. Color never carries status alone.

## Typography

Use the native system sans stack for reading and the existing system monospace
stack for measurements, recipes, labels, and controls. Keep body copy near
68ch. Use strong size and weight changes rather than decorative type.

## Layout

Use a disciplined single-column reading measure with occasional full-width
evidence bands. Sections should alternate between concise prose, direct tables,
and interactive or visual evidence. Avoid uniform card grids and nested panels.

## Components

- Findings use numbered headings and explicit evidence-status labels.
- Gate tables always show target, observed result, and decision.
- Interactive charts expose only sampled data and show recipe/seed details.
- Geometry figures include a plain-language visual read and model caveat.
- Controls are keyboard accessible and show exact current values.

## Motion

Interactions update directly without ornamental animation. Honor
`prefers-reduced-motion` and never animate layout.
