% DebGPT(1) | General Purpose Terminal LLM Tool with Some Debian-Specific Design
% Copyright (C) 2024-2025 Mo Zhou <lumin@debian.org>; GNU LGPL-3.0+ License.

NAME
====

DebGPT - General Purpose Terminal LLM Tool with Some Debian-Specific Design

> "AI" = "Artificial Idiot"


SYNOPSIS
========

`debgpt [arguments] [subcommand [subcommand-arguments]]`

DESCRIPTION
===========

DebGPT is a lightweight terminal tool designed for everyday use with Large
Language Models (LLMs), aiming to explore their potential in aiding
Debian/Linux development. The possible use cases include general language
understanding and editing, code generation, writing documentation, code
editing, and more as you can imagine.

To achieve that, DebGPT gathers relevant information from various sources like
files, directories, and URLs, and compiles it into a prompt for the LLM. DebGPT
supports a range of LLM service providers, either commercial and self-hosted,
including OpenAI, Anthropic, Google Gemini, Ollama, LlamaFile, vLLM, and ZMQ
(DebGPT's built-in backend for self-containment). 

TABLE OF CONTENTS
=================

- [NAME](#name)
- [SYNOPSIS](#synopsis)
- [DESCRIPTION](#description)
- [QUICK START](#quick-start)
- [FRONTENDS](#frontends)
- [TUTORIAL](#tutorial)
  - [1. Chatting with LLM and CLI Behavior](#1-chatting-with-llm-and-cli-behavior)
  - [2. Context Readers for Additional Information](#2-context-readers-for-additional-information)
  - [3. Inplace Editing of a File](#3-inplace-editing-of-a-file)
  - [4. Vector Retriever for Most Relevant Information](#4-vector-retriever-for-most-relevant-information)
  - [5. MapReduce for Any Length Context](#5-mapreduce-for-any-length-context)
  - [6. Piping through Everywhere](#6-piping-through-everywhere)
  - [7. DebGPT Subcommands](#7-debgpt-subcommands)
  - [8. Prompt Engineering](#8-prompt-engineering)
  - [9. Debian Specific Usage Cases](#9-debian-specific-usage-cases)
- [TROUBLESHOOTING](#troubleshooting)
- [BACKEND](#backend)
  * [Available Backend Implementations](#available-backend-implementations)
  * [LLM Selections](#llm-selections)
  * [Hardware Requirements](#hardware-requirements)
  * [Usage of the ZMQ Backend](#usage-of-the-zmq-backend)
- [REFERENCES](#references)
- [LICENSE and ACKNOWLEDGEMENT](#license-and-acknowledgement)


QUICK START
===========

First, install `DebGPT` from PyPI or Git repository:

```
pip3 install debgpt
pip3 install git+https://salsa.debian.org/deeplearning-team/debgpt.git
```

The bare minimum "configuration" required to make `debgpt` work is
`export OPENAI_API_KEY="your-api-key"`. If anything else is needed,
use the TUI-based wizard to (re-)configure:

```
debgpt config
```

Or use `debgpt genconfig` to generate a configuration template and place it at
`$HOME/.debgpt/config.toml`.  Both `config` and `genconfig` will inherit any
existing configurations.

Upon completion, you can start an interactive chat with the LLM:

```
debgpt
```

Enjoy the chat!

Hint: A collection of samples generated using DebGPT can be found at
[this repository](https://salsa.debian.org/lumin/ai-noises).

FRONTENDS
=========

The frontend is a client that communicates with an LLM inference backend. It is
responsible for sending user input to the backend and receiving responses while
maintaining a history of interactions.

Available frontend options (specified by the `--frontend|-F`) are:
[`openai`](https://platform.openai.com/docs/overview),
[`anthropic`](https://console.anthropic.com/),
[`google`](https://ai.google.dev/gemini-api/),
[`xai`](https://console.x.ai/),
[`llamafile`](https://github.com/Mozilla-Ocho/llamafile),
[`ollama`](https://github.com/ollama/ollama),
[`vllm`](https://docs.vllm.ai/en/latest/),
`zmq` (DebGPT built-in),
`dryrun` (for debugging or copy-pasting information).

Note: For non-self-hosted backends, review third-party user agreements and
refrain from sending sensitive information.


TUTORIAL
========

The following examples are carefully ordered. You can start from the first
example and gradually move to the next one.

#### 1. Interaction Mode with LLM and CLI Behavior

When no arguments are given, `debgpt` leads you into a general terminal
chatting client with LLM backends. Use `debgpt -h` to see detailed options.

```
debgpt
```

During the interactive chatting mode, you may press `/` and see a list of
available escaped commands that will not be seen as LLM prompt.

* `/save <path.txt>`: save the last LLM response to the specified file.

* `/reset`: clear the context. So you can start a new conversation without quiting.

* `/quit`: quit the chatting mode. You can press `Ctrl-D` to quit as well.

The first user prompt can be provided through argument (`--ask|-A|-a`):

```
debgpt -A "Who are you? And what can LLM do?"
```

By specifying the `--quit|-Q` option, the program will quit after receiving
the first response from LLM. For instance, we can let it mimic `fortune`
with temperature 1.0 (`--temperature|-T 1.0`) for higher randomness:

```
debgpt -T 1.0 -QA 'Greet with me, and tell me a joke.'
```

After each session, the chatting history will be saved in `~/.debgpt` as a
json file in a unique name. The command `debgpt replay` can replay the last
session if you forgot what LLM has replied to you.

The program can write the last LLM response to a file through `-o <file>`,
and read question from `stdin`:

```
debgpt -Qa 'write a hello world in rakudo for me' -o hello.raku
debgpt -HQ stdin < question.txt | tee result.txt
```

After gettting familiarized with the fundamental usage and its CLI behavior,
we can directly move on to the most important feature of this tool, namely the
special prompt reader -- `MapReduce`.


#### 2. Context Readers for Additional Information

Context Reader is a function that reads the plain text contents from the
specified resource, and wrap them as a part of a prompt for the LLM. The
context readers can be arbitrarily combined together or specified multiple
times through the unified argument `--file|-f`. It can read from a file,
a PDF file, a directory, a URL, a Debian Policy section, a Debian Developer
Reference section, a Debian BTS page, a Debian build status page (buildd),
a Google search result, etc. The specification syntax of the unified reader
`--file|-f` can be found using the command `debgpt -f :` or `debgpt -f '?'`.

Some simple examples are shown below:

```
# read a plain text file or PDF file and ask a question
debgpt -Hf README.md -a 'very briefly teach me how to use this DebGPT.'
debgpt -Hf debgpt/policy.py -A 'explain the code'
debgpt -Hf my-resume.pdf -a 'Does this person have any foss-related experience?'

# read a directory
debgpt -Hf debian/ -a 'how is this package built? How many binary packages will be produced?'

# read a URL
debgpt -Hf 'https://www.debian.org/vote/2022/vote_003' -A 'Please explain the differences among the above choices.'

# pipe a command line
debgpt -Hf cmd:'git diff --staged' -A 'briefly summarize the changes and provide a git commit message.'
```

The reader can be specified multiple times to put multiple information source
into a single context.  The full list of supported reader specs, as well as
corresponding examples, can be printed using `debgpt -f :`, or `debgpt -f "?"`,
or `debgpt -x :`.

#### 3. Inplace Editing of a File

The argument **[--inplace|-i]** is for in-place editing of a file. It is a
read-write reader that does the same as `--file|-f` (read-only) does, but
the inplace one will write the LLM response back to the file. We expect the
user to use this feature for editing a file.

If specified, the edits (in UNIX diff format) will be printed to the screen.
The `--inplace|-i` will mandate the `--quit|-Q` behavior, and will turn
off markdown rendering.

The following example will ask LLM to edit the `pyproject.toml` file, adding
`pygments` to its dependencies. This really works correctly.

```
debgpt -Hi pyproject.toml -a 'edit this file, adding pygments to its dependencies.'
```

If working in a Git repository, we can make things more automated:
You may further append `--inplace-git-add-commit` to automatically add and
commit the changes to the Git repository. If you want to review before commit,
specify `--inplace-git-p-add-commit|-I` argument instead.

```
debgpt -Hi pyproject.toml -a 'edit this file, adding pygments to its dependencies.' --inplace-git-add-commit
```

The commit resulted by the above example can be seen at [this link](https://salsa.debian.org/deeplearning-team/debgpt/-/commit/968d7ab31cb3541f6733eb34bdf6cf13b6552b7d).
Recent LLMs are strong enough to easily and correctly add type annotations
and doc strings in DebGPT's python codebase, see example [here](https://salsa.debian.org/deeplearning-team/debgpt/-/commit/4735b38141eafd6aa9b0863fc73296aa41562aed).


#### 4. Vector Retriever for Most Relevant Information

> This is WIP. Leveraging the embeddings to retrieve.  Basically RAG.


#### 5. MapReduce for Any Length Context

The "MapReduce" feature is the choice if you want the LLM to read bulk documentations.

Generally, LLMs have a limited context length. If you want to ask a question
regarding a very long context, you can split the context into multiple parts,
and extract the relevant information from each part. Then, you can ask the
LLM to answer the question based on the extracted information.

The implementation of this is fairly simple: split the gathered information
texts until the pre-defined maximum chunk size is satisfied, ask the LLM to
extract relevant information from each chunk, and then repeatedly merge the
extracted information through LLM summarization, untill there is only one chunk
left.  As a result, this functionality can be very quota-consuming if you are
going to deal with long texts. Please keep an eye on your bill when you try
this on a paied API service.

This functionality is implemented as the `--mapreduce|-x` argument. The user
has to specify the `--ask|-A|-a` argument to tell LLM what kind of question we
want to ask so it can extract the right information. It will summarize if the
`--ask|-A|-a` argument is missing.

The key difference between the MapReduce and Vector Retriever is that
MapReduce will really make the language model read all information
you passed to it, while vector retriever will only make language model read
the most relevant several pieces of information stored in the database.

Some usage examples of MapReduce are as follows:

```
# load a long file (such as buildlog) and ask question
debgpt -Hx buildlog.txt -A 'Why does the build fail? How to fix it?'
debgpt -Hx 'https://www.debian.org/doc/debian-policy/policy.txt' -A 'what is the purpose of the archive?'
debgpt -Hx policy: -A 'what package should enter contrib instead of main or non-free?'

# this will automatically find the buildlog path
debgpt -Hx sbuild: -A 'why does the build fail? do you have any suggestion?'

# I'm really lazy to learn or recall details
debgpt -H -x policy: -x devref: -a 'which document (and which section) talked about Multi-Arch: ?'

# search google, read pages, and answer question (the --ask|-a|-A is the google search keyword unless specified following "google:")
debgpt -Hx google: -a 'how to start python programming?'
debgpt -Hx google:'debian packaging' -a 'how to learn debian packaging?'

# load a directory and ask question
debgpt -Hx . -a 'which file of this debgpt project implemented mapreduce? how does it work?'
debgpt -Hx . -a 'teach me how to use this software. Is there any hidden functionality that is not written in its readme?'
debgpt -Hx ./debian -A 'how is this package built? how many binary packages will be produced?'

# load Debian mailing list threads and answer question
debgpt -Hx ldo:debian-devel/2025/05 -a 'write a news report to summarize what happend in this month. Always cite the source URL.'
debgpt -Hx ldo:debian-vote/2025/04,05 -a 'what is the result of the AI DFSG gr? Always cite the source URL.'
```

The full list of supported reader specs, as well as corresponding examples, can
be printed using `debgpt -f :`, or `debgpt -f "?"`, or `debgpt -x :`.

The `-H` argument will skip printing the first prompt generated by `debgpt`,
because it is typically very lengthy, and only useful for debugging and
development purpose.  To further tweak the mapreduce behavior, you may want to
check the `--mapreduce_chunksize <int>` and `--mapreduce_parallelism <int>`
arguments.


#### 6. Piping through Everywhere

Being able to pipe the inputs and outputs among different programs is one of
the reasons why I love the UNIX philosophy.

The pipe mode is useful when you want to use `debgpt` in a shell script Try the
follows on the Makefile in debgpt repo. Later we will introduce a in-place
editing functionality which is more convenient than this one.

```
cat Makefile | debgpt -a 'delete the deprecated targets' pipe | tee tmp ; mv tmp Makefile; git diff
```

The pipe mode can be used for editing something in vim in-place.

```
# In vim debgpt/task.py, use 'V' mode to select the task_backend function, then 
:'<,'>!debgpt -a 'add type annotations and comments to this function' pipe
```

This looks interesting, right? `debgpt` has a git wrapper that automatically
generates the git commit message for the staged contents and commit the message.
Just try `debgpt git commit --amend` to see how it works. This will also be
mentioned in the subcommands section.


#### 7. DebGPT Subcommands

**Git subcommand.**

Let LLM automatically generate the git commit message, and call git to commit it:

```
debgpt git commit --amend
```

If you don't even want to `git commit --amend` the commited message, just
remove `--amend` from it.


#### 8. Prompt Engineering

As you may have seen, the biggest variation in LLM usage happens in the context
including how you provide the context readers, and how you ask the question
through `--ask|-A|-a`. By adjusting the way you provide those information
and ask the question, you can get significantly different results. To properly
make LLM work for you, you may need to go through some basic prompt engineering
methods.

The following are some references on this topic:

1. OpenAI's Guide https://platform.openai.com/docs/guides/prompt-engineering

Advanced usage of LLM such as
[Chain-of-Thought (CoT)](https://arxiv.org/pdf/2205.11916.pdf)
will not be covered in this document.
Please refer external resources for more information.

The usage of LLM is limited by our imaginations. I am glad to hear from you if
you have more good ideas on how we can make LLMs useful for Debian development:
https://salsa.debian.org/deeplearning-team/debgpt/-/issues


#### 9. Debian Specific Usage Cases

* Analysis of the sbuild buildlog

* Analysis of the ratt buildlog directory

* Evaluation on `nm-templates`. There is a reader spec design for this:
  `-f nm:<question_id>` for loading nm-template questions. It is just a
  convenient wrapper of multiple other readers. The following is a script
  for answering all questions from nm-templates automatically. The answers
  will be stored in plain text files.

```
# nm_assigned.txt
debgpt -f nm:nm_assigned -a 'pretend to be Mo Zhou <lumin@debian.org> and answer the question. Give concrete examples, and links as evidence supporting them are preferred.' -o nm-assigned-selfintro.txt

# nm_pp1.txt
for Q in PH0 PH1 PH2 PH3 PH4 PH5 PH6 PH7 PHa; do
debgpt -HQf nm:pp1.${Q} -a 'Be concise and answer in just several sentences.' -o nm-pp1-${Q}-brief.txt;
debgpt -HQf nm:pp1.${Q} -a 'Be precise and answer with details explained.' -o nm-pp1-${Q}-detail.txt;
done

# nm_pp1_extras.txt
for Q in PH0 PH8 PH9 PHb; do
debgpt -HQf nm:pp1e.${Q} -a 'Be concise and answer in just several sentences.' -o nm-pp1e-${Q}-brief.txt;
debgpt -HQf nm:pp1e.${Q} -a 'Be precise and answer with details explained.' -o nm-pp1e-${Q}-detail.txt;
done

# nm_pp2.txt
for Q in BT2 BT6 BT8; do
debgpt -HQf nm:pp2.${Q} -a 'Be concise and answer in just several sentences.' -o nm-pp2-${Q}-brief.txt;
debgpt -HQf nm:pp2.${Q} -a 'Be precise and answer with details explained.' -o nm-pp2-${Q}-detail.txt;
done
```


TROUBLESHOOTING
===============

* Context overlength: If the result from context readers (such as feeding
  `--file` with a huge text file) is too long, you
  can switch to the `--mapreduce|-x` special reader, or switch to a model
  or service provider that supports longer context.

* Chunk size (`--mapreduce_chunksize`): In DebGPT, the internal measurement
  of text length is simply bytes. That's because different LLMs use different
  tokenizers, and DebGPT wants to support as many LLM inference backends as
  possible. To simplify software development, I just use bytes. That means
  accurate calculation and detection of context overlength cannot be done.
  A rough estimate is that each token has 4 characters in English. That means,
  if your LLM context size is 32k (tokens), we should be able to use roughly
  128k (bytes) chunk size with DebGPT.


BACKENDS
========

The backend is the server side that runs the LLM inference and communicates
with the client frontend. It can be self-hosted or provided by a third party.
Here we only discuss the self-hosted backends, i.e., Ollama, llamaFile,
vLLM, and the DebGPT built-in ZMQ.

## Ollama

Please refer to [their official documentation](https://ollama.com/) for setting
up. Note, you may need to adjust the `num_ctx` parameter in a `Modelfile`:

```
FROM qwen2.5
PARAMETER num_ctx 65536
```

Use `ollama create <modelname> -f Modelfile` to create a model with the new
parameters. See upstream
[API documentation](https://github.com/ollama/ollama/blob/main/docs/api.md)
and [Modelfile documentation](https://github.com/ollama/ollama/blob/main/docs/modelfile.md)
for more details.

## llamaFile

TODO: write this part of doc.

## ZMQ (DebGPT Built-in)

This tool provides one backend implementation: `zmq`.

* `zmq`: Only needed when you choose the ZMQ front end for
  self-hosted LLM inference server.

If you plan to use the `openai` or `dryrun` frontends, there is no specific
hardware requirement. If you would like to self-host the LLM inference backend
(ZMQ backend), powerful hardware is required.

**LLM Selections**

The concrete hardware requirement depends on the
LLM you would like to use. A variety of open-access LLMs can be found here
> `https://huggingface.co/spaces/HuggingFaceH4/open_llm_leaderboard`
Generally, when trying to do prompt engineering only, the "instruction-tuned"
LLMs and "RL-tuned" (RL is reinforcement learning) LLMs are recommended.

The pretrained (raw) LLMs are not quite useful in this case, as they have not
yet gone through instruction tuning, nor reinforcement learning tuning
procedure.  These pretrained LLMs will more likely generate garbage and not
follow your instructions, or simply repeat your instruction.  We will only
revisit the pretrained LLMs when we plan to start collecting data and fine-tune
(e.g., LoRA) a model in the far future.

The following is a list of supported LLMs for self-hosting (this list will
be updated when there are new state-of-the-art open-access LLMs available):

* Mistral7B (`Mistral-7B-Instruct-v0.2`) (default)
: This model requires roughly 15GB of disks space to download.

* Mixtral8x7B (`Mixtral-8x7B-Instruct-v0.1`)
: This model is larger yet more powerful than the default LLM. In exchange, it
poses even higher hardware requirements. It takes roughly 60~100GB disk space
(I forgot this number. Will check later).

Different LLMs will pose different hardware requirements. Please see the
"Hardware Requirements" subsection below.

**Hardware Requirements**

By default, we recommend doing LLM inference in `fp16` precision. If the VRAM
(such as CUDA memory) is limited, you may also switch to even lower preicisions
such as `8bit` and `4bit`. For pure CPU inference, we only support `fp32`
precision now.

Note, Multi-GPU inference is supported by the underlying transformers library.
If you have multiple GPUs, this memory requirement is roughly divided by your number of GPUs.

Hardware requirements for the `Mistral7B` LLM:

* `Mistral7B` + `fp16` (cuda): 24GB+ VRAM preferred, but needs a 48GB GPU to run all the demos (some of them have a context as long as 8k). Example: Nvidia RTX A5000, Nvidia RTX 4090.
* `Mistral7B` + `8bit` (cuda): 12GB+ VRAM at minimum, but 24GB+ preferred so you can run all demos.
* `Mistral7B` + `4bit` (cuda): 6GB+ VRAM at minimum but 12GB+ preferred so you can run all demos. Example: Nvidia RTX 4070 (mobile) 8GB.
* `Mistral7B` + `fp32` (cpu): Requires 64GB+ of RAM, but a CPU is 100~400 times slower than a GPU for this workload and thus not recommended.

Hardware requirement for the `Mixtral8x7B` LLM:

* `Mixtral8x7B` + `fp16` (cuda): 90GB+ VRAM.
* `Mixtral8x7B` + `8bit` (cuda): 45GB+ VRAM.
* `Mixtral8x7B` + `4bit` (cuda): 23GB+ VRAM, but in order to make it work with long context such as 8k tokens, you still need 2x 48GB GPUs in 4bit precision.

See https://huggingface.co/blog/mixtral for more.

**Usage of the ZMQ Backend**

If you want to run the default LLM with different precisions:

```
debgpt backend --max_new_tokens=1024 --device cuda --precision fp16
debgpt backend --max_new_tokens=1024 --device cuda --precision bf16
debgpt backend --max_new_tokens=1024 --device cuda --precision 8bit
debgpt backend --max_new_tokens=1024 --device cuda --precision 4bit
```

The only supported precision on CPU is fp32 (for now).
If you want to fall back to CPU computation (very slow):

```
debgpt backend --max_new_tokens=1024 --device cpu --precision fp32
```

If you want to run a different LLM, such as `Mixtral8x7B`  than the default `Mistral7B`:

```
debgpt backend --max_new_tokens=1024 --device cuda --precision 4bit --llm Mixtral8x7B
```

The argument `--max_new_tokens` does not matter much and you can adjust it (it
is the maximum length of each llm reply). You can adjust it as wish.

REFERENCES
==========

[1] Access large language models from the command-line
: https://github.com/simonw/llm

[2] Turn your task descriptions into precise shell commands
: https://github.com/sderev/shellgenius

[3] the AI-native open-source embedding database
: https://github.com/chroma-core/chroma

[4] LangChain: Build context-aware reasoning applications
: https://python.langchain.com/docs/introduction/

[5] Ollama: Embedding Models
: https://ollama.com/blog/embedding-models

[6] OpenAI: Embedding Models
: https://platform.openai.com/docs/guides/embeddings

[7] Moonshot - A simple and modular tool to evaluate and red-team any LLM application.
: https://github.com/aiverify-foundation/moonshot?tab=readme-ov-file

[8] LLMxMapReduce (Concurrent work. Their method is more advanced than mine)
: https://arxiv.org/abs/2410.09342

LICENSE and ACKNOWLEDGEMENT
===========================

DebGPT development is helped with various open-access and commercial LLMs on
code suggestion, code writing, code editing, document writing, with human
reviews and modifications.

```
Copyright (C) 2024-2025 Mo Zhou <lumin@debian.org>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
```
