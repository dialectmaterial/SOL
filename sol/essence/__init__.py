"""Small, reproducible experiments over SOL's verified canonical corpus.

ESSENCE consumes CORE data; importing it never starts a reader or native shell.
"""

from importlib import import_module

__all__ = ["prose_text", "export_prose",
           "CoreProvider", "FileProvider", "WordStudyError", "analyze_words", "check_word_result",
           "encode_word_result", "decode_word_result", "compare_words", "export_word_comparison",
           "SentenceStudyError", "analyze_sentences", "check_sentence_result", "encode_sentence_result",
           "decode_sentence_result", "analyze_tfidf", "check_tfidf_result",
           "encode_tfidf_result", "decode_tfidf_result"]


def __getattr__(name):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = "sol.essence.essence_as_reflection_within_itself.prose"
    if name in {"CoreProvider", "FileProvider", "WordStudyError"}:
        module = "sol.essence.essence_as_reflection_within_itself.word_inputs"
    elif name in {"analyze_words", "check_word_result", "encode_word_result", "decode_word_result"}:
        module = "sol.essence.essence_as_reflection_within_itself.words"
    elif name in {"compare_words", "export_word_comparison"}:
        module = "sol.essence.essence_as_reflection_within_itself.comparison"
    elif name in {"SentenceStudyError", "analyze_sentences", "check_sentence_result", "encode_sentence_result",
                  "decode_sentence_result"}:
        module = "sol.essence.essence_as_reflection_within_itself.sentences"
    elif name in {"analyze_tfidf", "check_tfidf_result", "encode_tfidf_result", "decode_tfidf_result"}:
        module = "sol.essence.essence_as_reflection_within_itself.tfidf"
    value = getattr(import_module(module), name)
    globals()[name] = value
    return value
