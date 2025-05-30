'''
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
'''
from typing import Iterable, Optional, Dict
import urwid
import os
import re
import sys
from . import defaults
from . import arguments

default = defaults.Config()
console = defaults.console

_TITLE = 'DebGPT Configurator'


def _abort_on_None(value: Optional[str]) -> None:
    if value is None:
        print('Aborted.')
        exit(1)


class ListBoxVimKeys(urwid.ListBox):

    def keypress(self, size, key) -> None:
        key_map = {
            'k': 'up',
            'j': 'down',
        }
        if key in ('esc', 'q', 'Q'):
            sys.exit(1)
        super().keypress(size, key_map.get(key, key))


class SingleChoice(object):

    # we store the user choice here
    _choice: Optional[str] = None

    @staticmethod
    def exit_on_esc(key: str) -> None:
        if key in ('esc', ):
            sys.exit(1)

    def item_chosen(self, button: urwid.Button, choice: str) -> None:
        SingleChoice._choice = choice
        raise urwid.ExitMainLoop(choice)

    def __init__(self,
                 title: str,
                 question: str,
                 choices: Iterable[str],
                 helpmsg: str,
                 statusmsg: str,
                 *,
                 focus: int = 0):
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
        pile = urwid.Pile(buttons)
        pile.set_focus(focus)
        body.append(urwid.LineBox(pile))
        # build the help message between menu and footer
        body.extend([
            urwid.Divider(),
            urwid.Text(helpmsg),
        ])
        # assemble the widgets
        body = ListBoxVimKeys(urwid.SimpleFocusListWalker(body))
        frame = urwid.Frame(header=header, body=body, footer=footer)
        frame = urwid.Padding(frame, left=1, right=1)
        loop = urwid.MainLoop(frame,
                              palette=[("reversed", "standout", "")],
                              unhandled_input=self.exit_on_esc)
        self.loop = loop

    def run(self):
        try:
            self.loop.run()
        except urwid.ExitMainLoop:
            return None
        return self._choice


class SingleEdit(object):

    # we store the user choice here
    _choice: Optional[str] = None

    @staticmethod
    def exit_on_esc(key: str) -> None:
        if key in ('esc', ):
            sys.exit(1)
        elif key in ('enter', ):
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
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
        conf['openai_base_url'] = value
    if frontend == 'openai' and 'openai_api_key' not in current_config:
        value = SingleEdit(
            _TITLE, "Enter the OpenAI API key:", default['openai_api_key'],
            "Typically your key can be found here: https://platform.openai.com/settings/organization/api-keys",
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
        conf['openai_api_key'] = value
    if frontend == 'openai' and not is_embedding and 'openai_model' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the OpenAI API model name:",
            default['openai_model'],
            'If not sure, just keep the default. Available options: https://platform.openai.com/docs/models',
            'Press Enter to confirm. Press Esc to abort.').run()
        _abort_on_None(value)
        conf['openai_model'] = value
    if frontend == 'openai' and is_embedding and 'openai_embedding_model' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator",
            "Enter the OpenAI API embedding model name:",
            default['openai_embedding_model'],
            'If not sure, just keep the default.',
            'Press Enter to confirm. Press Esc to abort.').run()
        _abort_on_None(value)
        conf['openai_embedding_model'] = value

    # anthropic part
    if frontend == 'anthropic' and 'anthropic_api_key' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the Anthropic API key:",
            default['anthropic_api_key'],
            "Typicall your key can be found here: https://console.anthropic.com/settings/keys",
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
        conf['anthropic_api_key'] = value
    if frontend == 'anthropic' and 'anthropic_model' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the Anthropic model name:",
            default['anthropic_model'],
            "If not sure, just keep the default. Available options: https://docs.anthropic.com/en/docs/about-claude/models",
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
        conf['anthropic_model'] = value

    # google part
    if frontend == 'google' and 'google_api_key' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the Google Gemini API key:",
            default['google_api_key'],
            "Typically found here: https://aistudio.google.com/app/apikey",
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
        conf['google_api_key'] = value
    if frontend == 'google' and not is_embedding and 'google_model' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the Google model name:",
            default['google_model'],
            "If not sure, just keep the default. Available options: https://ai.google.dev/gemini-api/docs/models/gemini",
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
        conf['google_model'] = value
    if frontend == 'google' and is_embedding and 'google_embedding_model' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the Google embedding model name:",
            default['google_embedding_model'],
            "If not sure, just keep the default.",
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
        conf['google_embedding_model'] = value

    # xai part
    if frontend == 'xai' and 'xai_api_key' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the xAI API key:",
            default['xai_api_key'],
            "Typically found here: https://console.x.ai/",
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
        conf['xai_api_key'] = value
    if frontend == 'xai' and not is_embedding and 'xai_model' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the xAI model name:",
            default['xai_model'],
            "If not sure, just keep the default. Available options: https://console.x.ai/",
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
        conf['xai_model'] = value

    # nvidia part
    if frontend == 'nvidia' and 'nvidia_base_url' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the NVIDIA NIM/NeMo service url:",
            default['nvidia_base_url'],
            "Default is https://integrate.api.nvidia.com/v1",
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
        conf['nvidia_base_url'] = value
    if frontend == 'nvidia' and 'nvidia_api_key' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the NVIDIA NIM/NeMo API key:",
            default['nvidia_api_key'],
            "Typically found here: https://build.nvidia.com/explore/discover",
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
        conf['nvidia_api_key'] = value
    if frontend == 'nvidia' and not is_embedding and 'nvidia_model' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the NVIDIA NIM/NeMo model name:",
            default['nvidia_model'],
            "If not sure, just keep the default. Available options: https://build.nvidia.com/explore/discover",
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
        conf['nvidia_model'] = value

    # ollama part
    if frontend == 'ollama' and 'ollama_base_url' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the Ollama service url:",
            default['ollama_base_url'],
            "Reference: https://github.com/ollama/ollama/blob/main/README.md",
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
        conf['ollama_base_url'] = value
    if frontend == 'ollama' and 'ollama_model' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the Ollama model name:",
            default['ollama_model'],
            "Reference: https://github.com/ollama/ollama/blob/main/README.md",
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
        conf['ollama_model'] = value

    # llamacpp part
    if frontend == 'llamacpp' and 'llamacpp_base_url' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the llama-server (llama.cpp) service url:",
            default['llamacpp_base_url'],
            "Reference: https://github.com/ggerganov/llama.cpp/blob/master/examples/server/README.md",
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
        conf['llamacpp_base_url'] = value

    # deepseek part
    if frontend == 'deepseek' and 'deepseek_base_url' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the DeepSeek service url:",
            default['deepseek_base_url'],
            "Just keep the default if you intend to use DeepSeek API service. Reference: https://api-docs.deepseek.com/",
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
        conf['deepseek_base_url'] = value

    if frontend == 'deepseek' and 'deepseek_api_key' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the DeepSeek API key:",
            default['deepseek_api_key'],
            "Typically found here: https://platform.deepseek.com/api_keys",
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
        conf['deepseek_api_key'] = value

    if frontend == 'deepseek' and 'deepseek_model' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the DeepSeek model name:",
            default['deepseek_model'],
            "If not sure, just keep the default. As of Jan 24 2025, the available models are: deepseek-chat, deepseek-reasoner. The list of latest models can be found here: https://api-docs.deepseek.com/quick_start/pricing",
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
        conf['deepseek_model'] = value

    # llamafile part
    if frontend == 'llamafile' and 'llamafile_base_url' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the LlamaFile service url:",
            default['llamafile_base_url'],
            "Reference: https://github.com/Mozilla-Ocho/llamafile",
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
        conf['llamafile_base_url'] = value

    # vllm part
    if frontend == 'vllm' and 'vllm_base_url' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the vLLM service url:",
            default['vllm_base_url'],
            "Reference: https://docs.vllm.ai/en/stable/",
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
        conf['vllm_base_url'] = value
    if frontend == 'vllm' and 'vllm_api_key' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the vLLM API key:",
            default['vllm_api_key'],
            "Reference: https://docs.vllm.ai/en/stable/",
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
        conf['vllm_api_key'] = value
    if frontend == 'vllm' and 'vllm_model' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the vLLM model name:",
            default['vllm_model'],
            "Reference: https://docs.vllm.ai/en/stable/",
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
        conf['vllm_model'] = value

    # zmq part
    if frontend == 'zmq' and 'zmq_backend' not in current_config:
        value = SingleEdit(
            "DebGPT Configurator", "Enter the DebGPT ZMQ Backend URL:",
            default['zmq_backend'],
            "The service endpoint where you launched debgpt backend.",
            "Press Enter to confirm. Press Esc to abort.").run()
        _abort_on_None(value)
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
    focus = {True: 0, False: 1}[default['render_markdown']]
    value = SingleChoice("DebGPT Configurator",
                         "Render LLM response (Markdown) in terminal?",
                         ['yes', 'no'],
                         "Default is 'yes' (recommended). This option \
produces fancy terminal printing with markdown stream.",
                         "Press Enter to confirm. Press Esc to abort.",
                         focus=focus).run()
    _abort_on_None(value)
    conf['render_markdown'] = value == 'yes'
    return conf


def _request_overwrite_config(dest: str) -> bool:
    '''
    ask the user whether to overwrite the existing configuration file
    '''
    value = SingleChoice(
        "DebGPT Configurator",
        f"Configuration file {repr(dest)} already exists. \
Overwrite?", ['no', 'yes'], "The existing options will be inherited. We will \
simply refresh the configuration file with the updates from this wizard. Press Esc to abort.",
        "Press Enter to confirm. Press Esc to abort.").run()
    _abort_on_None(value)
    return value == 'yes'


def _edit_config_template(config_template: str, key: str, value: str) -> str:
    '''
    Edit the configuration template (toml file). Updating the value of
    the specified key.

    Args:
        config_template: the configuration template as a string
        key: the key to be updated
        value: the value to be updated
    Returns:
        the updated configuration template
    '''
    lines = config_template.split('\n')
    newlines = []
    for line in lines:
        if re.match(r'^\s*{}\s*='.format(key), line):
            line = '{} = {}'.format(key, value)
        newlines.append(line)
    return '\n'.join(newlines)


def fresh_install_guide(dest: Optional[str] = None) -> dict:
    '''
    This function is a configuration guide for fresh installation of DebGPT.
    '''
    conf = dict()
    config_template: str = arguments.parse_args([]).config_template

    if dest and os.path.exists(dest):
        overwrite = _request_overwrite_config(dest)
        _abort_on_None(overwrite)
        if not overwrite:
            print('Aborted.')
            exit(0)

    # step 1: select a frontend
    frontends = [
        'OpenAI    (GPT)    | commercial,  OpenAI-API',
        'Anthropic (Claude) | commercial,  Anthropic-API',
        'Google    (Gemini) | commercial,  Google-API',
        'xAI       (Grok)   | commercial,  OpenAI-API',
        'Nvidia    (*)      | commercial,  OpenAI-API', 
        'DeepSeek           | commercial,  OpenAI-API, MIT-Licensed Model',
        'Ollama    (*)      | self-hosted, OpenAI-API',
        'llama.cpp (*)      | self-hosted, OpenAI-API',
        'LlamaFile (*)      | self-hosted, OpenAI-API',
        'vLLM      (*)      | self-hosted, OpenAI-API',
        'ZMQ       (*)      | self-hosted, DebGPT built-in',
        'Dryrun    (N/A)    | debug,       DebGPT built-in',
    ]
    frontends_focus = {
        'openai': 0,
        'anthropic': 1,
        'google': 2,
        'xai': 3,
        'nvidia': 4,
        'deepseek': 5,
        'ollama': 6,
        'llamacpp': 7,
        'llamafile': 8,
        'vllm': 9,
        'zmq': 10,
        'dryrun': 11,
    }[default['frontend']]

    frontend = SingleChoice("DebGPT Configurator",
                            "Select a frontend that DebGPT will use:",
                            frontends,
                            "A frontend is a client that communicates with \
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
using the `--frontend|-F` argument.",
                            "Press Enter to confirm. Press Esc to abort.",
                            focus=frontends_focus).run()
    _abort_on_None(frontend)
    frontend = frontend.split(' ')[0].lower().replace('.', '')
    conf['frontend'] = frontend

    # step 2: ask for the frontend-specific configuration
    extra = _request_frontend_specific_config(frontend)
    conf.update(extra)

#    # TODO: only ask for the embedding frontend-specific configuration
#    #       when the embedding frontend is really used.
#    # step 3: ask for the embedding frontend
#    embedding_frontends = [
#        'OpenAI    | commercial,  OpenAI-API',
#        'Google    | commercial,  Google-API',
#        'Random    | debug,       DebGPT built-in',
#    ]
#    embedding_frontends_focus = {
#        'openai': 0,
#        'google': 1,
#        'random': 2,
#    }[default['embedding_frontend']]
#    embedding_frontend = SingleChoice(
#        "DebGPT Configurator",
#        "Select an embedding frontend that DebGPT will use:",
#        embedding_frontends,
#        "An embedding model turns text into vector embeddings, \
#unlocking use cases like search. Choose a frontend that will compute the \
#embedding vectors.\n\n\
#The embedding frontend can be different from the frontend.\n\n\
#If you are not going to use the embedding-realted feature, such as vectordb,\
#retrieval, retrieval-augmented-generation (RAG), etc., you can select 'Random'.",
#        "Press Enter to confirm. Press Esc to abort.",
#        focus=embedding_frontends_focus).run()
#    _abort_on_None(embedding_frontend)
#    embedding_frontend = embedding_frontend.split(' ')[0].lower()
#    conf['embedding_frontend'] = embedding_frontend
#
#    # step 4: ask for the embedding frontend-specific configuration
#    newconf = _request_frontend_specific_config(embedding_frontend,
#                                                conf,
#                                                is_embedding=True)
#    conf.update(newconf)

    # step 3: ask for the common CLI behavior configuration
    extra = _request_common_cli_behavior_config()
    conf.update(extra)

    # edit the configuration template
    for k, v in conf.items():
        if isinstance(v, bool):
            v = 'true' if v else 'false'
            config_template = _edit_config_template(config_template, k, v)
        elif isinstance(v, str):
            config_template = _edit_config_template(config_template, k,
                                                    repr(v))
        else:
            raise ValueError('Unexpected type:', type(v))
    config_template += '\n'  # new line at the end

    # final: write configuration to specified destination
    if dest:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'wt') as f:
            f.write(config_template)
        console.log('Config written to:', dest)
        console.print('[white on violet]>_< Enjoy DebGPT!')
    else:
        # verbose print
        console.print('Configuration (config.toml):')
        print('```')
        print(config_template)
        print('```')

    return conf


if __name__ == '__main__':
    miniconfig = fresh_install_guide()
