#main.py

import asyncio
import sys
from colorama import Fore, Style, init as colorama_init

from core.config import Config
from core.logger_config import setup_logger
from core.command_dispatcher import CommandDispatcher
from core.voice_listener import listen_for_voice
from core.tts import speak, set_tts_config 
from core.utils.data_sanitizer import contains_control_chars

# Import the plain async functions (no @tool decorators)
from tools.system_tools import (
    open_application,
    open_website,
    get_weather,
    close_application,
)
from tools.agent_tools import setup_tools

from langchain.tools import Tool

# Initialize colorama
colorama_init(autoreset=True)

async def main():
    # 1) Load configuration (reads API keys from env safely)
    try:
        config = Config()
    except Exception as e:
        print(Fore.RED + f"Configuration error: {e}")
        return

    # 2) Configure TTS (API keys or local engines)
    set_tts_config(config)

    # 3) Bootstrap logger
    logger = setup_logger(config) # Assign to local variable 'logger'

    # 4) Instantiate the LLM (Gemini, OpenAI, etc.) from config
    llm = config.init_llm()

    # 5) Build the list of agent tools
    agent_tools_list = setup_tools(config, llm, logger=logger)

    search_tool_func = None
    for t in agent_tools_list:
        if t.name == "duckduckgo_search":
            search_tool_func = t.func
            break

    
    voice_flag = {"enabled": False} 

    tool_map = {
        "open_application": Tool(
            name="open_application",
            func=open_application,
            description="Opens a specified application by name (e.g., 'notepad')."
        ),
        "open_website": Tool(
            name="open_website",
            func=open_website,
            description="Opens a specified URL in the default browser (e.g. 'https://google.com')."
        ),
        "get_weather": Tool(
            name="get_weather",
            func=get_weather,
            description="Gets the current weather for a specified location (e.g., 'Durban')."
        ),
        "close_application": Tool(
            name="close_application",
            func=close_application,
            description="Closes a specified application by name (e.g., 'notepad')."
        ),
    }

    dispatcher = CommandDispatcher(
        llm=llm,
        tools=tool_map,
        agent_tools=agent_tools_list,
        search_tool=search_tool_func,
        logger=logger,
        voice_flag_ref=voice_flag, 
        config=config,
    )

   
    print(
        Fore.GREEN
        + f"{config.ASSISTANT_NAME} is ready. Type 'enable voice mode' to speak, or type your command:"
    )
    try:
        await speak(config.ASSISTANT_GREETING)
    except Exception as e_tts:
        logger.warning(f"Initial TTS greeting failed (might be normal if no audio output): {e_tts}")
        pass

    voice_listener_task = None 
    
    loop = asyncio.get_running_loop()
    while True:
        try:
            if voice_flag["enabled"]:
                if not voice_listener_task or voice_listener_task.done():
                    logger.info("Starting voice listener task in background...")
                    voice_listener_task = asyncio.create_task(
                        listen_for_voice(
                            voice_flag_ref=voice_flag,
                            process_command_fn=dispatcher.process_command,
                            config=config,
                            logger=logger,
                        )
                    )
                await asyncio.sleep(0.1) 
                continue

            prompt_message = Fore.WHITE + "You> " + Style.RESET_ALL
            command = await loop.run_in_executor(None, input, prompt_message)
            command = command.strip()

            if not command or contains_control_chars(command):
                print(Fore.RED + "Invalid input detected—please use standard characters only.")
                continue

            low_command = command.lower()
            if low_command in ["exit", "quit", "goodbye"]:
                bye_message = config.ASSISTANT_FAREWELL
                print(Fore.GREEN + f"{config.ASSISTANT_NAME}: {bye_message}")
                await speak(bye_message)

                if voice_listener_task and not voice_listener_task.done():
                    voice_listener_task.cancel()
                    logger.info("Cancelled voice listener task during exit.")
                    try:
                        await voice_listener_task
                    except asyncio.CancelledError:
                        pass
                break 
            
            await dispatcher.process_command(command)

        except EOFError:
            logger.warning("EOFError received from input. This usually means stdin was closed. Exiting REPL.")
            print(Fore.YELLOW + "Input stream closed. Exiting application.")
            break
        except KeyboardInterrupt:

            print(Fore.YELLOW + "\nCommand input interrupted. Type 'exit' or 'quit' to close.")
            continue 

    logger.debug("Session ended.")


if __name__ == "__main__":
    
    _main_logger = None 

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\nApplication interrupted by user (Ctrl+C).")
        
        try:
            from core.config import Config as _Cfg
            from core.tts import speak as _speak_final 
            _cfg = _Cfg()

            set_tts_config(_cfg) 
            farewell_msg = f"Session terminated. {_cfg.ASSISTANT_FAREWELL}"
            print(Fore.GREEN + farewell_msg) 
            asyncio.run(_speak_final(farewell_msg))
        except Exception as e_ki_speak:
            print(Fore.RED + f"Could not speak farewell message during KeyboardInterrupt: {e_ki_speak}")
        finally:
            sys.exit(0)
    except EOFError:
        
        print(Fore.RED + "Fatal EOFError: Application input stream was closed unexpectedly at a high level.")
        sys.exit(1)
    except Exception as e:
        print(Fore.RED + f"An unexpected fatal error occurred: {e}")
        
        try:
            from core.config import Config as _CfgEmergency
            from core.logger_config import setup_logger as _setup_logger_emergency
            _cfg_emergency = _CfgEmergency()
            _emergency_logger = _setup_logger_emergency(_cfg_emergency, for_emergency=True)
            _emergency_logger.error("Fatal error during execution at top level: %s", e, exc_info=True)
            print(Fore.RED + "An internal error occurred—please check the log for details.")
        except Exception as e_log:
            print(Fore.RED + f"Additionally, failed to log the fatal error: {e_log}")
        finally:
            sys.exit(1)
