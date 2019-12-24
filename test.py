import os.path

from chatterbot import ChatBot
from chatterbot.conversation import Statement
from chatterbot.trainers import ChatterBotCorpusTrainer


# Create a chatbot
chatbot = ChatBot(
    'John Doe',
    storage_adapter='chatterbot.storage.SQLStorageAdapter',
    database_uri='sqlite:///database.sqlite3',
    logic_adapters=[
        'chatterbot.logic.MathematicalEvaluation',
        'chatterbot.logic.BestMatch',
        {
            'import_path': 'chatterbot.logic.BestMatch',
            'default_response': 'I am sorry, but I do not understand.',
            'maximum_similarity_threshold': 0.90
        }
    ]
)

if not os.path.exists('database.sqlite3'):
    # Do initial training
    cc_trainer = ChatterBotCorpusTrainer(chatbot)
    cc_trainer.train('chatterbot.corpus.english')


if __name__ == '__main__':
    # Get conversation details
    person = input('Your name: ')
    convo_id = input('Conversation id: ')

    # Start a conversation
    response = Statement('Hello!', conversation=convo_id)
    print(response)

    while True:
        # Get input from user
        query = Statement(
            input('> '),
            in_response_to=response.text,
            conversation=convo_id,
            persona=person,
        )

        # Show output from bot
        response = chatbot.get_response(query)
        print(response)
