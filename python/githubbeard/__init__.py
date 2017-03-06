from functools import partial, wraps

from skybeard.beards import BeardChatHandler
from skybeard.bearddbtable import BeardDBTable
from skybeard.utils import get_beard_config, get_args
from skybeard.decorators import onerror
from skybeard.mixins import PaginatorMixin

from github import Github
from github.GithubException import UnknownObjectException

from . import format_

import logging

logger = logging.getLogger(__name__)

CONFIG = get_beard_config()


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


class GithubBeard(PaginatorMixin, BeardChatHandler):

    __userhelp__ = "Github. In a beard."

    __commands__ = [
        ("currentusersrepos", 'get_current_user_repos',
         'Lists clickable links to repos of specifed user.'),
        ("getrepo", "get_repo",
         "Gets information about given repo specifed in 1st arg."),
        ("getpr", "get_pending_pulls",
         "Gets pending pull requests from specified repo (1st arg)"),
        ("getdefaultrepo", "get_default_repo",
         "Gets default repo for this chat."),
        ("setdefaultrepo", "set_default_repo",
         "Sets default repo for this chat."),
        ("searchrepos", "search_repos",
         "Searches for repositories in github."),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.github = Github(CONFIG['token'])
        self.default_repo_table = BeardDBTable(self, 'default_repo')
        self.search_repos_results = BeardDBTable(self, 'search_repos_results')

    @onerror
    @get_args_as_str_or_ask("What would you like to search github for?")
    async def search_repos(self, msg, args):
        await self.sender.sendChatAction('typing')
        search_results = self.github.search_repositories(args)
        search_results = [i for i in search_results[:30]]

        await self.send_paginated_message(
            search_results, format_.make_repo_msg_text)

    @onerror
    async def get_default_repo(self, msg):
        with self.default_repo_table as table:
            entry = table.find_one(chat_id=self.chat_id)
            if entry:
                await self.sender.sendMessage(
                    "Default repo for this chat: {}".format(entry['repo']))
            else:
                await self.sender.sendMessage("No repo set.")

    @onerror
    @get_args_as_str_or_ask("What would you like the default repo to be?")
    async def set_default_repo(self, msg, args):
        with self.default_repo_table as table:
            entry = table.insert(dict(chat_id=self.chat_id, repo=args))

            if entry:
                await self.sender.sendMessage("Repo set to: {}".format(args))
            else:
                raise Exception("Not sure how, but the entry failed to be got?")

    async def user_not_found(self):
        """Send a message explaining the user was not found."""
        await self.sender.sendMessage("User not found.")

    @onerror("Failed to get repo info.")
    @get_args_as_str_or_ask("Which repo would you like to get?")
    async def get_repo(self, msg, args):
        """Gets information about a github repo."""
        repo = self.github.get_repo(args)
        await self.sender.sendMessage("Repo name: {}".format(repo.name))
        await self.sender.sendMessage("Repo str: {}".format(repo))

    @onerror("Failed to get repo info.")
    async def get_pending_pulls(self, msg):
        """Gets information about a github repo."""
        args = get_args(msg)
        if args:
            repo = self.github.get_repo(args[0])
        else:
            with self.default_repo_table as table:
                entry = table.find_one(chat_id=self.chat_id)
            repo = self.github.get_repo(entry['repo'])
        pull_requests = repo.get_pulls()

        pr = None
        for pr in pull_requests:
            await self.sender.sendMessage(
                await format_.make_pull_msg_text_informal(pr),
                parse_mode='HTML')
        if pr is None:
            await self.sender.sendMessage(
                "No pull requests found for {}.".format(repo.name))

    @onerror
    async def get_current_user_repos(self, msg):
        args = get_args(msg)
        try:
            try:
                user = self.github.get_user(args[0])
            except IndexError:
                user = self.github.get_user()
        except UnknownObjectException:
            await self.user_not_found()
            return

        name = user.name or user.login
        await self.sender.sendMessage("Github repos for {}:".format(name))
        await self.sender.sendChatAction(action="typing")
        repos = ""
        for r in user.get_repos():
            repos += "- <a href=\"{}\">{}</a>\n".format(r.url, r.name)
        await self.sender.sendMessage(repos, parse_mode='HTML')
