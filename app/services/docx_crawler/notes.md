### Plan:

We want to crawl the document.

firstly looking for either term `serious` or `sae` in the title to know we're looking at the right table

after that we want to grab the data per `term` (symptom/outcome)
and then state the percentage change for the outcome based on the compound

if both compounds produce a chance of the `term`, but not equal
then we want the output to be

_More participants who received C1 (xx%) experienced T1 compared to C2 (xx%)._

if the compounds produce equal chance of the outcome:

_An equal proportion of participants experienced T1 (xx%)._

if a compound has no cases of that term (0%)

_Only xx% of participants who received C2 experienced T1._

and if neither compound have any case of the term

*_No participants experienced T1_*

for example, using `client1_ae.docx` we want it looking like:

```json
{
  "compounds": [
    "Placebo",
    "Compound X"
  ],
  "table_title": "Summary of Serious Adverse Events",
  "table_number": "2.1.1",
  "summary_sentences": {
    "totals_sentence": "A total of 3 participants received Placebo, and a total of 19 participants received Compound X.",
    "per-term_sentences": [
      "More participants who received Placebo (33%) experienced Seizure compared to Compound X (16%).",
      "Only 11% of participants who received Compound X experienced Nausea",
      "More participants who received Placebo (67%) experienced Headache compared to Compound X (21%).",
      "Only 53% of participants who received Compound X experienced Bleeding"
    ]
  }
}

```