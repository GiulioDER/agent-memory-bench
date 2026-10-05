"""Generation settings for the memory-discipline Kaggle tasks (preregistration 098, Deviation 1).

Standard library only, and copied verbatim into both generated task files, like `scoring.py`.

Kaggle's model proxy reserves the worst-case cost of every call before making it, computed from
the maximum output length; at the provider default an Opus call reserved $3.20 and the account's
whole daily quota is $10, so with four calls in flight the Opus models could never start. Capping
the reply length bounds the reservation. 8,192 tokens is about fifteen times the mean reply of the
one model run before the cap (gemini-3.7-flash, 532 output tokens per item including thinking), so
the cap bounds cost without shaping what a model says; a reply cut off by it has no directive line
and is scored `format_failure`, which the analysis reports.
"""

MAX_REPLY_TOKENS = 8192


def reply_length_cap(llm):
    """The extra API parameter that caps reply length, named the way this client expects it.

    Kaggle serves Gemini models either through Google's own client, whose config field is
    `max_output_tokens`, or through the OpenAI-compatible endpoint, which takes
    `max_completion_tokens` (the name newer GPT models require; `max_tokens` is refused by them).
    """
    if type(llm).__name__ == "GoogleGenAI":
        return {"max_output_tokens": MAX_REPLY_TOKENS}
    return {"max_completion_tokens": MAX_REPLY_TOKENS}
