Changelog
=========

v0.7.4 -- 2025-01-19
--------------------

debian specific changes:
* Fix https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=1080577

v0.7.3 -- 2025-01-16
--------------------

major changes:
 * system prompt: enforce citation and URL inclusion in responses

minor improvements:
 * readme: explain chunk size unit (bytes), not tokens (Closes: #46)
 * copyright: bump year
 * reader: support Debian nm-templates `pp1.*`, `pp2.BT{2,6,8}`.
   (full nm-templates support still WIP)
   Example: $ debgpt -f nm:pp1.PH0 -a 'answer briefly.'
 * readme: reorganize contents.

v0.7.2 -- 2025-01-11
--------------------

minor improvements:
 * DebGPT> Makefile: remove deprecated autopep8 target
 * DebGPT> cli: use repr() for frontend and model names in commit messages
 * cache: extend cache expiration to 1 month. Closes: #35
 * cli: add help function to list all supported reader specifications
 * cli: bugfix for extra arguments.
 * cli: dump session unconditionally to avoid token waste [Shengqi Chen]
 * cli: enhance sbuild reader to filter build logs and support custom paths (Closes: #42)
 * cli: update help for sbuild reader to include path support and filtering
 * cli: use repr() for prompt and frontend model details in commit messages
 * cli: workaround sqlite3 multithread expire refresh issue
 * frontend: append error in dumped session files [Shengqi Chen]
 * frontend: temporarily disable system message or temperature for o1-preview and o1-mini (Closes: #38)
 * frontend: try multiple ways to obtain the username [Shengqi Chen]
 * readme: add toc
 * readme: update backend part for ollama
 * remove the unused `debgpt_home` variable

v0.7.1 -- 2024-11-09
--------------------

Bugfixes:

* 25e5a33 bugfix: wrong arguments. impacts mapreduce parallelism

Features:

* 79d5a6b mapreduce: implement compact map mode and enable by default
* 13ec97c reader: implement debian mailing list reader.

Minor changes:

* various minor improvements, such as improve help/printed message clarity
* 2e37c7f readme: add link to the ai-noises repo for debgpt generated samples
* ddbc520 readme: add example for mailing list summary (Closes: #14, #25)

v0.7 -- 2024-11-08
------------------

Significant overhaul of the codebase. Major changes include:
* Re-licensed project from MIT/Expat to LGPL-3.0-or-later.
* Re-organize almost all python code and make it more modular and maintainable.
* Unified all context reader to `--file|-f` argument, including pdf, etc. See
  README for examples on usage and special grammar.
* Overhaul mapreduce code. Now it is much more efficient and faster, and
  robust.
* Implemented the vector DB, embeddding and retrieval system. Now you can store
  and retrieve the context and the generated response. But that part for CLI is
  still under development. That will be in the next release.
  * Supported Embedding frontends: OpenAI and Google.
* 233381d frontend: add support to xAI (Grok)
* 600ae4a cli: add a pipe mode which supports line-based inplace editing in vim
  (This might be broken now due to code refactor. Will be fixed in the next
  release)

Normal changes:
* f362d8d cli+cache: add delete-cache subcommand
* 287df1e cache: implement SQLite-backed cache with LZ4 compression and tests
* fa364e4 policy: move txt cache into sqlite cache
* various improvements to the configurator
* e078eb2 rename gemini frontend to google frontend
* 913bdb3 configurator: inherit all config options and auto edit the template (Closes: #26)
* 3f7499c frontend: add `/quit` command to interactive mode
* b82442d configurator(wizard): configure the embedding model as well
* b643c7f cli: add vdb subcommand: debgpt vdb [--db] ls
* e12d0de pyproject: add lz4 to dependencies
* add numpy to dependencies.
* 113ca09 debgpt: add a basic implementation of embedding model (client)
* 7633b17 vectordb: compress text field using lz4 for efficient storage
* 6fad04e cli: add --no-render_markdown option
* 2cf3687 cli: add -q to --quit|-Q
* 71a4878 debgpt: unify rich.console usage

Minor changes:
* yapf code styling (mainly Google style)
* overhaul readme and tutorial
* use AI to improve type annotation, quality, documentation, bugfix, and write
  functions.
* add tests and improve test coverage to 100% for most frequently used
  functions. AI (e.g. Copilot) can write simple test case very quickly.
  Really reduced my workload for developing tests. In most cases, I just need
  to type tab to accept the suggestion. Manual editing happens but not frequent.
* no longer support python 3.9
* 5680463 reader: enable caching and set cache expiration.
* 6492539 reader: use cache for read_url
* bf2ff19 reader: use pycurl if installed. Closes: #27
* misc improvements and bugfixes
* 7872534 cli: delete the genconf alias for genconfig
* b64dd86 defaults: unify console.log usage

v0.6 -- 2024-10-31
------------------

Major features and changes:

[Inplace Code Editing]

* d3382e4 feature: inplace file/code editing by LLM. It works.
* c9190f2 inplace: if commiting automatically, also record frontend and model
* f048e58 further add --inplace-git-add-commit option for git add+commit after inplace code edit.

[Configurator TUI]

* e43d8ed configurator: implement debgpt.configurator based on urwid for TUI fresh install guide
* 8e70c4d cli: let `debgpt config` (re)configure with the wizard
* a9c0050 cli: replace text fresh install guide with TUI.

Minor changes:

* 24449f5 update short description of the DebGPT project
* Improve the README, print message, and doc in the code.
* 37c1b07 feat: add render option to replay function for assistant messages
* 003da6d assets: generate a new logo for debgpt using DALLE3

v0.5.93 -- 2024-10-29
---------------------

New feature:

* 214c1c3 cli: add google search support for context loading (mapreduce)

Major changes:

* 34def61 debian: change `:sbuild` into `sbuild:` for mapreduce
* 1d20dee debian: change :policy and :devref into policy: and devref: for mapreduce
* cca73a8 cli: enable markdown rendering by default

Minor updates, documentation, and bugfixes:

* 5bb734c cli: allow specifying --mapreduce multiple times.
* 56aebed defaults: deprecate the default question templates. Difficult to remember and hence useless
* Improve readme.
* 816a7e3 do not remove left prompt when rendering LLM response as markdown
* 69a8a8a frontend: always retry in oneshot methods

v0.5.92 -- 2024-10-28
---------------------

Major feature updates:

* Add support for rendering LLM response markdown text with rich.
  Not enabled by default. Use `render_markdown = true` in the config file
  to enable it all the time.
  Example: `debgpt --render -a 'write a c++ hello world program'`

* PDF file support is added for both `--pdf` and `--mapreduce` arguments.
  Example: `debgpt -H --pdf ./some.pdf -a 'what is this?'`

Minor updates and bugfixes:

* Update readme with references and examples.
* render LLM response as markdown in replay.
* 4768d41 cli: make json file optional for replay command
* cce8d2f cli: remove fortune mode (deprecated)
* 9ffadf3 pyproject: add optional dependencies
* d6bf0c1 make: add pylint and simplify linting targets
* d09b9fa cli: add short aliases for mapreduce arguments
* readme: update installation instructions
* cace664 cli: do not print first-install-guide for first-time genconfig
* c6429e8 improve debugging message
* 9a1a724 cli: increase default mapreduce parallelism to 8
* d7536f6 mapreduce: simplify file type handling for text files.
  If mime type detect failed, just read as plain text.

v0.5.91 -- 2024-10-27
---------------------

Minor features::

* Add retry mechanism for rate limit exceeded errors in the mapreduce function.
  This is added for OpenAI, Google Gemini, and Anthropic frontends.
* mapreduce functionality now supports loading text from URLs.
  Example: http://.., https://..., file://....

Minor fixes:

* fed46bf frontend: add import error handling for service sdks
* improve verbose and debugging messages
* cli: organize argument parser in argument group
* 2d324c8 debgpt: add top_p parameter to config template
* 5dacfe1 debian: mapreduce: add support for loading text from URLs

v0.5.90 -- 2024-10-26
---------------------

Major Change:

The biggest change in this release is the introduction of the mapreduce
functionality which enables any-length text processing, which was not
possible before.

Examples:
$ debgpt -Hx <any-file-directory> -A <your-question>
$ debgpt -Hx ./debian -A 'what is this?'
$ debgpt -Hx ./debian -A 'how is this package built? how many binary packages will be produced?'
$ debgpt -Hx :policy -A 'what is the changes of the latest version compared to the previous version?'
$ debgpt -Hx :sbuild -a 'why does the build fail? do you have any suggestion?'

Changes:

* frontend: add oneshot() method for all frontends
* README: introduce mapreduce usage example.
* use yapf instead of autopep8 for code formatting
* debgpt: remove sbuild support in favor of refactor mapreduce load for build logs
* cli: add short '-a' option for '--ask' argument in mapreduce configuration
* cli: add --amend option to git commit subcommand.

v0.5.2 -- 2024-10-26
--------------------

Features:

* e618872 add support for Google Gemini frontend integration
* fa40aa2 add support for Anthropic frontend integration
* b5ccd43 cli: add support for loading latest sbuild build logs

Minor fixes and improvements:

* b052cf8 cli: fix session index display in interactive mode prompt after /reset
* 742c54e README: add interactive mode tips and commands

Currently supported frontends:
  (commercial): OpenAI, Google Gemini, Anthropic
  (self-hosted): vLLM, Ollama, Llamafile, ZMQ

v0.5.1 -- 2024-10-16
---------------------

Minor fixes:

* d2ab5c3 `defaults: update OpenAI model to gpt-4o`
* d65f9d5 cli: enhance fresh install detection with OpenAI base URL check
* 9b7d360 cli: refactor config template generation with helper function
* 3ee10de Apply autopep8.
* 9dbe4f9 frontend: bugfix: inherit OpenAIFrontend instead
* 3e287e4 metadata: add PyPI classifiers to pyproject.toml
* 9a66d94 frontend: reorder vLLM API key argument definition in CLI

v0.5.0 -- 2024-10-16
---------------------

Now we have a reasonable set of supported frontends:
  OpenAI, Ollama, Llamafile, vLLM, and ZMQ

New features:
* 07d6de3 frontend: add support for vLLM service integration

Minor fixes:

* 31cf21f frontend: use AbstractFrontend init directly instead of super()
* 8d76755 task: explicitly annotate debgpt usage for debgpt git commit
* ef269d2 defaults: be verbose on loading config and overriding configs
* 907831e genconfig: fix toml grammar error.

v0.4.95 -- 2024-10-16
---------------------

New features:

* eeab25d Add --monochrome to disable colorized outputs during conversation
* 38111eb Add ollama frontend (OpenAI-API compatibibility mode)
* c065fb6 Add llamafile frontend (alias to openai frontend)

Minor updates:

* 949d71e cli: Provide a fresh-install guide (Closes: #1064469)
* 943b107 frontend: Skip console output during config template generation

v0.4.94 -- 2024-01-12
---------------------

Major bug fixes:

* ed4914c Fix support for `OPENAI_API_KEY` env var. (Closes: #1060654)

Feature updates:

* 27e53d3 Improve git-commit prompt (Otto Kekäläinen)
* 166ed80 Refactor file selection in `debgpt` to allow line range specification.
  For example, you can use `debgpt -f pyproject.toml:3-10` to read from line 3
  (inclusive) to line 10 (exclusive). It's just python slicing.
* 1d12619 Add support for loading Arch Wiki pages. (but the wiki pages are
  really long. Can easily exceed the context length limit)

Minor updates:

* 5641d22 Fix misc typos and improve spelling (Otto Kekäläinen)
* 30d2ea3 pyflakes is really good
* 1640f71 Refactor CLI completion in debgpt.
* 0a9ef7b bts: filter out garbage from the HTML

v0.4.93 -- 2024-01-09
---------------------

New Features:

* 46798b3 Add pynew function to retrieve information from Python's What's New website.
* f611ec1 cli: Add support for loading CPython What's New website. (--pynew)

Minor changes:

* 0f50221 clear all pyflakes in this repo
* 3d35c1a readme: add -T for fortune examples where randomness is needed

v0.4.92 -- 2024-01-08
---------------------

Major changes:

* Use `debgpt genconfig` to auto-generate the config.toml template.
The original manually written one at `etc/config.toml` was deprecated.

* Implemented ordered argparse. The complicated argument order such
as `-f file1.txt --man man -f file2` will be correctly reflected in
the generated prompt.

Minor changes:

* Reorganize code and do the chore. Make CLI less verbose. More pytests.

v0.4.91 -- 2024-01-07
---------------------

Major bug fix:

* 87fb088 bring batch the accidentally deleted function

Minor updates:

* 3cc2d26 Add function to parse the order of selected arguments in the command line interface. (wip)
* 3a3eca4 make: add make install starget

v0.4.90 -- 2024-01-07
---------------------

Development release with massive breaking and major changes.

Breaking changes:

* Redesign CLI. It is more flexible and easier to use now. Please refer the
examples in README or the manpage. It is too long to describe here.

Major changes:

* Merge all doc in README.md and rewrite a portion of them.
* Make README.md compatible to manpage through pandoc.
* Overall all documentations and reorganize them.
* Support more text loaders for CLI.
* Rewrite argument subparsers for the CLI.

Minor changes:

* Merged all examples from demo.sh to README.md
* Remove conda environment YAML files. No longer necessary.
* Split pytest code to dedicated tests directory.
* Strip pytest from dependencies.
* Miscellaneous code organization.
* Removed replay examples in examples/ directory.
* Add debianization fiiles.

This release note is not written by LLM.

v0.4.0 -- 2024-01-04
--------------------

Breaking changes:

* the `-i (--iteractive)` command line option is removed. Interactive mode is the default now.
* `replay.py` is moved inside `debgpt/`. Use `debgpt replay` instead.

Majore changes:

* Refactor the subparsers in `main_cli.py`. The cmdline behavior slightly
  changed. For instance, previously `debgpt` will tell you what task it
  supports, but now it will directly enter the interaction with LLM without
  auto-generated first prompt. It is equivant to `debgpt none`. Use `debgpt
  -h/--help` to lookup tasks instead. Use `debgpt <task> -h` to check arguments
  for each task.
* Implemented the `dryrun` frontend. It quits after generating the first
  prompt. You can copy and paste this prompt into free-of-charge web-based
  LLMs.

Changes:

- Updated `demo.sh` script to use `debgpt replay` instead of `python3 replay.py`.
- Moved the `replay` functionality inside the `debgpt` directory.
- Added `-M` shortcut option for `--openai_model_id`.
- Added `--hide_first_prompt` option to improve user experience for certain tasks.
- Updated the documentation.
- Added `--multiline` support for prompt toolkit.
- Implemented a dry-run frontend to generate prompts for free web-based LLM.
- Suppressed all warnings in the CLI.
- Added support for `--temperature` and `--top_p` arguments.
- Improved documentation by adding links and updating example config.

v0.3.0 -- 2024-01-03
--------------------

Major updates:

* support OpenAI API now. you can specify `--openai_model_id` to specify a model.
When OpenAI Frontend is used, we will enable the streaming mode, which prints
LLM outputs in real time (word by word) to the terminal.

Minor updates:

* optimize frontend/cli loading speed.
* support config file (default is ~/.debgpt/config.toml)
* added `debgpt stdin < some-file.txt` and `debgpt file ... none`.
* fix device for pipeline when the user specified cpu.

v0.2.1 -- 2024-01-03
--------------------

This is a minor feature update.

* llm: switch to streaming mode when chatting locally. The LLM will
  generate tokens one by one in real-time.

v0.2 -- 2024-01-02
------------------

This is a Feature release

* llm: add Mixtral8x7B model.
* llm: switch to transformers.pipeline to enable multi-gpu inference

v0.1 -- 2024-01-02
-------------------

This is the Initial release.
