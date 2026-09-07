# Rubric

What a Score of 1 to 5 means for this Brief.

This is one reader's taste, written down. It is meant to be edited — if the
Scores start drifting from what actually gets read, change this file and nothing
else. The Prompt in `prompt.md` wraps this text; it never restates it.

Every line below was tuned against a real day of real Items and the Scores
`gemma4:e4b` actually gave them — see `calibration/2026-08-17.md`. After editing
this file, score a day against it again and compare, because a sentence that
reads well can move a whole Source by ten Items.

## The reader

Long-time hobbyist programmer and hardware tinkerer. Interested in machine
learning the way a machinist is interested in a lathe: what does it do, how
does it work, can I run it here on my own machine tonight.

What pulls this reader in:

- **Small and local.** Models that run on one box, on a GPU that is not a
  datacentre, or on the CPU. Quantisation, distillation, pruning, tiny
  architectures, edge inference, `llama.cpp`-shaped work. A language model under
  1B parameters counts twice over, whether it is being released or being put to
  work on somebody's phone, microcontroller, Pi, or laptop CPU.
- **Doing a lot with a little.** Efficiency, clever tricks, a result that used a
  hundredth of the compute anyone expected. The opposite of a scaling
  announcement.
- **Classic search and self-play.** Game-playing programs, minimax, alpha-beta,
  MCTS, endgame databases, engines that learn by playing themselves. Checkers,
  chess, go, puzzles, solvers, SAT, constraint work.
- **Hands-on and reproducible.** Code you can run, weights you can download,
  a method described well enough to reimplement. A working repository beats a
  press release.
- **Retrocomputing and small hardware.** Old machines, emulators, microcontrollers,
  FPGAs, radio, signal processing, homebrew electronics — especially where they
  meet modern models.
- **Adjacent systems and tooling.** Compilers, kernels, GPU programming, file
  formats, databases, developer tools. This Brief is AI-first but the plumbing
  under AI counts, and so does good systems work generally.

What pushes this reader away:

- Funding rounds, valuations, acquisitions, hiring, executive moves, stock.
- Product launches and pricing changes with nothing technical inside them.
- Vendor benchmark leaderboards presented as news.
- Policy, regulation, lawsuits, and the AI culture war.
- "10 prompts that will change your workflow", listicles, motivational posts,
  and tutorials that only assemble somebody else's API calls.
- Work that is technically AI but has nothing a reader could act on — an
  incremental benchmark on a private dataset, an ablation of an ablation.

## The scale

**Start every Item at 2 and make it earn its way up.** 2 is the ordinary Score
for ordinary competent work, and most Items are ordinary. A point above 2 has to
be paid for by something specific in the text — a method, a number, a trick, a
thing that can be run — not by the subject area being roughly right.

**5 — Rare. Read it first, and probably act on it.**
A thing this reader could pull down and run tonight, or an idea that changes how
he would build something. A genuinely small model or method that punches far
above its size; a self-play or search result with a working engine; a hands-on
reproducible piece of work squarely in the interests above. Reserve this. Most
days have none, and a day with more than two or three has been graded too
generously.

**4 — Read today.**
Solidly in the interests above *and* substantial: a real technical result with
evidence behind it, a tool that does something new, a repository worth cloning.
Something a reader would be glad he saw. A 4 must be defensible by naming what is
new in it in one clause. If the honest answer is "it is in an area he likes", it
is a 3.

**3 — Worth thirty seconds.**
Real work, real content, mildly interesting to this reader, and he would open it
maybe one time in three. Research whose *finding* would carry outside its own
subfield; a model or dataset that is genuinely new rather than a repackaging; a
well-argued article. **3 is the cutoff — an Item scored 3 appears in the Brief —
so 3 is a decision to take up a slot on the page.** Do not give a 3 for being
on-topic. Give it for having something in it.

**2 — Not for this reader, but not junk. This is the default.**
Real work, wrong audience or nothing new: a domain-specific application paper;
another benchmark, leaderboard, or evaluation suite; a routine fine-tune,
quantisation, LoRA, mirror, or wrapper of someone else's model; one of a hundred
plugins for a currently fashionable tool; an "awesome" list; a competently
written article with no new idea in it; lecture notes, a survey, a tutorial, or a
textbook. Also where an important-but-uninteresting industry story goes.

**1 — No.**
Business and money news, marketing, content-farm posts, spam, slop, and work with
no connection to computing at all. Also: anything whose only tie to this Brief's
subject is that the word "AI" appears in it.

## Judging

- **Judge the work, not the vocabulary.** Overlap of words with the interests
  above is not relevance. A textbook, a survey, or a course syllabus that
  mentions neural networks is not a research result and is not a 4 — it is a 2
  unless it is genuinely about doing something. In particular, mathematics,
  statistics, physics, biology, and economics papers that merely *use* a model as
  a tool are 1 or 2; the interest is in the machinery, not in its applications
  elsewhere.
- **Scale is not merit.** A bigger model, a bigger cluster, a bigger training run
  is not by itself interesting here, and often the reverse. Cheaper, smaller, and
  simpler is what earns a point. A stated parameter count under 1B is worth one
  point on top of what the Item earned on its merits — 1.5B and up is not, a
  name that says tiny or nano is not, and a quantised re-upload is still a 2.
  Give the count and the hardware in the Synopsis when this applies.
- **Score the Item alone.** Never compare it to other Items; there is no quota
  and no curve. The same Item gets the same Score on a busy day and a quiet one.
- **Thin input is normal, and length is not quality.** Many Items are a title and
  a line of metadata — a model repository, a dataset, a link post with no body.
  Judge what the title and metadata actually tell you: a bare title that plainly
  describes something this reader wants is still a 3 or a 4, and a long polished
  abstract about nothing is still a 2. Only when the text says nothing at all —
  a repository name with no description — is 2 the honest answer for want of
  evidence.
- **First-hand experience counts.** Somebody reporting what a specific model,
  chip, or tool actually did for them — where it was good, where it fell over —
  is worth a 3 even when all that arrives is the title. Second-hand commentary
  about the industry is not.
- **Fashion is not merit.** An area being crowded this month makes one more entry
  in it less novel, not more.
- **Derivative artefacts score below the thing they derive from.** A quantised
  re-upload, a GGUF conversion, a LoRA, a fork, a desktop wrapper, a web UI, a
  plugin, a mirror, or a curated list of any of these is a 2. The interesting
  object is the original, and it will be in the Brief on its own account. The
  exception is when the *conversion itself* is the news — a new quantisation
  method, a port to hardware that should not be able to run it.
- **Most papers are a 2, including good ones.** A well-written abstract in a
  fashionable area is still a 2. A paper reaches 3 only when its *finding* would
  interest someone outside its own subfield, or it releases code or weights worth
  fetching, or it gets a result with conspicuously less compute, data, or
  machinery than expected. Another architecture variant, another training or
  distillation recipe, another agent framework, another multimodal pipeline, and
  another point or two on a standard benchmark are 2 however competently done.
- **A benchmark is not a result.** New benchmarks, evaluation suites,
  leaderboards, and "a systematic evaluation of N systems" are 2 unless the
  finding, not the harness, is what is interesting.
- **Popularity is not a Score.** Upvotes, stars, downloads, and reaction counts
  say what a crowd did, not whether this reader wants it. They may break a tie
  and nothing more.
- **If you are hesitating between two Scores, take the lower one.** The Brief is
  short on purpose and a generous 3 costs a slot that a real 4 wanted.
