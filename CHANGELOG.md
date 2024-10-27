Changelog
=========

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

