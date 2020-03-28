from chatbot.nlploader import nlp


def get_pairs(text):
    """
    Make a list of bigram (part of speech, lemma) pairs for the given text.

    If the text is too short to create pairs, lemmatize each token instead.

    :param text: Input text.
    :returns: List of bigram pairs or lemmatized tokens.
    """

    pairs = list()
    document = nlp(text)

    if len(document) <= 2:
        # Text is short, just lemmatize it
        pairs = [token.lemma_.lower() for token in document]
    else:
        # Exclude stop words and numbers
        tokens = [
            token for token in document
            if token.is_alpha and not token.is_stop
        ]
        if len(tokens) < 2:
            # If we ended up with <2 tokens, re-add the stop words
            tokens = [token for token in document if token.is_alpha]

        # Build list of pairs
        for index in range(1, len(tokens)):
            pairs.append('{}:{}'.format(
                tokens[index - 1].pos_,
                tokens[index].lemma_.lower()
            ))

        if len(pairs) == 0:
            # No pairs made, just lemmatize the original input
            pairs = [token.lemma_.lower() for token in document]

    return pairs
