# Exam Prep — Mistral targeted solution recovery findings

Branch: `experiment/mistral-ocr-layout-probe`

This note records evidence from the successful seven-column targeted OCR run after the
full-document Run A. It is diagnostic only and does not change the production pipeline.

## Provider result

The targeted bundle completed successfully with:

- model requested/resolved: `mistral-ocr-4-0`;
- provider requests: 1;
- retries: 0;
- crop pages: 7;
- crop PDF bytes: 2,096,423;
- latency: 25,344 ms;
- usage pages processed: 7;
- provider estimated cost: `0.0070000000` unit / `1303.75` IRT as returned by AvalAI.

The seven crops were physical solution columns:

`33:left, 34:left, 35:right, 36:left, 37:right, 40:left, 43:right`.

## The original probe manifest under-counted headings

OCR4 did not preserve a one-heading-per-block structure under targeted cropping:

- one crop was represented as a single HTML table block;
- several crops were represented as one large text block;
- the page-40 crop was represented as one large equation block.

The first diagnostic scanner only called the heading parser at the start of each provider
block, so its manifest reported only 11 headings. Scanning line-like content inside every
block, including HTML table cells, finds 28 heading occurrences in the same raw response.

This is a parser defect in the diagnostic manifest, not a provider omission.

## Every required repair target was recovered

The base full-document contract had eight missing solution headings:

`4, 5, 6, 10, 15, 26, 30, 74`.

It also had one invalid answer label for question 57.

The targeted raw response recovers all nine targets uniquely:

- Q4 -> option 2
- Q5 -> option 3
- Q6 -> option 2
- Q10 -> option 2
- Q15 -> option 4
- Q26 -> option 2
- Q30 -> option 2
- Q57 -> option 3
- Q74 -> option 3

The printed crop images were also visually checked for these headings and agree with the
nine values above.

Therefore a target-only repair projects the structural solution contract from 147 unique
base headings to all 155 questions, while eliminating the one invalid base answer label.

## Targeted OCR must not overwrite healthy base headings

The crop pass is useful for missing boundary metadata, but it is not more trustworthy in
general. On the page-34 crop the printed source and the base run show:

- Q12 -> option 3;
- Q13 -> option 3;
- Q14 -> option 4.

The targeted crop OCR instead produced Q12 -> 4, Q13 -> 5, and Q14 -> 6.

The incorrect answer-label tokens were not low-confidence warnings. Provider confidence
for the erroneous Q12/Q13/Q14 option tokens was approximately 0.9905, 0.9922, and 0.9944.
By contrast, the correctly recovered Q10 option-2 token had confidence only about 0.5801.
This is direct evidence that word confidence cannot be a correctness gate for answer labels.

The safe merge rule is therefore strict:

1. derive missing/invalid question numbers from the base structural audit;
2. accept targeted OCR only for those predeclared target question numbers;
3. require one unique valid option label in the targeted evidence;
4. fail closed on conflicting targeted labels;
5. never let a non-target crop heading overwrite an already accepted base heading.

## Do not replace full solution text with crop OCR

The targeted pass also contains severe transcription artifacts inside otherwise useful
crops. Examples include repeated words in Q74 and placeholder/corrupted mathematical
symbols around Q56/Q57. Therefore the targeted pass is not a replacement solution-body
transcriber.

Its role is deliberately narrow:

`question number + answer label + boundary anchor`

The full OCR/source evidence remains responsible for the solution body, and later text/
formula fidelity checks remain independent.

## Architecture consequence

The structural path for this representative document can now be treated as:

1. two bounded full-document OCR4 chunks;
2. local page/range/question geometry and RTL ordering;
3. local solution-heading state machine;
4. target-only crop re-OCR for explicit missing/invalid heading metadata;
5. safe target-only merge;
6. visual/source coverage reconciliation;
7. separate transcription/formula risk and verifier stage.

The next benchmark should focus on text and formula fidelity, not on document skeleton
recovery. The structural evidence is now strong enough to stop spending full-document OCR
calls merely to rediscover the same boundaries.
