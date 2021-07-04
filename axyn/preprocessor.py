def preprocess(client, message):
    """Return a cleaned-up version of the contents of the given message."""
    content = message.clean_content

    # Strip off leading @Axyn if it exists
    axyn = f"@{client.user.display_name}"
    if content.startswith(axyn):
        content = content[len(axyn) :]

    # Remove leading/trailing whitespace
    content = content.strip()

    return content
