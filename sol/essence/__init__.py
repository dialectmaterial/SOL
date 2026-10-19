"""Small, reproducible experiments over SOL's verified canonical corpus.

ESSENCE consumes CORE data; importing it never starts a reader or native shell.
"""

from importlib import import_module

__all__ = ["MAX_RESULT_BYTES", "TermExperimentError", "analyze_term", "check_term_result",
           "encode_term_result", "decode_term_result", "prose_text", "export_prose",
           "CoreProvider", "FileProvider", "WordStudyError", "analyze_words", "check_word_result",
           "encode_word_result", "decode_word_result", "compare_words", "export_word_comparison",
           "SentenceStudyError", "analyze_sentences", "check_sentence_result", "encode_sentence_result",
           "decode_sentence_result"]


def __getattr__(name):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = "sol.essence.prose" if name in {"prose_text", "export_prose"} else "sol.essence.terms"
    if name in {"CoreProvider", "FileProvider", "WordStudyError"}:
        module = "sol.essence.word_inputs"
    elif name in {"analyze_words", "check_word_result", "encode_word_result", "decode_word_result"}:
        module = "sol.essence.words"
    elif name in {"compare_words", "export_word_comparison"}:
        module = "sol.essence.comparison"
    elif name in {"SentenceStudyError", "analyze_sentences", "check_sentence_result", "encode_sentence_result",
                  "decode_sentence_result"}:
        module = "sol.essence.sentences"
    value = getattr(import_module(module), name)
    globals()[name] = value
    return value
