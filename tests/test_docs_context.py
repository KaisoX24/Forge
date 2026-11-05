import random

import pytest

from lessons.docs_context import (
    CHARS_PER_TOKEN, build_doc_refs, chunk_title, clean_heading, docs_budget, estimate_tokens, ground_step,
    pack_docs, prepare_step_docs, render_chunk, render_docs, source_url,
)
from models.data_models import ObjectivePlan, RetrievedDocument


def doc(cid, content="some text about things", *, url="https://d/p1/", anchor="#sec", h1="Page", h2=None, dist=0.3):
    md = {"chunk_id": cid, "url": url, "anchor": anchor, "Header 1": h1}
    if h2:
        md["Header 2"] = h2
    return RetrievedDocument(content=content, metadata=md, distance=dist)


def cost(d):
    return estimate_tokens(render_chunk(d, 99))


def ids(packed):
    return [d.metadata["chunk_id"] for d in packed.chunks]


def test_estimate_tokens_rounds_up_and_handles_empty():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 2                    # 4 / 3.5 -> 2
    assert estimate_tokens("a" * 7) == 2 and estimate_tokens("a" * 8) == 3


def test_estimate_tokens_uses_the_given_ratio():
    assert estimate_tokens("a" * 100, chars_per_token=2) == 50


def test_default_budget_matches_the_numbers_we_agreed():
    assert docs_budget() == 8192 - 2048 - 1000 - 819 == 4325


def test_budget_follows_the_window_and_the_reserved_answer_room():
    assert docs_budget(num_ctx=16384, num_predict=2048, fixed_prompt_tokens=1000, margin=0.1) > docs_budget()


def test_budget_refuses_a_configuration_with_no_room():
    with pytest.raises(ValueError, match="No room"):
        docs_budget(num_ctx=4096, num_predict=2048, fixed_prompt_tokens=1500)


def test_heading_link_junk_is_removed():
    raw = 'Path Parameters[¶](https://fastapi.tiangolo.com/tutorial/path-params/#path-parameters "Permanent link")'
    assert clean_heading(raw) == "Path Parameters"


def test_real_link_text_is_kept_and_whitespace_collapsed():
    assert clean_heading("Use  [Pydantic](https://x.dev)   models") == "Use Pydantic models"


def test_plain_and_empty_headings():
    assert clean_heading("Query Parameters") == "Query Parameters" and clean_heading("[¶](https://x)") == ""


def test_title_is_the_deepest_heading():
    assert chunk_title(doc("a", h1="Page", h2="Path parameters with types")) == "Path parameters with types"


def test_title_falls_back_to_a_shallower_heading_then_none():
    assert chunk_title(doc("a", h1="Page")) == "Page"
    assert chunk_title(RetrievedDocument(content="x", metadata={}, distance=0.1)) is None


def test_source_url_is_page_plus_anchor():
    assert source_url(doc("a", url="https://d/p/", anchor="#x")) == "https://d/p/#x"


def test_source_url_without_anchor_or_url():
    assert source_url(doc("a", url="https://d/p/", anchor="")) == "https://d/p/"
    d = RetrievedDocument(content="x", metadata={"source_file": "p.md"}, distance=0.1)
    assert source_url(d) == "p.md"

def test_everything_fits_so_nothing_is_dropped():
    a, b = doc("a", "x" * 400), doc("b", "y" * 400, url="https://d/p2/")
    packed = pack_docs([[a], [b]], budget_tokens=10_000)
    assert sorted(ids(packed)) == ["a", "b"] and packed.dropped == 0 and packed.est_tokens == cost(a) + cost(b)


def test_never_exceeds_the_budget_whatever_the_chunk_sizes():
    rng = random.Random(7)
    for _ in range(200):
        results = [[doc(f"r{r}-{i}", "z" * rng.randint(100, 2500), url=f"https://d/{rng.randint(1,4)}/")
                    for i in range(5)] for r in range(2)]
        budget = rng.randint(300, 6000)
        packed = pack_docs(results, budget)
        assert packed.est_tokens <= budget
        assert packed.est_tokens == sum(cost(d) for d in packed.chunks)


def test_worst_case_ten_large_chunks_fits_the_real_budget_and_serves_both_requirements():
    r1 = [doc(f"a{i}", "x" * 2466, url=f"https://d/a{i}/") for i in range(5)]
    r2 = [doc(f"b{i}", "y" * 2466, url=f"https://d/b{i}/") for i in range(5)]
    packed = pack_docs([r1, r2], docs_budget())
    assert packed.est_tokens <= docs_budget() and packed.dropped > 0
    assert any(i.startswith("a") for i in ids(packed)) and any(i.startswith("b") for i in ids(packed))


def test_requirements_take_turns_so_neither_starves():
    r1 = [doc(f"a{i}", "x" * 300, url=f"https://d/a{i}/") for i in range(3)]
    r2 = [doc(f"b{i}", "y" * 300, url=f"https://d/b{i}/") for i in range(3)]
    packed = pack_docs([r1, r2], budget_tokens=cost(r1[0]) * 4)
    assert ids(packed) == ["a0", "b0", "a1", "b1"] and packed.dropped == 2


def test_a_chunk_retrieved_for_both_requirements_is_counted_once():
    shared = doc("shared", "s" * 200, url="https://d/s/")
    packed = pack_docs([[shared, doc("a1", url="https://d/a/")], [shared, doc("b1", url="https://d/b/")]], 10_000)
    assert sorted(ids(packed)) == ["a1", "b1", "shared"]


def test_a_chunk_that_does_not_fit_is_skipped_but_a_smaller_later_one_still_goes_in():
    big, small = doc("big", "x" * 2400, url="https://d/1/"), doc("small", "y" * 100, url="https://d/2/")
    packed = pack_docs([[big, small]], budget_tokens=cost(small) + 5)
    assert ids(packed) == ["small"] and packed.dropped == 1


def test_nothing_retrieved_gives_empty_docs():
    for results in ([], [[], []]):
        packed = pack_docs(results, 1000)
        assert packed.chunks == [] and packed.est_tokens == 0 and packed.dropped == 0


def test_chunks_without_an_id_are_deduplicated_by_content():
    a = RetrievedDocument(content="same text", metadata={"url": "https://d/"}, distance=0.1)
    b = RetrievedDocument(content="same text", metadata={"url": "https://d/"}, distance=0.2)
    assert len(pack_docs([[a], [b]], 1000).chunks) == 1


def test_chunks_are_grouped_by_page_keeping_relevance_order_within_a_page():
    a1, b1, a2 = doc("a1", url="https://d/A/"), doc("b1", url="https://d/B/"), doc("a2", url="https://d/A/")
    assert ids(pack_docs([[a1, b1, a2]], 10_000)) == ["a1", "a2", "b1"]


def test_a_stricter_chars_per_token_ratio_packs_less():
    results = [[doc(f"c{i}", "x" * 800, url=f"https://d/{i}/") for i in range(8)]]
    loose = pack_docs(results, 1500, chars_per_token=4.5)
    strict = pack_docs(results, 1500, chars_per_token=2.5)
    assert len(strict.chunks) < len(loose.chunks)


def test_rendered_text_is_never_bigger_than_the_budget_claims():
    chunks = [doc(f"c{i}", "x" * 500, url=f"https://d/{i}/", h1=f"Title {i}") for i in range(8)]
    packed = pack_docs([chunks], docs_budget())
    assert estimate_tokens(render_docs(packed.chunks)) <= packed.est_tokens


def test_rendering_numbers_the_sources_and_shows_title_url_and_text():
    text = render_docs([doc("a", "alpha body", h1="First", url="https://d/1/", anchor="#one"),
                        doc("b", "beta body", h1="Second", url="https://d/2/", anchor="#two")])
    assert "[Source 1] First (https://d/1/#one)\nalpha body" in text
    assert "[Source 2] Second (https://d/2/#two)\nbeta body" in text and not text.endswith("\n")


REQ_A = "Declare a path parameter with a type annotation"
REQ_B = "Explain how numeric validation constrains values"


def test_fully_covered_step_is_grounded():
    chunks = [doc("a", "You declare a path parameter with a type annotation. Explain numeric validation: it constrains values.")]
    g = ground_step([REQ_A, REQ_B], chunks)
    assert g.label == "grounded" and g.coverage >= 0.6 and g.missing == []


def test_step_is_only_as_grounded_as_its_weakest_requirement():
    chunks = [doc("a", "You declare a path parameter with a type annotation.")]
    g = ground_step([REQ_A, REQ_B], chunks)
    assert g.coverage == min(c for _, c in g.per_requirement) and g.coverage < 0.6
    assert g.label in ("weak", "unproved")


def test_a_requirement_counts_as_covered_by_chunks_retrieved_for_the_other_requirement():
    chunks = [doc("b", "Numeric validation constrains values. You declare a path parameter with a type annotation.")]
    assert ground_step([REQ_A], chunks).label == "grounded"


def test_no_docs_means_unproved_with_all_words_missing():
    g = ground_step([REQ_A], [])
    assert g.label == "unproved" and g.coverage == 0.0 and "parameter" in g.missing


def test_missing_words_are_merged_sorted_and_unique():
    g = ground_step([REQ_A, REQ_B], [doc("a", "nothing relevant at all")])
    assert g.missing == sorted(set(g.missing)) and len(g.missing) > 3


def test_the_label_is_always_consistent_with_the_coverage():
    from exercises.grounding import grounding_label
    for text in ("", "path parameter", "declare a path parameter with a type", REQ_A):
        g = ground_step([REQ_A], [doc("a", text)] if text else [])
        assert g.label == grounding_label(g.coverage)


def test_custom_thresholds_are_honoured():
    chunks = [doc("a", "declare path parameter")]
    assert ground_step([REQ_A], chunks, min_for_grounded=0.99).label != "grounded"
    assert ground_step([REQ_A], chunks, min_for_grounded=0.01).label == "grounded"

def test_one_ref_per_distinct_section_in_order():
    chunks = [doc("a", url="https://d/p1/", anchor="#x", h1="One"), doc("b", url="https://d/p1/", anchor="#x", h1="One"),
              doc("c", url="https://d/p2/", anchor="#y", h1="Two")]
    refs = build_doc_refs(chunks, ground_step([REQ_A], chunks))
    assert [(r.label, r.url) for r in refs] == [("One", "https://d/p1/#x"), ("Two", "https://d/p2/#y")]


def test_every_ref_carries_the_steps_label_and_coverage():
    chunks = [doc("a", "declare a path parameter with a type annotation", url="https://d/1/"), doc("b", url="https://d/2/")]
    g = ground_step([REQ_A], chunks)
    refs = build_doc_refs(chunks, g)
    assert {r.grounding for r in refs} == {g.label} and {r.coverage for r in refs} == {g.coverage}


def test_a_ref_without_any_heading_is_labelled_by_its_url():
    d = RetrievedDocument(content="x", metadata={"url": "https://d/p/", "anchor": ""}, distance=0.1)
    assert build_doc_refs([d], ground_step([REQ_A], [d]))[0].label == "https://d/p/"


def test_no_chunks_means_no_refs():
    assert build_doc_refs([], ground_step([REQ_A], [])) == []

def step(*reqs):
    return ObjectivePlan(objective="Learn how path parameters work", requirements=list(reqs))


def test_each_requirement_is_used_as_a_query():
    seen = []
    prepare_step_docs(step(REQ_A, REQ_B), lambda q: seen.append(q) or [], budget_tokens=1000)
    assert seen == [REQ_A, REQ_B]


def test_end_to_end_text_refs_and_grounding_agree():
    retrieve = lambda q: [doc("c1", "You declare a path parameter with a type annotation. Explain numeric validation: it constrains values.",
                              url="https://d/p1/", anchor="#types", h1="Types")]
    result = prepare_step_docs(step(REQ_A, REQ_B), retrieve, budget_tokens=docs_budget())
    assert "[Source 1] Types (https://d/p1/#types)" in result.text
    assert [r.url for r in result.refs] == ["https://d/p1/#types"] and result.grounding.label == "grounded"


def test_grounding_reflects_only_what_the_model_actually_sees():
    "The words that make REQ_A covered live only in a chunk that did not fit; so the label must say so."
    helpful = doc("helpful", "You declare a path parameter with a type annotation. " + "pad " * 600, url="https://d/h/")
    filler = doc("filler", "completely unrelated content here", url="https://d/f/")
    retrieve = lambda q: [filler, helpful]                         # the helpful chunk ranks second...
    result = prepare_step_docs(step(REQ_A), retrieve, budget_tokens=cost(filler) + 10)
    assert ids(result.packed) == ["filler"] and result.packed.dropped == 1
    assert result.grounding.label != "grounded" and "parameter" in result.grounding.missing


def test_the_packed_docs_never_exceed_the_budget_for_a_realistic_worst_case():
    big = lambda q: [doc(f"{q[:3]}{i}", "word " * 490, url=f"https://d/{q[:3]}{i}/") for i in range(5)]
    result = prepare_step_docs(step(REQ_A, REQ_B), big, budget_tokens=docs_budget())
    assert result.packed.est_tokens <= docs_budget()
    assert estimate_tokens(result.text) <= result.packed.est_tokens


def test_a_step_with_a_single_requirement_works():
    result = prepare_step_docs(step(REQ_A), lambda q: [doc("c1", "declare a path parameter with a type annotation")],
                               budget_tokens=1000)
    assert len(result.packed.chunks) == 1 and result.grounding.label == "grounded"


def test_nothing_retrieved_gives_empty_text_no_refs_and_unproved():
    result = prepare_step_docs(step(REQ_A), lambda q: [], budget_tokens=1000)
    assert result.text == "" and result.refs == [] and result.grounding.label == "unproved"