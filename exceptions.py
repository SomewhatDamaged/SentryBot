class SentryBotException(Exception):

    def __init__(self, message: str, variables: dict):
        self.message = message
        print(f"Encountered error: {message}")
        if not variables:
            return
        print( "Variables: ")
        for key, datum in variables.items():
            print(f"  {key}: {datum}")
