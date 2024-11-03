'''
MIT License

Copyright (c) 2024 Mo Zhou <lumin@debian.org>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''
from typing import Iterable, Optional, Dict
import urwid
import os
import rich
from . import defaults

default = defaults.Config(verbose=True)
console = defaults.console


class SingleChoice(object):

    # we store the user choice here
    _choice: Optional[str] = None

    @staticmethod
    def exit_on_esc(key: str) -> None:
        if key in ('esc', ):
            raise urwid.ExitMainLoop()

    def item_chosen(self, button: urwid.Button, choice: str) -> None:
        SingleChoice._choice = choice
        raise urwid.ExitMainLoop(choice)

    def __init__(self, title: str, question: str, choices: Iterable[str],
                 helpmsg: str, statusmsg: str):
        # header
        header = urwid.AttrMap(urwid.Text(title, align='center'), 'reversed')
        footer = urwid.Text(statusmsg)
        # build the question between header and menu
        body = [
            urwid.Divider(),
            urwid.Text(question),
            urwid.Divider(),
        ]
        # build the menu
        buttons = []
        for c in choices:
            button = urwid.Button(c)
            urwid.connect_signal(button, "click", self.item_chosen, c)
            buttons.append(urwid.AttrMap(button, None, focus_map="reversed"))
        body.append(urwid.LineBox(urwid.Pile(buttons)))
        # build the help message between menu and footer
        body.extend([
            urwid.Divider(),
            urwid.Text(helpmsg),
        ])
        # assemble the widgets
        body = urwid.ListBox(urwid.SimpleFocusListWalker(body))
        frame = urwid.Frame(header=header, body=body, footer=footer)
        frame = urwid.Padding(frame, left=1, right=1)
        loop = urwid.MainLoop(frame,
                              palette=[("reversed", "standout", "")],
                              unhandled_input=self.exit_on_esc)
        self.loop = loop

    def run(self):
        self.loop.run()
        return self._choice


class SingleEdit(object):

    # we store the user choice here
    _choice: Optional[str] = None

    @staticmethod
    def exit_on_esc(key: str) -> None:
        if key in ('esc', 'enter'):
            raise urwid.ExitMainLoop()

    def edit_update(self, edit: urwid.Edit, new_edit_text: str) -> None:
        self._choice = new_edit_text

    def __init__(self, title: str, question: str, default: str, helpmsg: str,
                 statusmsg: str):
        # process arguments
        self._choice = default
        # header and footer
        header = urwid.AttrMap(urwid.Text(title, align='center'), 'reversed')
        footer = urwid.Text(statusmsg)
        # build the question between header and menu
        body = [
            urwid.Divider(),
            urwid.Padding(urwid.Text(question), left=1, right=1),
            urwid.Divider(),
        ]
        # build the edit widget
        edit = urwid.Edit("", default)
        urwid.connect_signal(edit, 'change', self.edit_update)
        edit = urwid.LineBox(edit)
        body.append(edit)
        body.extend([
            urwid.Divider(),
            urwid.Padding(urwid.Text(helpmsg), left=1, right=1),
        ])
        # assemble the widgets
        body = urwid.ListBox(urwid.SimpleFocusListWalker(body))
        frame = urwid.Frame(header=header, body=body, footer=footer)
        frame = urwid.Padding(frame, left=1, right=1)
        loop = urwid.MainLoop(frame,
                              palette=[("reversed", "standout", "")],
                              unhandled_input=self.exit_on_esc)
        self.loop = loop

    def run(self):
        self.loop.run()
        return self._choice


_TITLE = 'DebGPT Configurator'


def _request_frontend_specific_config(frontend: str,
                                      current_config: Dict = dict(),
                                      is_embedding: bool = False) -> dict:
    '''
    ask the user to provide the frontend-specific configuration
    '''
    conf = dict()

    # openai part
    if frontend == 'openai' and 'openai_base_url' not in current_config:
        value = SingleEdit(
            _TITLE, "Enter the OpenAI base url:", default['openai_base_url'],
            "Keep the default as is, if you do not intend to use this API on a different compatible service.",
            "Press Esc to abort.").run()
        conf['openai_base_url'] = value
    if frontend == 'openai' and 'openai_api_key' not in current_config:
        value = SingleEdit(
            _TITLE, "Enter the OpenAI API key:", default['openai_api_key'],
            "Typically your key can be found here: https://platform.openai.com/settings/organization/api-keys",
            "Press Esc to abort.").run()
        conf['openai_api_key'] = value
    if frontend == 'openai' and not is_embedding and 'openai_model' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the OpenAI API model name:",
            default['openai_model'],
            'If not sure, just keep the default. Available options: https://platform.openai.com/docs/models',
            'Press Esc to abort.').run()
        conf['openai_model'] = value
    if frontend == 'openai' and is_embedding and 'openai_embedding_model' not in current_config:
        value = SingleEdit("DebGPT Configurator",
                           "Enter the OpenAI API embedding model name:",
                           default['openai_embedding_model'],
                           'If not sure, just keep the default.',
                           'Press Esc to abort.').run()
        conf['openai_embedding_model'] = value

    # anthropic part
    if frontend == 'anthropic' and 'anthropic_api_key' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the Anthropic API key:",
            default['anthropic_api_key'],
            "Typicall your key can be found here: https://console.anthropic.com/settings/keys",
            "Press Esc to abort.").run()
        conf['anthropic_api_key'] = value
    if frontend == 'anthropic' and 'anthropic_model' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the Anthropic model name:",
            default['anthropic_model'],
            "If not sure, just keep the default. Available options: https://docs.anthropic.com/en/docs/about-claude/models",
            "Press Esc to abort.").run()
        conf['anthropic_model'] = value

    # gemini part
    if frontend == 'gemini' and 'gemini_api_key' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the Google Gemini API key:",
            default['gemini_api_key'],
            "Typically found here: https://aistudio.google.com/app/apikey",
            "Press Esc to abort.").run()
        conf['gemini_api_key'] = value
    if frontend == 'gemini' and not is_embedding and 'gemini_model' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the Google model name:",
            default['gemini_model'],
            "If not sure, just keep the default. Available options: https://ai.google.dev/gemini-api/docs/models/gemini",
            "Press Esc to abort.").run()
        conf['gemini_model'] = value
    if frontend == 'gemini' and is_embedding and 'gemini_embedding_model' not in current_config:
        value = SingleEdit("DebGPT Configurator",
                           "Enter the Google embedding model name:",
                           default['gemini_embedding_model'],
                           "If not sure, just keep the default.",
                           "Press Esc to abort.").run()
        conf['gemini_embedding_model'] = value

    # ollama part
    if frontend == 'ollama' and 'ollama_base_url' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the Ollama service url:",
            default['ollama_base_url'],
            "Reference: https://github.com/ollama/ollama/blob/main/README.md",
            "Press Esc to abort.").run()
        conf['ollama_base_url'] = value
    if frontend == 'ollama' and 'ollama_model' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the Ollama model name:",
            default['ollama_model'],
            "Reference: https://github.com/ollama/ollama/blob/main/README.md",
            "Press Esc to abort.").run()
        conf['ollama_model'] = value

    # llamafile part
    if frontend == 'llamafile' and 'llamafile_base_url' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the LlamaFile service url:",
            default['llamafile_base_url'],
            "Reference: https://github.com/Mozilla-Ocho/llamafile",
            "Press Esc to abort.").run()
        conf['llamafile_base_url'] = value

    # vllm part
    if frontend == 'vllm' and 'vllm_base_url' not in current_config:
        value = SingleEdit("DebGPT Configurator",
                           "Enter the vLLM service url:",
                           default['vllm_base_url'],
                           "Reference: https://docs.vllm.ai/en/stable/",
                           "Press Esc to abort.").run()
        conf['vllm_base_url'] = value
    if frontend == 'vllm' and 'vllm_api_key' not in current_config:
        value = SingleEdit("DebGPT Configurator", "Enter the vLLM API key:",
                           default['vllm_api_key'],
                           "Reference: https://docs.vllm.ai/en/stable/",
                           "Press Esc to abort.").run()
        conf['vllm_api_key'] = value
    if frontend == 'vllm' and 'vllm_model' not in current_config:
        value = SingleEdit("DebGPT Configurator", "Enter the vLLM model name:",
                           default['vllm_model'],
                           "Reference: https://docs.vllm.ai/en/stable/",
                           "Press Esc to abort.").run()
        conf['vllm_model'] = value

    # zmq part
    if frontend == 'zmq' and 'zmq_backend' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the DebGPT ZMQ Backend URL:",
            default['zmq_backend'],
            "The service endpoint where you launched debgpt backend.",
            "Press Esc to abort.").run()
        conf['zmq_backend'] = value

    # dryrun part
    if frontend == 'dryrun':
        pass

    return conf


def _request_common_cli_behavior_config() -> dict:
    '''
    ask the user to provide the common CLI behavior configuration
    '''
    conf = dict()
    # 1. whether to render LLM response markdown
    value = SingleChoice(
        "DebGPT Configurator", "Render LLM response (Markdown) in terminal?",
        ['yes', 'no'], "Default is 'yes' (recommended). This option \
produces fancy terminal printing with markdown stream.",
        "Press Esc to abort.").run()
    conf['render_markdown'] = value == 'yes'
    return conf


def _request_overwrite_config(dest: str) -> bool:
    '''
    ask the user whether to overwrite the existing configuration file
    '''
    value = SingleChoice(
        "DebGPT Configurator",
        f"Configuration file {repr(dest)} already exists. \
Overwrite?", ['no', 'yes'], "Press Esc to abort.",
        "Press Esc to abort.").run()
    return value == 'yes'


def fresh_install_guide(dest: Optional[str] = None) -> dict:
    '''
    This function is a configuration guide for fresh installation of DebGPT.
    '''
    conf = dict()

    if dest and os.path.exists(dest):
        overwrite = _request_overwrite_config(dest)
        if not overwrite:
            print('Aborted.')
            exit(1)

    # step 1: select a frontend
    frontends = [
        'OpenAI    | commercial,  OpenAI-API',
        'Anthropic | commercial,  Anthropic-API',
        'Gemini    | commercial,  Google-API',
        'Ollama    | self-hosted, OpenAI-API',
        'LlamaFile | self-hosted, OpenAI-API',
        'vLLM      | self-hosted, OpenAI-API',
        'ZMQ       | self-hosted, DebGPT built-in',
        'Dryrun    | debug,       DebGPT built-in',
    ]

    frontend = SingleChoice(
        "DebGPT Configurator", "Select a frontend that DebGPT will use:",
        frontends, "A frontend is a client that communicates with \
its corresponding backend that serves large language model (LLM). \
To use a commercial \
service, you may need to sign up and pay for an API key. Besides, \
if you have a spare GPU or a powerful CPU, you can take a look at the \
self-hosted LLM services. A web search can direct you to the details.\n\n\
This configurator will generate a minimal configuration file for you to \
make DebGPT work with the selected frontend.\n\n\
For advanced usages and more options, you may generate a configuration \
template with the following command for manual editing:\n\n\
  $ debgpt genconfig > ~/.debgpt/config.yaml\n\n\
This could be useful if you wish to switch among multiple frontends \
using the `--frontend|-F` argument.", "Press Esc to abort.").run()
    if not frontend:
        print('Aborted.')
        exit(1)
    frontend = frontend.split(' ')[0].lower()
    conf['frontend'] = frontend

    # step 2: ask for the frontend-specific configuration
    extra = _request_frontend_specific_config(frontend)
    conf.update(extra)

    # step 3: ask for the embedding frontend
    embedding_frontends = [
        'OpenAI    | commercial,  OpenAI-API',
        'Gemini    | commercial,  Google-API',
        'Random    | debug,       DebGPT built-in',
    ]
    embedding_frontend = SingleChoice(
        "DebGPT Configurator",
        "Select an embedding frontend that DebGPT will use:",
        embedding_frontends,
        "An embedding model turns text into vector embeddings, \
unlocking use cases like search. Choose a frontend that will compute the \
embedding vectors.\n\n\
The embedding frontend can be different from the frontend.\n\n\
If you are not going to use the embedding-realted feature, such as vectordb,\
retrieval, retrieval-augmented-generation (RAG), etc., you can select 'Random'.",
        "Press Esc to abort.").run()
    if not embedding_frontend:
        print('Aborted.')
        exit(1)
    embedding_frontend = embedding_frontend.split(' ')[0].lower()
    conf['embedding_frontend'] = embedding_frontend

    # step 4: ask for the embedding frontend-specific configuration
    newconf = _request_frontend_specific_config(frontend,
                                                conf,
                                                is_embedding=True)
    conf.update(newconf)

    # step 3: ask for the common CLI behavior configuration
    extra = _request_common_cli_behavior_config()
    conf.update(extra)

    # final: write configuration to specified destination
    if dest:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'wt') as f:
            for k, v in conf.items():
                if isinstance(v, bool):
                    v = 'true' if v else 'false'
                    f.write('{} = {}\n'.format(k, v))
                else:
                    f.write('{} = {}\n'.format(k, repr(v)))
        console.print('Config written to:', dest)
        console.print('[white on violet]>_< Enjoy DebGPT!')
    else:
        # verbose print
        console.print('Minimal Configuration (config.toml):')
        print('```')
        for k, v in conf.items():
            if isinstance(v, bool):
                v = 'true' if v else 'false'
                print('{} = {}'.format(k, v))
            else:
                print('{} = {}'.format(k, repr(v)))
        print('```')

    return conf


if __name__ == '__main__':
    miniconfig = fresh_install_guide()
