import asyncio
import subprocess
from telethon.tl.types import Message
from .. import loader, utils
import logging
import shlex

log = logging.getLogger(__name__)

@loader.tds
class RomchikConsoleMod(loader.Module):
    strings = {
        "name": "RomchikConsole 0.8",
        "usage": ".run <команда> для выполнения команды в консоли.",
        "error": "<b>Произошла ошибка при выполнении команды.</b>",
        "loaded": "Модуль <bold>RomchikConsole 0.8</bold> успешно загружен!",
        "no_command": "<b>Не указана команда для выполнения!</b>",
        "result": "<b>Результат выполнения команды:</b>\n🟩 <b>Stdout:</b>\n<code>{}</code>\n🟥 <b>Stderr:</b>\n<code>{}</code>",
    }

    def __init__(self):
        self.name = self.strings["name"]
        self._me = None
        self.__author__ = "@Remurchenok789"
        self.__version__ = "0.8.0"

    async def client_ready(self, client, db):
        self._me = await client.get_me()

    @loader.command(
        ru_doc="Выполняет команду в консоли.",
        eng_doc="Executes a command in the console.",
        name="run"
    )
    async def run(self, message: Message):
        """Выполняет команду в консоли."""
        try:
            command = utils.get_args_raw(message)
            if not command:
                return await utils.answer(message, self.strings["no_command"])

            # Разбираем команду на аргументы
            args = shlex.split(command)
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            stdout_result = ""
            stderr_result = ""
            last_update_time = None

            async def read_stream(stream, result_var, update_message, stream_name):
                nonlocal stdout_result, stderr_result, last_update_time
                while True:
                    line = await stream.readline()
                    if line:
                        decoded_line = line.decode().strip()
                        if stream_name == 'stdout':
                            stdout_result += decoded_line + "\n"
                        else:
                            stderr_result += decoded_line + "\n"

                        current_time = asyncio.get_event_loop().time()
                        # Устанавливаем скорость обновления в зависимости от команды
                        if command.startswith("ping"):
                            speed = 5.0
                        else:
                            speed = 1.5

                        if not last_update_time or current_time - last_update_time >= speed:
                            result_text = f"<b>Результат выполнения команды:</b>\n🟩 <b>Stdout:</b>\n<code>{stdout_result}</code>\n🟥 <b>Stderr:</b>\n<code>{stderr_result}</code>"
                            # Truncate the result text to fit within Telegram's message length limit
                            max_length = 4096 - len("<b>Результат выполнения команды:</b>\n🟩 <b>Stdout:</b>\n<code></code>\n🟥 <b>Stderr:</b>\n<code></code>")
                            truncated_result_text = result_text[:max_length] + (result_text[max_length:] and '...')

                            await utils.answer(update_message, truncated_result_text, parse_mode="html")
                            last_update_time = current_time
                    else:
                        break

            # Отправляем начальное сообщение
            loading_message = await utils.answer(message, "<b>Начинаем выполнение команды...</b>")

            try:
                # Запускаем задачи для чтения stdout и stderr с учетом таймаута
                await asyncio.wait_for(
                    asyncio.gather(
                        read_stream(process.stdout, stdout_result, loading_message, 'stdout'),
                        read_stream(process.stderr, stderr_result, loading_message, 'stderr')
                    ),
                    timeout=5.0 if command.startswith("ping") else None
                )
            except asyncio.TimeoutError:
                await utils.answer(loading_message, "<b>Команда была завершена из-за превышения времени выполнения (5 секунд).</b>")
                process.kill()
                await process.wait()

            # Дожидаемся завершения процесса
            await process.wait()

            # Завершаем процесс и обновляем сообщение в конце
            if not stdout_result and not stderr_result:
                result = "Команда выполнена, но ничего не было выведено."
            else:
                result = self.strings["result"].format(stdout_result or "Нет вывода", stderr_result or "Нет ошибок")

            await utils.answer(loading_message, result, parse_mode="html")

        except Exception as e:
            await utils.answer(message, self.strings["error"])
            log.error(str(e))