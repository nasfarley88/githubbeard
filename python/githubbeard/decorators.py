from functools import wraps, partial

from skybeard.utils import get_args


def get_args_as_str_or_ask(text):
    """Gets arguments as a string or asks the question in text.

    Often, telegram commands can take arguments directly after the command or
    they can ask for information once the command has been sent. With this
    decorator, this happens automatically, e.g.

    .. code::python
        # Map this function to /whatsyourname

        @get_args_as_str_or_ask("What's your name?")
        async def whats_your_name(self, msg, args):
            await self.sender.sendMessage("Hello, {}.".format(args))

    will behave as:
    .. code::
        > /whatsyourname Reginald
        < Hello, Reginald.

    or
    .. code::
        > /whatsyourname
        < What's your name?
        > Reginald
        < Hello, Reginald.

    """
    return partial(_get_args_as_str_or_ask_decorator, text=text)


def _get_args_as_str_or_ask_decorator(f, text):
    """See get_args_as_str_or_ask for docs."""
    @wraps(f)
    async def g(beard, msg):
        args = get_args(msg, return_string=True)
        if not args:
            await beard.sender.sendMessage(text)
            resp = await beard.listener.wait()

            args = resp['text']

        await f(beard, msg, args)

    return g

