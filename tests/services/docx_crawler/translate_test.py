import pytest

from app.services.docx_crawler.translate.translate import (
    select_compounds,
    base_substitutions,
    per_term_substitutions,
    select_per_term_template,
    generate_totals_sentence,
    generate_per_term_sentence,
    translate_parsed_docx_content,
    OUTPUT_SENTENCES,
)


def cell(name, count, int_percent, percent):
    return {
        "compound": name,
        "count": count,
        "percent": int_percent,
        "percent_str": percent,
    }


# ---------------------------------------------------------------------------
# select_compounds
# ---------------------------------------------------------------------------


def test_select_compounds_returns_rows_in_request_order():
    rows = [cell("Placebo", 1, 33, "33%"), cell("Compound X", 3, 16, "16%")]
    # request reversed order -> result follows the request, not the data
    result = select_compounds(rows, ["Compound X", "Placebo"])
    assert [r["compound"] for r in result] == ["Compound X", "Placebo"]


def test_select_compounds_with_odd_casing_matches_table_compound():
    rows = [cell("Placebo", 1, 33, "33%"), cell("Compound X", 3, 16, "16%")]
    result = select_compounds(rows, ["PlacEBO", "CoMpOunD x"])
    assert [r["compound"] for r in result] == ["Placebo", "Compound X"]


def test_select_compounds_raises_on_missing_compound():
    rows = [cell("Placebo", 1, 33, "33%")]
    with pytest.raises(ValueError, match="not found"):
        select_compounds(rows, ["Placebo", "Compound Z"])


# ---------------------------------------------------------------------------
# base_substitutions / per_term_substitutions
# ---------------------------------------------------------------------------


def test_base_substitutions_maps_name_and_count_by_position():
    key_data = [cell("Placebo", 3, 0, None), cell("Compound X", 19, 0, None)]
    assert base_substitutions(key_data) == {
        "C1": "Placebo",
        "C1N": 3,
        "C2": "Compound X",
        "C2N": 19,
    }


def test_per_term_substitutions_includes_term_and_present_percents():
    key_data = [cell("Compound X", 3, 16, "16%"), cell("Placebo", 1, 33, "33%")]
    subs = per_term_substitutions(key_data, "Seizure")
    assert subs["T"] == "Seizure"
    assert subs["C1%"] == "16%"
    assert subs["C2%"] == "33%"


def test_per_term_substitutions_omits_none_percent():
    # the zero compound has percent None -> no C2% key emitted
    key_data = [cell("Compound X", 2, 11, "11%"), cell("Placebo", 0, 0, None)]
    subs = per_term_substitutions(key_data, "Nausea")
    assert "C1%" in subs
    assert "C2%" not in subs


# ---------------------------------------------------------------------------
# select_per_term_template  (the branch logic)
# ---------------------------------------------------------------------------


def test_branch_both_positive_unequal_picks_both():
    a, b = cell("Placebo", 2, 33, "33%"), cell("Compound X", 1, 16, "16%")
    template, ordered = select_per_term_template(a, b, OUTPUT_SENTENCES["per_term"])
    assert template == OUTPUT_SENTENCES["per_term"]["both"]
    assert [c["compound"] for c in ordered] == [
        "Placebo",
        "Compound X",
    ]  # higher first, already in order


def test_branch_both_positive_reorders_higher_first():
    # comp_a is the LOWER percentage -> must be reordered so higher lands in C1
    a, b = cell("Compound X", 1, 16, "16%"), cell("Placebo", 2, 33, "33%")
    template, ordered = select_per_term_template(a, b, OUTPUT_SENTENCES["per_term"])
    assert template == OUTPUT_SENTENCES["per_term"]["both"]
    assert [c["compound"] for c in ordered] == [
        "Placebo",
        "Compound X",
    ]  # higher (33) first


def test_branch_equal_positive_picks_equal():
    a, b = cell("Placebo", 2, 20, "20%"), cell("Compound X", 4, 20, "20%")
    template, _ = select_per_term_template(a, b, OUTPUT_SENTENCES["per_term"])
    assert template == OUTPUT_SENTENCES["per_term"]["equal"]


def test_branch_both_zero_picks_none():
    a, b = cell("Placebo", 0, 0, None), cell("Compound X", 0, 0, None)
    template, _ = select_per_term_template(a, b, OUTPUT_SENTENCES["per_term"])
    assert template == OUTPUT_SENTENCES["per_term"]["none"]


def test_branch_one_zero_reorders_nonzero_first():
    # comp_a is zero -> non-zero comp_b must come first so its name/percent fill C1
    a, b = cell("Placebo", 0, 0, None), cell("Compound X", 10, 53, "53%")
    template, ordered = select_per_term_template(a, b, OUTPUT_SENTENCES["per_term"])
    assert template == OUTPUT_SENTENCES["per_term"]["one"]
    assert [c["compound"] for c in ordered] == ["Compound X", "Placebo"]


def test_branch_one_zero_nonzero_already_first_keeps_order():
    a, b = cell("Compound X", 10, 53, "53%"), cell("Placebo", 0, 0, None)
    template, ordered = select_per_term_template(a, b, OUTPUT_SENTENCES["per_term"])
    assert template == OUTPUT_SENTENCES["per_term"]["one"]
    assert [c["compound"] for c in ordered] == ["Compound X", "Placebo"]


# ---------------------------------------------------------------------------
# rendered sentences (end-to-end truthfulness)
# ---------------------------------------------------------------------------


def test_totals_sentence_renders():
    totals = [
        {"compound": "Placebo", "count": 3},
        {"compound": "Compound X", "count": 19},
    ]
    assert generate_totals_sentence(totals, ["Placebo", "Compound X"]) == (
        "A total of 3 participants received Placebo, "
        "and a total of 19 participants received Compound X."
    )


def test_per_term_one_zero_names_the_nonzero_compound():
    term = {
        "term": "Bleeding",
        "compounds": [
            cell("Placebo", 0, 0, None),
            cell("Compound X", 10, 53, "53%"),
        ],
    }
    sentence = generate_per_term_sentence(term, ["Placebo", "Compound X"])
    assert (
        sentence
        == "Only 53% of participants who received Compound X experienced Bleeding."
    )


def test_per_term_both_higher_first_even_when_requested_lower_first():
    term = {
        "term": "Seizure",
        "compounds": [
            cell("Placebo", 1, 33, "33%"),
            cell("Compound X", 3, 16, "16%"),
        ],
    }
    # request Compound X (lower) first; sentence must still name Placebo (higher) first
    sentence = generate_per_term_sentence(term, ["Compound X", "Placebo"])
    assert sentence == (
        "More participants who received Placebo (33%) experienced Seizure "
        "compared to Compound X (16%)."
    )


# ---------------------------------------------------------------------------
# translate_parsed_docx_content (top level)
# ---------------------------------------------------------------------------


def test_translate_requires_exactly_two_compounds():
    with pytest.raises(ValueError, match="exactly two"):
        translate_parsed_docx_content({"tables": []}, ["Placebo"])


def test_translate_wraps_tables_and_builds_sentences():
    parsed = {
        "tables": [
            {
                "table_number": "2.1.1",
                "table_title": "Summary of Serious Adverse Events",
                "term_data": [
                    {
                        "term": "Seizure",
                        "compounds": [
                            cell("Placebo", 1, 33, "33%"),
                            cell("Compound X", 3, 16, "16%"),
                        ],
                    },
                ],
                "total_with_SAE": [
                    {"compound": "Placebo", "count": 3},
                    {"compound": "Compound X", "count": 19},
                ],
            }
        ]
    }
    out = translate_parsed_docx_content(parsed, ["Placebo", "Compound X"])
    assert list(out.keys()) == ["tables"]
    table = out["tables"][0]
    assert table["table_number"] == "2.1.1"
    assert table["selected_compounds"] == ["Placebo", "Compound X"]
    assert table["summary_sentences"]["totals_sentence"].startswith("A total of 3")
    assert table["summary_sentences"]["per_term_sentences"][0]["term"] == "Seizure"
