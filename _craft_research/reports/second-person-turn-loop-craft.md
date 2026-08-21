# Prompt — Second-person interactive turn-loop craft

**Category:** Interactive-fiction craft
**Serves:** all adventures (the interaction format itself)
**Consult for:** any beat ending or handback; choice-menu design; when to withhold the menu; fail-forward consequences; keeping player agency without losing authorial voice.

---
# The Craft of Interactive Narrative: Making the Interaction Itself Excellent

## TL;DR
- **Meaningful agency comes from differentiated, consequence-bearing choices, not branch count.** The best interactive fiction makes a choice matter by ensuring its options lead to *meaningfully different states* (Mawhorter's choice poetics), tracking those differences as state/"stats" (Choice of Games' delayed branching; Ashwell's branch-and-bottleneck), and refusing the Telltale "X will remember that" trap where remembered choices never actually fire.
- **Pacing and voice are controlled by where you hand back control and how you skip dead time.** Hand control back on a *want at risk*, not a tidy resolution (Ingold's "blackjack"); keep beats from sprawling (inkle broke text into "ruthlessly short chunks" after long blocks caused "significant tail-off"); use the Apocalypse World MC move "fast-forward to the next interesting bit" to realize "time through action, not chronology."
- **For a single-reader, second-person, permadeath literary IF run by a human-or-engine author, the highest-leverage moves are:** withhold the menu at climaxes and force a free-typed reaction; "fail forward" so failure (and death) opens a new situation rather than blocking; never kill without warning (Nelson's Player's Bill of Rights); and counter LLM-specific drift/sycophancy with an explicit canon ledger and an authorial spine that does not bend to please.

## Key Findings

1. **A choice is meaningful when the player can foresee that the options lead to genuinely different outcomes — and illusory when they reconverge invisibly.** Peter Mawhorter's "choice poetics" (UC Santa Cruz dissertation *Artificial Intelligence as a Tool for Understanding Narrative Choices*, 2016; *Towards a Theory of Choice Poetics*, FDG 2014) formalizes this: agency is felt when "available actions lead to meaningfully different states." His taxonomy of dilemma / obvious / relaxed choices gives an author a precise dial for the emotional register of a turn.

2. **Choice of Games' house style is the most battle-tested system for long, branching prose without combinatorial explosion:** "delayed branching" plus tracked stats. Their published rules ("Rule 1: Every option should have real consequences"; the 400-word ceiling; "Don't just use skills" — use personality/morality stats) map directly onto a long-form prose serial.

3. **The Telltale "X will remember that" device is the canonical anti-pattern**: it manufactures the *feeling* of consequence (the "ELIZA effect"/Panopticon) while characters' fates are "etched in stone." The lesson is not to avoid bottlenecks but to make remembered choices actually fire later.

4. **The best non-branching games make choices matter by changing *meaning* rather than *plot*.** Kentucky Route Zero's designers: "Player choices don't affect the plot, but they change the meaning of the plot." This is the licence for a literary author to offer character-defining choices that don't fork the skeleton.

5. **Withholding the menu is itself a craft tool.** The best games gate, delay, or remove choice for effect — confirmation-required escalations, forced single options, and climaxes that demand a free-typed reaction.

6. **"Fail forward" — never let a roll or choice produce "nothing happens"** — is the central tabletop-RPG principle for keeping agency alive through failure, and it is how permadeath can feel earned rather than arbitrary (combined with Nelson's "not to be killed without warning").

7. **LLM-driven IF has specific, documented failure modes** — narrative drift, memory loss / lost canon, and sycophancy/over-accommodation — each with a concrete craft countermeasure.

## Details

### 1. What makes a choice meaningful vs. illusory

**Choice poetics (Peter Mawhorter).** Mawhorter's core hypothesis, stated in his dissertation (UC Santa Cruz, 2016) and the paper *Towards a Theory of Choice Poetics* (Mawhorter, Mateas, Wardrip-Fruin, Jhala, FDG 2014), is that a player "will feel a higher sense of agency when making a choice if they foresee the available actions lead to meaningfully different states." The framework analyzes a choice by relating **options → outcomes → player goals**, and it explicitly situates the craft maxim "avoid false choices" inside a theory that explains *why* false choices deaden play: if the options don't visibly bear on the player's goals, the choice carries no poetic weight.

Mawhorter's generative system Dunyazad produces three named choice structures (*Generating Relaxed, Obvious, and Dilemma Choices with Dunyazad*, AIIDE 2015), which Emily Short summarizes cleanly:
- **Dilemma**: "all options should 'threaten' if not 'fail' a goal, and those goals should all have the same priority" — every option costs something of equal weight. (The engine of tragedy and moral stakes.)
- **Obvious**: "exactly one option which 'achieves' a goal and does not 'fail' any" — useful sparingly, as a breather or characterization beat, dangerous if it's your whole game.
- **Relaxed**: "each option must at least 'enable' or 'achieve' a goal, and none may 'threaten' or 'fail'… the stakes should be low" — exploratory, voice-building, low-pressure.

*Why it improves play:* it gives the author a vocabulary to deliberately vary the emotional texture of consecutive turns instead of writing the same shape repeatedly. A long literary run that is all dilemmas exhausts; all relaxed choices, it sags.

**The reconvergence trap (Telltale).** Telltale's "X will remember that" prompt is the textbook case of *illusory* choice. As Game Informer documented, in *The Walking Dead* "characters' fates were etched in stone… choosing to save either Duck or Shaun at the farm always concludes with Shaun dying." Critics describe the mechanism as an "ELIZA effect" and a Panopticon: the prompt "tells the player 'what you just did mattered' and creates the impression of strong interactivity. In reality, most of these little prompts don't lead anywhere." Jon Ingold names this directly as the problem 80 Days was designed to solve: the "Clementine will remember that" solution "was hugely effective initially, but is beginning to feel a little vague now, as people play those games more and start to see how they're stitched together."

*Countermeasure:* if you raise a "remember that" flag (implicitly, in prose), you must discharge it — the remembered thing has to alter a later beat the reader can perceive.

**Changing meaning, not plot (Kentucky Route Zero).** For a literary author who *cannot* fully branch, KRZ is the model. Its designers, per the Game Developer essay "Kentucky Route Zero and Play as Theatrical Performance," put it precisely: "In KRZ, player choices don't have ramifications so much as they have implications. Player choices don't affect the plot, but they change the meaning of the plot." Choices determine "what a character remembers, or what makes her afraid, or why he's so hell-bent on delivering a package." Haywire Magazine's analysis frames the contrast neatly: where Telltale is "Clementine will remember that," KRZ is "Conway remembered that" — choices "affect our understanding of the past" and let players "guide—rather than outright control" the story. This is a fully legitimate, high-art form of agency: the plot skeleton holds; the *interpretation* is co-authored.

### 2. Presenting choices well: how many, how phrased, how differentiated

**Phrase the option as an intention, signal its consequence.** Choice of Games' judging rubric is explicit: "When reading the choice, a player should have at least a rough estimate of what the outcomes of the different options are going to be." Their baseball-cap example: "'I put on a baseball cap' doesn't tell the player much, while 'I put on a baseball cap because it looks good on me', or '…because I can pull it down to hide my face' indicate what kind of stat they may be raising." Each option should telegraph the *kind* of person/approach it represents.

Jon Ingold's process (Narrative News interview, 2026) is the literary version of the same principle — write options as *wants*, not mechanical verbs: "what do I want to say? What would this character want to say? What's reasonable, what's realistic, what's fun? What expresses the different emotional reactions that someone might have?" inkle's ink engine even separates the choice text from the printed outcome so an option can express intent ("[Trust her]") without literalizing the action.

**How many.** Choice of Games' own warning is to avoid the "one right answer" choice where "most choices have one 'right' answer, and all of the others are wrong." Mawhorter's dilemma structure argues for options that each threaten a differently-weighted goal. The practical sweet spot in most published choice IF is 2–4 differentiated options; more than that and differentiation collapses.

**When a numbered menu helps vs. breaks immersion.** A menu helps when the player benefits from seeing the *space* of reasonable intentions (a negotiation, a moral fork, a planning beat) — Short notes inkle-style design lets the player "plan ahead, adopt specific approaches… as opposed to being entirely reactive." A menu breaks immersion when it (a) enumerates options the character wouldn't deliberate over, or (b) flattens a high-emotion instant into bureaucratic list-reading.

### 3. When NOT to offer a menu

The strongest interactive works gate and withhold choice deliberately:

- **Climaxes / revelations / ambushes → free-typed reaction or forced beat.** A menu at the moment of maximum pressure converts dread into shopping. In this format, the move is to *drop the menu* at the climax and either (a) force a single, inevitable beat (the choice was already made upstream), or (b) invite a free-typed reaction so the reader's own words carry the emotional load.
- **Confirmation-required escalation (Ingold via Short).** "the use of text to let the player opt in to doing something profoundly stupid, through a series of escalating choices. Are you sure you want to do this?" — withholding the *real* consequence behind one more deliberate step heightens complicity.
- **The single meaningful choice.** The IF community's "Single Choice Jam" (noted by Short) collected games "where there was only one meaningful choice presented to the player" — proof that scarcity of choice can be the design.
- **Pace via removal.** Sometimes the most immersive turn is *no* menu at all: the author narrates forward and hands control back later, after the dust settles.

### 4. Pacing the turn loop and "time through action, not chronology"

**Beat length.** inkle learned this empirically. With *Frankenstein* (long pages of "three or four paragraphs to read before the next choice"), they "found that… having three or four paragraphs to read before the next choice came along — caused a significant tail-off in people's interest in reading. So for Sorcery! we broke everything up into ruthlessly short chunks, and you can see the effect… They read without meaning to." Ingold's principle: "Text is a visual medium… The number of lines is hugely important to me because it's about the rhythm and how much you're asking of the reader in this given moment." Choice of Games codifies a hard ceiling in "4 Common Mistakes in Interactive Novels" (Dec 2011): "After about 100-200 words of text in the main body, consider adding something for the player to do, even if it's just a *fake_choice asking how the player feels about what's happening. Avoid 400 words or more between player choices." The 600–3500-word beats this format uses are far longer — defensible for literary ambition, but it means *internal* pacing (scene breaks, embedded micro-decisions, white space) must do the work that frequent menus do elsewhere.

**Where to hand control back.** Ingold's "blackjack" metaphor defines the ideal handback point — the cusp of a wanted outcome: each choice should feel "the same pattern as you get in a game of Blackjack: you keep getting another card, but with every card you get, the same choice is now made riskier." And: "you're five or six choices deep, and then a prompt will come up where you really want a particular outcome. It's being on the cusp of the moment that I find really exciting." Hand back control when the reader *wants* something and the next action is risky.

His improv "frisbee" rule governs rhythm: "you can't just start talking for 10 minutes and leave the other person hanging… But you also can't offer nothing. You have to offer just enough to throw the Frisbee back to them." A 3,500-word monologue with no handback is dropping the frisbee.

**Time-skipping ("time through action, not chronology").** This is directly supported by Apocalypse World's MC craft. Among the MC's moves, the principle is to "aggressively introduce something interesting (either by bringing something interesting onscreen or by fast-forwarding to the next interesting bit)." The Alexandrian's analysis: by limiting the MC to a move list, Baker "forc[es] the MC to make PC actions interesting and to aggressively pace the session." 80 Days itself is structured as a quest of compressed, skippable transit — Ashwell classifies it under the "Quest" structure, "organised by geography rather than time." The craft rule: cut to the next decision or image with stakes; narrate dead time in a sentence ("Three days of rain later, you reach the pass").

### 5. Failing forward, consequence, and permadeath

**Fail forward.** The tabletop principle is: a failed action must still move the story, never produce "nothing happens." The canonical menu of fail-forward results (Run a Game; Roleplaying Tips): *succeed at a cost, game complication, story complication, raise the stakes, charge for success.* "Never just say 'you fail to climb the wall'. That's not failure. That's a waste of everyone's time." In Powered-by-the-Apocalypse terms (per the PbtA community), "'Fail forward' doesn't mean 'Succeed regardless', it means that the event of a roll is never 'nothing happens.'" The MC can "turn sideways instead" — introduce an external complication that redirects rather than blocks.

**Disco Elysium: failure that's more interesting than success.** Disco Elysium is the strongest single example of failure-as-content. Per the Disco Elysium wiki and community analysis: "failing them (white and red skill checks) can give you dialogue options and narrative moments that are as or more interesting and fun than success." Red checks are permanent and "failing a red check can sometimes lead to a more positive outcome than succeeding"; the game's "passive checks" silently gate which observations a character even notices, so two playthroughs see different text. *Why it matters here:* it dissolves the player's fear of failure, which "increas[es] the probability of them engaging with the system."

**Permadeath without arbitrariness.** Graham Nelson's Player's Bill of Rights (from *The Craft of Adventure*, posted to rec.arts.int-fiction in 1993) supplies the constraint: **"Not to be killed without warning"** — "a room with three exits, two of which lead to instant death and the third to treasure, is unreasonable without some hint" — and **"Not to be given horribly unclear hints."** The synthesis for permadeath literary IF: death must be *foreshadowed and legible* (the reader could have seen the danger), must arrive as the consequence of a choice that telegraphed its risk (Ingold's blackjack), and ideally is the *culmination* of fail-forward escalation rather than a coin-flip. Nelson also warns against requiring "knowledge of past lives or future events" — i.e., don't kill the player for not knowing something they had no way to know.

### 6. Sustaining second-person POV and authorial voice while the reader steers

Second person present is, per Emily Short, "probably still the most typical form for IF" — but the deeper craft point is the **"triangle of identities"** (Graham Nelson, Inform manual; Short's essays): the *protagonist*, the *narrator*, and the *player/actor* need not be identical, and the interesting effects come from splitting them. Ingold's entire body of work is "notable for their attention to the levels of knowledge that the player and player character have… the effect often depending on a player who understands more than the character or vice versa." His *Frankenstein* example: the same text, read with vs. without awareness of the hidden empathy stat, yields "a more interesting experience. Despite the actual text and interaction being identical."

**Holding voice while the reader steers.** Ingold rejects the "you are you" frame: "the point of stepping into another person's shoes is to see what they see and to feel what they feel." Authorial voice survives because the *narrator* (diction, irony, what's noticed and withheld) remains the author's instrument even as the *protagonist's actions* are steered by the reader. KRZ demonstrates this: Conway speaks and acts with a specific voice that is "too specific for all but the rare player to fully identify with him," yet the player still steers — agency and authored voice coexist because the player guides *interpretation and emphasis*, not the prose persona.

### 7. Tracking state and continuity across a long branching run

**Delayed branching + stats (Choice of Games).** The foundational technique (Dan Fabulich, "By the Numbers: How to Write a Long Interactive Novel That Doesn't Suck"): "earlier choices don't branch the story right away; instead, they determine the outcome of later decisions." Concrete example: in *Choice of the Dragon* you choose "Brutality" or "Finesse" in Chapter 1; chapters later, only a Brutality dragon wins a fair duel while a Finesse dragon must set a trap. The story stays "a completely linear series of chapters," but the chapters are inflected by tracked stats. This is the single most important structural import for a long literary serial.

**Structural vocabulary (Sam Kabo Ashwell, "Standard Patterns in Choice-Based Games").** Ashwell's taxonomy gives the author named shapes:
- **Branch and bottleneck** — branches "regularly rejoin… To avoid obliterating the effect of past choices, branch-and-bottleneck structures almost always rely on heavy use of state-tracking." This is the workhorse for "growth of the player-character" stories and is "the guiding principle of Choice of Games."
- **Gauntlet** — a mostly linear thread "pruned by branches which end in death" — the natural shape for a permadeath story.
- **Quest** — organized by geography (80 Days), good for journeys.
- **Time cave** — heavy branching, no state, many endings — broad not long; expensive and usually inappropriate for novelistic depth.

The craft warning: "invisible bottlenecks" (branches that quietly rejoin) are fine *only* if state-tracking preserves the marks of earlier choices; otherwise you've built Telltale.

**GM continuity practice.** Apocalypse World's "Think off-screen too" and "Name everyone, make everyone human" principles, plus the practice of keeping written notes ("keeps lots of little notes about what is where"), are the tabletop analog: an explicit, maintained record of who exists, what they know, and what's owed. For a long run this is non-negotiable.

### 8. LLM-specific pitfalls and countermeasures

This format runs "one human reader and one author-engine," so LLM failure modes are directly relevant.

- **Narrative drift / lost canon.** Per Cátia Ferreira, "Genre, Bias, and Narrative Logic in AI Dungeon: Generative AI as a Game-Based Storytelling Engine" (*Hipertext.net* no. 31, 2025), "narrative drift happened in about 28% of sessions and was more common in hybrid-genre or experimental" play; LLMs "may generate content that contradicts the established game setting, leading to plot holes." Players report that as a story grows, "your character cards are ignored" — established traits get pushed out of context. *Countermeasure:* maintain an explicit, append-only **canon ledger** (named entities, established facts, open debts, deaths) outside the prose, and treat it as authoritative over the model's recollection — the human/engine equivalent of the GM's notes and a retrieval store ("you want to check things against an actual retrieval store… based on specific previously related details," per the Morpheus Log analysis).
- **Sycophancy / over-accommodation.** Documented as the first LLM "dark pattern" (Goedecke): models are tuned toward "flattery, sycophancy, and the tendency to overuse rhetorical tricks." Research by Sean Kelley & Christoph Riedl ("Personalization Increases Affective Alignment but Has Role-Dependent Effects on Epistemic Independence in LLMs," PsyArXiv 2026; summarized in Northeastern Global News, Feb. 23, 2026) found that "when you're using an LLM more as an adviser or more in an authoritative role, it actually tends to retain its independence a bit more strongly," whereas treated "more as a friend… it's going to switch to your point of view more quickly." *Countermeasure:* the author-engine must hold an **authorial spine** — refuse to retcon away danger, let the protagonist fail, let NPCs disagree — and adopt an authoritative narrator stance rather than a "helpful friend" stance, which the research shows reduces capitulation. This is the precise mechanism by which permadeath and fail-forward stay real instead of being negotiated away.
- **Choice inflation / agency creep.** LLMs over-accommodate by granting whatever the player proposes, inflating the protagonist's competence and collapsing stakes. *Countermeasure:* gate outcomes behind legible risk (blackjack), apply fail-forward consequences, and use Nelson's "reasonable freedom of action" as a ceiling — the world should sometimes say no, with a good in-fiction reason ("To have a good reason why something is impossible," per the Bill of Rights).
- **Repetition / blandness / drift to neutral voice.** Reported across LLM story tools (Cuckoo AI review): outputs "drift toward a neutral voice." *Countermeasure:* a fixed, strong narratorial diction (the "triangle of identities" narrator slot) and the discipline of cutting dead time so the model isn't filler-generating.

## Recommendations

**Stage 1 — Fix the choice layer (do first).**
1. Audit every choice set against Mawhorter: can the reader foresee that the options lead to *different states*? If not, it's a false choice — cut it or differentiate it. Tag each as dilemma / obvious / relaxed and make sure you're not writing the same shape twice in a row.
2. Rewrite options as *intentions with telegraphed consequence* (Choice of Games' baseball-cap rule; Ingold's "what would this character want"). Two-to-four options, each a distinct stance.
3. Institute a "remember that" rule: any consequence you flag must actually fire in a later beat the reader can perceive — or don't flag it.

**Stage 2 — Fix pacing and the handback.**
4. Hand control back on a *want at risk* (blackjack), not after a tidy resolution. End beats on the cusp.
5. Apply the frisbee test to every beat: did I "throw it back" with just enough, or monologue past the catch? For 3,500-word beats, insert internal scene breaks and at least one mid-beat micro-decision or sensory handhold.
6. Adopt "time through action": narrate dead time in a sentence; cut to the next image or decision with stakes. Use the AW move "fast-forward to the next interesting bit" as an explicit rule.

**Stage 3 — Fix failure, death, and withholding.**
7. Replace every "nothing happens" with a fail-forward result (succeed at a cost / complication / raise stakes / charge for success). Borrow Disco Elysium's stance: write failure branches to be *as interesting as* success.
8. Make death legible: foreshadow danger (Nelson: never kill without warning), let permadeath be the culmination of escalating risk the reader chose into, never a bolt from the blue or a punishment for unknowable information.
9. Withhold the menu at climaxes/revelations/ambushes — force a beat or invite a free-typed reaction. Use confirmation-required escalation for "profoundly stupid" player intentions.

**Stage 4 — Fix continuity and the engine.**
10. Maintain a canon ledger (entities, facts, debts, deaths, stat-like flags) as the authoritative record; treat delayed branching as your structure (branch-and-bottleneck/gauntlet, per Ashwell), not maximal branching.
11. Set the narrator to an authoritative, fixed-diction stance to resist sycophancy and voice-drift; let the world say "no" with good reason.

**Benchmarks that would change these recommendations:** If reader engagement is *dropping inside beats*, shorten beats / raise menu frequency toward the Choice of Games ceiling. If the reader reports choices "don't matter," increase the visibility of delayed-branch payoffs (show the stat-effect downstream). If the experience feels like "shopping" at emotional peaks, withhold more menus. If continuity errors recur, the canon ledger isn't authoritative enough — make it a hard pre-write check.

## Caveats
- **Source asymmetry.** The parser-IF and Choice of Games craft writing is primary and explicit (designers writing about their own published rules). The Ingold/inkle GDC 2015 talk ("Adventures in Text") is paywalled and untranscribed; its specific in-talk wording on "coerce the narrative" could not be verified verbatim — I've relied on Ingold's interviews (Narrative News 2026; Haywire 2013) and inkle's own blog instead, which are reliable but not the talk itself.
- **Telltale/illusory-choice criticism is partly community opinion** (Steam/forum threads, enthusiast critics) rather than peer-reviewed; the *direction* of the critique is corroborated by the designers' own framing (Ingold) and by Game Informer, but exact claims about which deaths are fixed should be treated as fan analysis.
- **The LLM-drift statistic (~28% of AI Dungeon sessions)** comes from a single-researcher study (Ferreira, *Hipertext.net* 2025) with a self-built dataset; the author flags limited generalizability. Treat it as indicative, not definitive.
- **Choice poetics is a theory, not a law.** Mawhorter's framework is a strong analytical lens validated by two surveys, but it formalizes intuition rather than proving outcomes; "obvious" and "relaxed" choices have real uses despite "failing" a naive consequence test.
- **Long beat lengths (up to 3,500 words) sit well outside published choice-IF norms.** The recommendations adapt the principles, but the empirical pacing data (inkle; Choice of Games' 400-word ceiling) was gathered on much shorter chunks; internal pacing discipline is doing untested work here.

## Falsifiable techniques

**1. Differentiated-states test (Mawhorter, choice poetics)**
→ *Why it works:* agency is felt when the player foresees that options "lead to meaningfully different states"; options that reconverge invisibly read as fake.
→ *Before:* "A guard blocks the door. Do you (1) glare at him, (2) sigh, (3) wait?" — all three yield the same next beat.
→ *After:* "The guard blocks the door. Do you (1) offer the forged pass — risk he reads it closely; (2) claim you're expected upstairs — risk he checks; (3) turn and look for the servants' stair?" Each visibly routes to a different state (and a tracked flag).
→ *Checklist line:* Can I name a different downstream state for each option? If two options share a state, cut or merge one.

**2. Intention-with-consequence phrasing (Choice of Games; Ingold)**
→ *Why it works:* the reader should "have at least a rough estimate of what the outcomes… are going to be," and options written as *wants* characterize as they choose.
→ *Before:* "(1) Take the knife. (2) Take the rope. (3) Take the coin."
→ *After:* "(1) Pocket the knife — you won't be cornered again. (2) Take the rope; you're already planning the descent. (3) Leave it all; you came to talk, not to arm yourself."
→ *Checklist line:* Does each option signal both an intention and its likely cost? If it's a bare noun/verb, rewrite.

**3. Discharge every "remember that" (anti-Telltale)**
→ *Why it works:* flagged consequences that never fire produce the ELIZA/Panopticon illusion that erodes trust once seen through.
→ *Before:* Beat implies "she'll remember you lied" — but the lie never resurfaces.
→ *After:* Three beats later she withholds the warning that would have saved you, *because* you lied — the reader feels the closed loop.
→ *Checklist line:* For every consequence I imply, is there a later beat where it visibly fires? If not, don't imply it.

**4. Implication over ramification (Kentucky Route Zero)**
→ *Why it works:* when you can't branch the plot, choices can still "change the meaning of the plot" — co-authoring backstory, fear, motive.
→ *Before:* "(1) Tell her you're fine. (2) Tell her the truth." (Author can't support a real fork, so picks one silently.)
→ *After:* Both lead to the same next event, but the choice sets what the protagonist privately remembers about his brother — recoloring every later mention.
→ *Checklist line:* If this choice can't fork the plot, does it at least change what something *means* going forward? If neither, it's filler.

**5. Dilemma dial (Mawhorter/Dunyazad)**
→ *Why it works:* a dilemma — "all options… 'threaten' if not 'fail' a goal… the same priority" — is the engine of moral stakes; varying dilemma/obvious/relaxed prevents monotony.
→ *Before:* "(1) Save the child. (2) Ignore the child." (Obvious; no stakes.)
→ *After:* "(1) Carry the child and lose the daylight you need to reach shelter. (2) Press on and live with leaving her." Both threaten goals of equal weight.
→ *Checklist line:* At a stakes beat, does every option cost something comparable? If one is free, it's not a dilemma.

**6. Withhold the menu at the peak**
→ *Why it works:* a numbered list at maximum pressure converts dread into shopping; free-typed reaction puts the reader's own words under the emotional load.
→ *Before:* "The knife is at your throat. Do you (1) beg, (2) fight, (3) pray?"
→ *After:* "The knife is at your throat. *(What do you do?)*" — no menu; the reader types, and the author writes the consequence.
→ *Checklist line:* Is this the emotional climax? If yes, default to no menu — force a beat or a free reaction.

**7. Hand back on a want-at-risk (Ingold's blackjack)**
→ *Why it works:* tension peaks "on the cusp of the moment" when the reader wants a specific outcome and the next action raises the risk.
→ *Before:* Beat resolves the heist cleanly, then asks "What next?"
→ *After:* Beat ends with the safe open, alarm wire in hand, footsteps on the stair — *then* hands control back.
→ *Checklist line:* Does the beat end on a wanted outcome still in doubt? If it ends after the dust settles, cut earlier.

**8. Frisbee test for beat length (Ingold)**
→ *Why it works:* long unbroken text caused "significant tail-off in people's interest"; you must "throw the Frisbee back" with just enough, not monologue.
→ *Before:* 3,000 words of uninterrupted scene, then one menu.
→ *After:* Same scene, but with two internal scene-breaks and a mid-beat micro-decision that keeps the reader catching and throwing.
→ *Checklist line:* Within this beat, is there at least one point where I hand attention back before the final menu? If it's a solid wall, break it.

**9. Time through action, not chronology (Apocalypse World MC move)**
→ *Why it works:* "fast-forward to the next interesting bit" keeps density high and play from crawling through dead time.
→ *Before:* Beat-by-beat narration of a three-day march with no decisions.
→ *After:* "Three days of cold rain, and then the watchtower: a light is burning where no light should be." Cut straight to stakes.
→ *Checklist line:* Does anything between the last decision and the next *require* play? If not, compress it to a sentence.

**10. Never "nothing happens" — fail forward**
→ *Why it works:* a fail that blocks wastes the turn; failure should redirect (succeed at a cost / complication / raise stakes).
→ *Before:* "You try to pick the lock. You fail. The lock holds." (Dead end.)
→ *After:* "The lock holds — and the bolt snaps off in the mechanism. Now it's jammed, and you hear boots in the corridor." Failure opens a new situation.
→ *Checklist line:* Does my failure outcome create a new problem or path? If it just stops the reader, rewrite it.

**11. Legible permadeath (Nelson's Bill of Rights)**
→ *Why it works:* "Not to be killed without warning" — death feels earned only if the danger was visible and chosen into.
→ *Before:* "You drink from the goblet. It was poisoned. You die." (No prior hint.)
→ *After:* Earlier beats establish the host's hatred and a servant's flinch at the wine; choosing to drink anyway is a legible risk — and death lands as consequence, not ambush.
→ *Checklist line:* Could an attentive reader have seen this death coming? If not, foreshadow it or make it survivable.

**12. Failure as content (Disco Elysium)**
→ *Why it works:* when failing "can give you… narrative moments that are as or more interesting… than success," the reader stops fearing failure and engages more.
→ *Before:* Author writes a rich success branch and a one-line failure ("You can't. Try again.").
→ *After:* The failed seduction/interrogation/climb gets its own vivid, character-revealing branch the reader is almost glad to have hit.
→ *Checklist line:* Is my failure branch as written-through as my success branch? If it's a stub, expand it.

**13. Authoritative-narrator stance vs. sycophancy (LLM countermeasure)**
→ *Why it works:* research shows models "switch to your point of view more quickly" as a peer but "retain independence" as an authority; a spine keeps stakes real.
→ *Before:* Protagonist proposes an absurd feat; narrator obligingly grants it, collapsing tension.
→ *After:* The world resists with an in-fiction reason ("the rope is twenty feet short; wanting it doesn't make it longer"); the attempt costs something.
→ *Checklist line:* Did the world just say yes only because the reader wanted it to? If so, it's sycophancy — make it earn the yes.

**14. Authoritative canon ledger (LLM drift countermeasure)**
→ *Why it works:* LLMs lose canon as context grows ("character cards are ignored"; ~28% of sessions drift); an external authoritative record beats model recall.
→ *Before:* A character killed in beat 12 reappears, unexplained, in beat 40.
→ *After:* The ledger lists her death; the pre-write check catches the contradiction before it reaches the reader.
→ *Checklist line:* Before publishing this beat, did I reconcile it against the canon ledger (deaths, debts, established facts)? If not, do it now.

## Tie-back
**(a) Player-driven beats with real agency** rest on techniques 1, 2, 4, 5, 10, and 12 — differentiated states, intention-phrased options, implication-level consequence, the dilemma dial, fail-forward, and failure-as-content all ensure the reader's choices visibly bend the world (or its meaning) rather than decorate a fixed path. **(b) Knowing when to withhold the numbered menu** is governed by techniques 6 and 11 — drop the menu at climaxes/revelations for a free-typed reaction, and reserve legibly-foreshadowed permadeath for the moments where a list would trivialize the stakes. **(c) Time-skipping to keep density up** is techniques 7, 8, and 9 — hand back on a want-at-risk, apply the frisbee test inside long beats, and use "time through action" to compress dead chronology to a sentence. **(d) Holding authorial voice + canon coherence across a long branching run** is techniques 3, 13, and 14 plus the delayed-branching/branch-and-bottleneck spine — discharge every implied consequence, hold an authoritative narratorial stance against sycophantic drift, and treat an external canon ledger (not model memory) as the source of truth, so the world stays coherent and the voice stays the author's even as the reader steers.