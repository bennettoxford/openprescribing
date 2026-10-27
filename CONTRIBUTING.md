# How to contribute

Thank you for your interest in contributing! If you haven't already, drop us a line on mail@openprescribing.net. We want you working on things you're excited about.

We use GitHub issues for suggestions and for bug tracking.

## Testing

We have unit tests for Python: `python manage.py test` and for JavaScript: `npm run test`. See the README for more details on setting up the project, and running tests.

The documentation could be undoubtedly be better: tell openprescribing-support@googlegroups.com if you get stuck, or have any suggestions.

## Submitting changes

Please fork the repo, then send a pull request with a clear list of what you've done (read more about [pull requests](https://help.github.com/articles/using-pull-requests/)).

Before you send the pull request, please make sure all tests pass, and add new tests for anything... new.

If you wanted to add functional tests in the front-end, we would love you forever.

Please follow our coding conventions (below) and make sure all of your commits are atomic (one feature per commit).

Always write a clear log message for your commits. One-line messages are fine for small changes, but bigger changes should look like this:

    $ git commit -m "A brief summary of the commit
    >
    > A paragraph describing what changed, why it changed, and its impact."

## Coding conventions

Python is [PEP8](https://www.python.org/dev/peps/pep-0008/).
