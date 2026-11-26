
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from sumy.utils import get_stop_words


def generate_summary(text: str):

    if not text.strip():
        return "No text available for summarization"

    parser = PlaintextParser.from_string(
        text,
        Tokenizer("english")
    )

    summarizer = LsaSummarizer()
    summarizer.stop_words = get_stop_words("english")

    sentences = list(summarizer(parser.document, 3))

    if not sentences:
        return "Not enough text to generate a summary"

    summary = " ".join(str(sentence) for sentence in sentences)

    return summary
