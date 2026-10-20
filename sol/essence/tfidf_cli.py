"""Headless TF-IDF adapter; files need neither CORE nor a UI."""
from sol.essence.tfidf import analyze_tfidf, check_tfidf_result, encode_tfidf_result
from sol.essence.word_cli import _provider
from sol.essence.word_inputs import WordStudyError


def render_tfidf(result):
    from sol.essence.cli import _safe

    lines = ["TF-IDF (tfidf-v1): raw TF; ln((1+N)/(1+df))+1; document L2 normalization.",
             "Overall: mean document weights, including empty documents.",
             "Lexical weights do not establish conceptual similarity."]
    for label, terms in [("Overall", result["overall"])] + [
            (f"Document {row['input_index']}", row["top_terms"]) for row in result["documents"]]:
        lines.append(label + ":")
        lines.extend(f"  {_safe(row['word'])}  {row['score']:.12f}" for row in terms)
        if not terms:
            lines.append("  No eligible terms.")
    return "\n".join(lines)


def run(options, result=None):
    from sol.essence.cli import _json

    if options.action == "check" and (options.compare or any(
            getattr(options, "reference_" + name) is not None
            for name in ("provider", "file", "corpus", "within", "passage", "span"))):
        raise WordStudyError("TF-IDF takes one provider, without a reference", code="invalid_input")
    saved = result["word_study"]["target"] if result else None
    target = _provider(options, saved=saved)
    result = analyze_tfidf(target, top_n=options.top_n) if result is None else check_tfidf_result(target, result)
    if options.action == "check":
        source = result["word_study"]["target"]
        receipt = {"status": "current", "protocol": result["protocol"], "version": result["version"],
                   "provider": source["provider"], "binding": source["binding"], "summary": source["summary"]}
        print(_json(receipt) if options.json else "Verified against the current source binding.\n\n" + render_tfidf(result))
    else:
        print(encode_tfidf_result(result) if options.json else render_tfidf(result))
    return 0
