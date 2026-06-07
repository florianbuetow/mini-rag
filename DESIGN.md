---
name: MiniRAG Chat
description: A quiet, local-first reading room for interrogating your own documents
colors:
  bg-primary: "#212121"
  bg-secondary: "#171717"
  bg-sidebar: "#171717"
  bg-input: "#2f2f2f"
  bg-active: "#343541"
  text-primary: "#ececec"
  text-secondary: "#b4b4b4"
  text-muted: "#a1a1b0"
  border: "#444444"
  accent: "#10a37f"
  accent-hover: "#0d8c6d"
  citation-bg: "#0b7a5e"
  accent-contrast: "#ffffff"
  user-bubble: "#2f2f2f"
  error: "#f87171"
  code-bg: "#1e1e2e"
  warning-bg: "#5c2d2d"
  warning-text: "#f8d7da"
typography:
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "normal"
  ui:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.5px"
  mono:
    fontFamily: "'SF Mono', 'Fira Code', 'Consolas', monospace"
    fontSize: "0.85em"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
rounded:
  sm: "4px"
  md: "6px"
  lg: "8px"
  xl: "10px"
  2xl: "16px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  2xl: "24px"
components:
  button-send:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.accent-contrast}"
    rounded: "{rounded.xl}"
    height: "32px"
    width: "32px"
  button-send-hover:
    backgroundColor: "{colors.accent-hover}"
  button-new-chat:
    backgroundColor: "{colors.bg-input}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.lg}"
    padding: "10px 16px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.md}"
    padding: "6px 12px"
  select-control:
    backgroundColor: "{colors.bg-input}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
    padding: "6px 10px"
  composer:
    backgroundColor: "{colors.bg-input}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.2xl}"
    padding: "8px 12px"
  chat-entry:
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.lg}"
    padding: "10px 12px"
  chat-entry-active:
    backgroundColor: "{colors.bg-active}"
    textColor: "{colors.text-primary}"
  citation-pill:
    backgroundColor: "{colors.citation-bg}"
    textColor: "{colors.accent-contrast}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  message-user:
    backgroundColor: "{colors.user-bubble}"
    rounded: "{rounded.2xl}"
    padding: "12px 16px"
---

# Design System: MiniRAG Chat

## 1. Overview

**Creative North Star: "The Reading Room"**

MiniRAG's chat surface is a quiet, private room for interrogating your own
library. It is not a destination and not a brand statement; it is the desk you
sit at to ask your documents a question and read a cited answer. Density is
moderate, the palette is restrained, and exactly one color is allowed a voice,
the **Signal Green** accent that marks what is live, selected, or sourced.
Everything else is neutral so the documents and the answer carry the screen. The
interface earns trust by disappearing into the task and showing its work.

The system explicitly rejects the consumer-chatbot costume (oversized speech
bubbles, emoji affordances, a chatty mascot persona) and the marketing-page
reflex (decorative gradients, glassmorphism, gradient text, hero-metric blocks).
It also refuses the opposite failure: a "clean" minimal veneer that hides the
retrieval mechanics. For this audience, visible mechanics, citations, search
mode, alpha, and live status, are a feature, not clutter. Surfaces are flat and
separated by tone rather than lifted by shadow; the single soft shadow in the
system is reserved for true overlays. Type is one system sans with a monospace
partner for code. There is no display face, because a reading room has no
marquee.

It ships two themes of equal standing, a default low-glare dark and a warm paper
light, switchable from the top bar and remembered per user. Both must hold the
same contrast bar; neither is an afterthought.

**Key Characteristics:**
- Restrained by default; one accent (Signal Green) and a neutral surface stack.
- Flat surfaces, depth from tonal layering and 1px hairline borders.
- Single system-sans family plus a monospace stack for code and identifiers.
- Retrieval is legible: citations, search mode, and status are first-class UI.
- Quiet, recessive controls; only the active or primary control wears the accent.
- Dual dark/light themes, both held to WCAG AA.

## 2. Colors

A near-monochrome neutral stack with one teal-green accent. Color is information,
never ornament: the accent appears only on primary actions, the current
selection, citations, and live state.

### Primary
- **Signal Green** (dark `#10a37f` / light `#0f8f72`): the only voiced color.
  Used for the send button, the focused input/control border, the current chat
  selection indicator, citation pills, and the "live" status dot. Hover deepens
  to `#0d8c6d` (dark) / `#0b755d` (light). Text on the accent is white
  (`#ffffff`).

### Neutral
The reading room is built almost entirely from neutrals, layered by tone to
create structure without lines or shadows.

- **Canvas** (dark `#212121` / light `#f7f7f4`): the main chat reading surface.
- **Recessed surface** (dark `#171717` / light sidebar `#efeee9`, top bar
  `#ffffff`): sidebar and top bar, set behind the canvas by tone.
- **Raised control** (dark `#2f2f2f` / light `#ffffff`): inputs, selects, the
  composer, and the user message bubble. Also the hover wash on list rows.
- **Active row** (dark `#343541` / light `#ddd9ce`): the selected conversation.
- **Ink** (dark `#ececec` / light `#202124`): primary text.
- **Muted ink** (dark `#b4b4b4` / light `#4f545c`): secondary text, captions.
- **Faint ink** (dark `#a1a1b0` / light `#6b6660`): placeholders, labels, and
  status. Tuned to clear the body contrast bar on the lightest surface each
  appears on (composer/settings `#2f2f2f` dark; sidebar `#efeee9` light).
- **Hairline** (dark `#444444` / light `#d4d0c7`): borders and dividers, the
  primary structural device in a shadowless system.

### Semantic State
- **Error** (dark `#f87171` / light `#b42318`): failed sends, error status,
  inline error text. The dark value is lightened from the base red so error text
  clears AA on the canvas and the raised-control surface.
- **Warning** (dark surface `#5c2d2d` on text `#f8d7da` / light surface
  `#fff1f0` on text `#a8071a`): the save-failure banner only.
- **Code** (dark `#1e1e2e` / light `#f0eee7`): code-block background, set apart
  from the raised-control surface so code reads as a distinct material.

### Named Rules
**The One Voice Rule.** Signal Green carries meaning, never decoration. If a
green element is not an action, the current selection, a citation, or live state,
it is wrong. On any given screen the accent should cover well under 10% of
pixels; its rarity is what makes it readable as a signal.

**The No-Wash Rule.** Never set gray text on the accent or on a saturated
surface. Text on Signal Green is white; text on the warning banner uses the
banner's own deep hue. Muted gray on a tinted surface is the system's banned
look.

## 3. Typography

**Body / UI Font:** system sans (`-apple-system, BlinkMacSystemFont, 'Segoe UI',
Roboto, 'Helvetica Neue', sans-serif`)
**Mono Font:** `'SF Mono', 'Fira Code', 'Consolas', monospace`

**Character:** Native, invisible, trustworthy. The system font means the tool
looks like it belongs on the user's OS rather than wearing a brand typeface; the
monospace partner gives code, paths, and citation keys their own exact texture.
No display face: hierarchy comes from size, weight, and color, not from a second
personality.

### Hierarchy
- **Body** (400, 16px, 1.6): assistant and user message prose. Markdown headings
  inside answers scale relative to this (h1 1.4em, h2 1.2em, h3 1.05em); they are
  in-content structure, not page chrome.
- **UI** (400, 13–15px): controls, chat list rows, selectors, composer input
  (15px). The working size of the interface.
- **Label** (600, 12px, +0.5px tracking, uppercase): section labels and the
  message role marker ("ASSISTANT"). The only place uppercase is permitted, and
  only on strings of one or two words.
- **Mono** (400, 0.85em block / 0.9em inline): code blocks, inline code, and
  anything that is a literal token (paths, identifiers, citation keys).

### Named Rules
**The Reading-Width Rule.** Message prose is capped at a fixed reading column
(768px / roughly 70ch), centered on the canvas. The chat is for reading; line
length is protected even when the window is wide.

**The Uppercase-Label Rule.** Uppercase + tracking is reserved for one- or
two-word labels (12px). Never set a sentence, a button, or body copy in caps.

## 4. Elevation

Flat by default. Depth is built from a four-step tonal surface stack (recessed
sidebar/top bar → canvas → raised control → active row) and 1px hairline
borders, not from drop shadows. This keeps the room calm and legible at any zoom.

One exception is sanctioned: **true overlays** that float above the page (the
search-settings panel, the export menu) may lift with a single soft ambient
shadow so they read as detached from the surface beneath. This is the only
shadow in the system. Everything anchored to the layout stays flat.

> Implemented: the settings panel and export menu carry the `--shadow-overlay`
> token below. Every other surface stays flat.

### Shadow Vocabulary
- **Overlay** (`box-shadow: 0 8px 24px rgba(0,0,0,0.32)` dark /
  `0 8px 24px rgba(0,0,0,0.12)` light): floating panels and menus only.
- **Focus ring** (`box-shadow: 0 0 0 3px <accent-ring>`): the live-status dot on
  the theme button, and the model for accessible focus indicators elsewhere.

### Named Rules
**The Flat-Anchor Rule.** Anything that belongs to the layout (cards, rows,
bars, bubbles, inputs) is flat. If you are reaching for a shadow on an anchored
element, you want a tonal surface step or a hairline border instead. Shadow is
for things that float, and almost nothing floats.

## 5. Components

Buttons, selects, inputs, and toggles are quiet and recessive: neutral at rest,
with the accent reserved for the one primary or active control. Feedback on
interaction is unambiguous; decoration is absent.

### Buttons
- **Shape:** small radii. Send button 10px (`{rounded.xl}`), text buttons 8px
  (`{rounded.lg}`) or 6px (`{rounded.md}`).
- **Primary (Send):** Signal Green fill, white glyph, 32×32 square-ish. Hover
  deepens to `#0d8c6d`. Disabled drops to the hover-gray surface at 50% opacity.
  This is the only always-accented button.
- **Secondary (New Chat):** raised-control fill (`#2f2f2f`), primary ink, 1px
  hairline border, padding 10px 16px. Hover lifts the fill one tonal step.
- **Ghost (Export, Settings):** transparent fill, muted ink, 1px hairline,
  padding 6px 12px. Hover fills with the hover wash and brightens text to ink.
- **Theme toggle:** a labeled ghost variant carrying a Signal Green status dot
  (`::before`, 8px, with a soft accent ring). The dot is live state, not
  decoration.

### Chips (Citation Pills)
- **Style:** a deeper Signal Green fill (`#0b7a5e`, the `citation-bg` token) so
  the small bold white label clears WCAG AA, white text, fully rounded
  (`{rounded.pill}`), 0.75em / 600, padding 2px 8px, inline at the baseline of
  answer prose. The fill stays in the accent's hue family (One Voice), just deep
  enough to carry white text; the brighter base accent is for larger marks only.
- **Role:** marks a source reference inside a generated answer. This is the
  retrieval-is-legible principle made visible; never restyle it into invisibility.

### Cards / Containers
This system avoids cards. Conversations are list rows, not cards; messages are
prose blocks (assistant) or a single rounded bubble (user). Use tonal surfaces
and spacing to group, not bordered card shells.

- **User bubble:** raised-control fill, 16px radius (`{rounded.2xl}`), padding
  12px 16px, inset from the left so authorship reads by alignment.
- **Assistant message:** no container at all, prose directly on the canvas with a
  small uppercase role label above it.

### Inputs / Fields
- **Composer:** raised-control fill, 1px hairline, 16px radius
  (`{rounded.2xl}`), auto-growing textarea (24–200px). Focus shifts the border to
  Signal Green (`:focus-within`). Placeholder uses faint ink, held to the body
  contrast bar.
- **Selects (Model, Corpus, search Mode):** raised-control fill, 1px hairline,
  6px radius, padding 6px 10px. Focus border shifts to Signal Green.
- **Number / Range (Top-K, Alpha):** same field vocabulary; range uses
  `accent-color` so the slider track is Signal Green.

### Navigation (Sidebar)
- **Style:** a fixed 260px recessed column. Conversation rows are 8px-radius list
  items in muted ink; hover applies the wash; the active row uses the active-row
  surface and primary ink. Row actions (rename, delete) reveal on hover.
- **Mobile:** not yet handled. The 260px sidebar is fixed; a collapse/overlay
  pattern is the natural next step (structural, not fluid type).

### Toggle Switch (Reranking)
- 40×22 track, fully rounded; 16px knob. Off: hairline border, muted-ink knob on
  canvas. On: Signal Green track and border, white knob translated right. Pure
  state communication, no labels inside the track.

### Status Line
- A sticky, muted, 12px line pinned to the bottom of the chat column for live
  retrieval/streaming status. The error variant switches the text to the error
  color. This is a signature component: it is how the tool shows its work in real
  time, and it should remain present, quiet, and honest.

## 6. Do's and Don'ts

### Do:
- **Do** keep Signal Green to actions, current selection, citations, and live
  state, under ~10% of any screen (The One Voice Rule).
- **Do** build depth from the tonal surface stack and 1px hairlines; reserve the
  single soft shadow for floating overlays only (The Flat-Anchor Rule).
- **Do** hold all text, including placeholders, labels, and the faint-ink role,
  to WCAG AA: ≥4.5:1 for body, ≥3:1 for large/bold. The faint-ink role is tuned
  for this (`#a1a1b0` dark / `#6b6660` light); re-verify on the lightest surface
  if you change it.
- **Do** keep both dark and light themes to the same contrast and state
  vocabulary; neither theme is a second-class citizen.
- **Do** honor `prefers-reduced-motion: reduce` for every transition (toggle,
  hover, the loading-dots animation): provide an instant or crossfade fallback.
- **Do** keep message prose in the fixed reading column (~70ch) and let code,
  paths, and citation keys render in the mono stack.
- **Do** keep retrieval mechanics visible: the status line, citation pills, and
  the search-settings controls are features, not noise.

### Don't:
- **Don't** dress this as a consumer chatbot: no oversized cartoon bubbles, no
  emoji-led affordances, no mascot or chatty persona. It is an instrument.
- **Don't** add marketing-page visual language: no decorative gradients, no
  glassmorphism, no `background-clip: text` gradient text, no hero-metric blocks.
- **Don't** hide retrieval mechanics behind a "clean" minimal veneer; a polished
  surface must never cost transparency.
- **Don't** let it read as an uncredited clone of a well-known consumer chat
  product; small, deliberate choices should signal this is its own local-first
  tool.
- **Don't** set gray text on the accent or on any saturated surface (The No-Wash
  Rule). Use white on Signal Green and the surface's own deep hue elsewhere.
- **Don't** put shadows on anchored elements, or introduce a second accent color.
  One voice, flat anchors.
- **Don't** use a display typeface or uppercase anything longer than a two-word
  label.
