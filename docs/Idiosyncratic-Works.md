# Idiosyncratic Works

A data-first hunt through the 779-work Fabric corpus for works as statistically strange as the three favorites in [Author-Style-Summaries](Author-Style-Summaries.md). Ranked by an "excess" index: the sum of every series' |z| beyond 2.0, rewarding both how many wild scores a work has and how wild they are. Excluded: self-works, plays, poetry, juvenile titles, and anything under 20k words (plays otherwise sweep the board; short texts have noisy z-scores).

---

## Calibration: the three favorites in the 779-work corpus

| Work               | excess | rank   |
| ------------------ | ------ | ------ |
| The Night Land     | 17.3   | **#1** |
| Gormenghast        | 0.8    | #124   |
| The Worm Ouroboros | 0.4    | #151   |
| Titus Groan        | 0.0    | #198   |

The Night Land is still the single strangest prose work in a corpus 5.5x larger than the original 141. Eddison and Peake collapsed, and that is the real lesson: distinctiveness is corpus-relative. The full PG fantasy shelf is stuffed with Malory, Morris, Bain, and saga translations, so Eddison's archaism is now just the neighborhood register. Peake's variance-over-mean rhythm washes out against pulpier company. Hodgson survives because his weirdness is invented grammar ("did be"), which no genre supplies.

## The discoveries

**The Consolidator - Daniel Defoe, 1705** (#2 overall, excess 14.7). A proto-SF lunar satire. Sentences average **55 words (z = +5.6)** with equally extreme variance (+5.6) and the deepest clause-nesting outside Bramah (+3.0). The function words mark collective-abstract satire: *their* +4.5, *this* +3.9, *they* +2.7; a book about ideas and factions, almost never about a person in a room.

**F. W. Bain's fake-Sanskrit romances** - the author-level find. Four works in the top 14 (*The Substance of a Dream* #5, *A Syrup of the Bees*, *Bubbles of the Foam*, *A Mine of Faults*). Published 1898-1919 as claimed translations of a lost Sanskrit manuscript. The fingerprint: **colon rates z = +3.2 to +4.0** (aphorism-chaining), *as* and *for* at +3 to +5 (endless similes and because-clauses), archaic rate +3, *her* elevated; heroine-centric mythic prose. Nobody else in 779 works punctuates like this.

**Ernest Bramah - The Wallet of Kai Lung / The Mirror of Kong Ho** (#6, #13). The corpus's **deepest parse trees (8.46 levels, z = +4.0)** and 44-word sentences built from mock-Mandarin ceremonial circumlocution, with the *highest* mean word length among the top group, where the three favorites all run short-worded. The structural opposite of Hodgson: ornament in the syntax and the lexicon.

**The Fixed Period - Anthony Trollope, 1882** (#4). His one dystopia (mandatory euthanasia at 67, narrated by its true-believer architect). Signature is modal mania: *be* +5.1, *been* +4.5, *would* +3.7; argument-prose, a narrator forever justifying hypotheticals. Weird along an axis none of the three favorites touch.

**William Morris, late prose romances** (*The Water of the Wondrous Isles* #10, *Child Christopher* #9, *The Wood Beyond the World* #20). Now the corpus archaism champions (z ~ +4.8) with *but/and* parataxis. Also The Night Land's nearest neighbors (cosine ~0.55), the closest thing to a Night Land clone that exists.

Honorable mentions: *Cliges* (Chretien de Troyes translation; *for/if/not* argument-logic of courtly debate), *Drome* by John Martin Leahy (pulp lost-world; *we* +4.2, pure expedition-narration), *Flaxius* by Charles Godfrey Leland (*or* +5.5, compulsive enumeration).

## Clone check

No Gormenghast clone exists; Peake's nearest neighbors are Tarzan novels at a weak 0.6 cosine, which means "nothing nearby." But **Ouroboros has a genuine kin-cluster**: *The World's Desire* (Haggard + Andrew Lang's Homeric pastiche, 0.61), Meredith's *The Shaving of Shagpat* (0.56), the Morris/Magnusson *Volsunga Saga* (0.56), and Fouque's *Sintram* (0.55). For more Eddison-shaped prose, that is the shortlist.

## Data-quality notes

- *Sigurd the Volsung* ranked #3 but is a verse epic that slipped past the `is_poetry` flag.
- The Purcell Papers Vol 3 posted the corpus's largest single deviation (*an*, z = +9.57); text check confirmed 505 of its 643 "an" tokens are Irish-dialect `an'` ("and"), a tokenizer artifact, not grammar.
