from v2enlib.utils import debuger, differentRatio, Pool, ThreadPool
from v2enlib.gSQL import GSQLClass
from v2enlib.config import config
from deep_translator import GoogleTranslator
from langcodes import Language as lcLanguage
from translators.server import TranslatorError
from string import punctuation
from tabulate import tabulate
from functools import lru_cache
from gc import collect
import httpx

# Exceptions
from requests.exceptions import *
from deep_translator.exceptions import *


class InputSent:
    def __init__(
        self,
        first: str = "",
        second: str = "",
        isFrom: str = "",
        accurate: float = 0,
    ) -> None:
        self.isFrom = isFrom or "Data set"
        self.first = first or "N/A"
        self.second = second or "N/A"
        self.accurate = accurate

    def isValid(self) -> bool:
        return bool(self.first and self.second)

    def SQLFormat(self) -> tuple:
        return self.first, self.second


class Executor:
    @staticmethod
    def transIntoList(cmd):
        return Translator.intoList(*cmd)

    @staticmethod
    def addPair(cmd):
        return Language.addPair(*cmd)

    @staticmethod
    def checkSpelling(cmd):
        return Language.checkSpelling(*cmd)


class Translator:
    @staticmethod
    def deepGoogle(
        query_text: str, from_language: str, to_language: str, *args, **kwargs
    ) -> str:
        try:
            return GoogleTranslator(source=from_language, target=to_language).translate(
                query_text
            )
        except (
            LanguageNotSupportedException,
            InvalidSourceOrTargetLanguage,
        ):
            return Translator.deepGoogle(
                query_text,
                str(lcLanguage.get(from_language)),
                str(lcLanguage.get(to_language)),
            )
        except Exception as e:
            debuger.printError(Translator.deepGoogle.__name__, e)
            return ""

    @staticmethod
    def translatorsTransSub(cmd):
        def execute(func, **kwargs):
            ou = ""
            allow_error = (
                ChunkedEncodingError,
                HTTPError,
                ReadTimeout,
                KeyError,
                JSONDecodeError,
            )
            if cmd[0]:
                try:
                    ou = func(**kwargs)
                except Exception as e:
                    if isinstance(e, TranslatorError):
                        try:
                            if tcmd := Translator.handleCodes(cmd[1], e):
                                ou = func(**tcmd)
                        except HTTPError as e:
                            raise e
                        except Exception as e:
                            debuger.printError(
                                Translator.translatorsTransSub.__name__, e
                            )
                    elif any(isinstance(e, i) for i in allow_error):
                        try:
                            ou = debuger.functionTimeout(
                                func=Translator.deepGoogle,
                                **cmd[1],
                            )
                        except Exception as e:
                            debuger.printError(
                                Translator.translatorsTransSub.__name__, e
                            )
                    else:
                        debuger.printError(Translator.translatorsTransSub.__name__, e)
            return [ou, func.__name__]

        return execute(cmd[0], **cmd[1])

    @staticmethod
    def translatorsTrans(cmd: list, trans_timeout, config) -> list:
        return ThreadPool.args(
            funcs=config.v2en.trans_dict.values(),
            subexecutor=Translator.translatorsTransSub,
            poolName="translationPool",
            query_text=cmd[0],
            from_language=cmd[1],
            to_language=cmd[2],
            timeout=trans_timeout,
            config=config,
            if_print_warning=False,
        )

    # TODO Rename this here and in `translatorsTrans`
    @staticmethod
    @debuger.measureFunction
    def handleCodes(cmd, e) -> list:
        try:
            if len(e.args):
                tcmd, execute = cmd.copy(), False
                target = e.args[0].split(" ")[1][:-4]
                for i in ["vie", "vi_VN", "vi-VN"]:
                    if (e.args[0]).find(i) != -1:
                        tcmd[target] = i
                        execute = True
                if execute:
                    return tcmd
        except Exception as e:
            debuger.printError("change format language", e)
        return []

    @staticmethod
    def intoList(sent, source_lang, target_lang, target_dictionary, timeout, config):
        return ThreadPool.function(
            func=Executor.checkSpelling,
            iterable=[
                [Language.convert(e[0]), target_dictionary, target_lang, e[1]]
                for e in Translator.translatorsTrans(
                    cmd=[sent, source_lang, target_lang],
                    trans_timeout=timeout,
                    config=config,
                )
            ],
        )


class Language:
    @staticmethod
    @debuger.measureFunction
    @lru_cache(maxsize=1024)
    def checkSpelling(text: str, dictionary: list, lang: str, tname: str = ""):
        word = ""
        try:
            words = text.split()
            outstr = ""
            for idx, word in enumerate(words):
                if (
                    word not in dictionary
                    and not word.isnumeric()
                    and word not in punctuation
                    and not Language.existOnWiki(word, lang)
                    and not Language.existOnWiki(f"{words[idx-1]} {word}", lang)
                    and (
                        idx + 1 >= len(words)
                        or not Language.existOnWiki(f"{word} {words[idx+1]}", lang)
                    )
                ):
                    if config.v2en.raise_on_error_word:
                        raise ValueError(
                            f"https://{lang}.wiktionary.org/wiki/{word} not existed"
                        )
                    outstr = ""
                    break
                outstr += f"{word} "
                if word.isalpha() and word not in dictionary:
                    dictionary.append(word)
            return [outstr, tname] if tname else outstr
        except Exception as e:
            debuger.printError(Language.checkSpelling.__name__, e)
        return ["", ""] if tname else ""

    @staticmethod
    @debuger.measureFunction
    def addPair(input_sent: InputSent, dictionary, cmds, config):
        is_agree, fdump = False, []
        print_data = ["Data set", input_sent.first, input_sent.second, "N/A"]
        fdump, sdump = "", ""
        input_sent.first, input_sent.second = ThreadPool.function(
            func=Executor.checkSpelling,
            iterable=[
                [Language.convert(e[0].replace("\n", "")), dictionary, e[1]]
                for e in [
                    [input_sent.first, config.v2en.flang],
                    [input_sent.second, config.v2en.slang],
                ]
            ],
        )
        if not input_sent.isValid():
            return "", "", False
        is_error, trans_data = True, []
        for first_tran, second_tran in zip(
            *Pool.function(
                func=Executor.transIntoList,
                iterable=[
                    [
                        input_sent.first,
                        config.v2en.flang,
                        config.v2en.slang,
                        dictionary,
                        config.v2en.trans_timeout,
                        config,
                    ],
                    [
                        input_sent.second,
                        config.v2en.slang,
                        config.v2en.flang,
                        dictionary,
                        config.v2en.trans_timeout,
                        config,
                    ],
                ],
            )
        ):
            if first_tran[0]:
                trans_data.append(
                    InputSent(
                        input_sent.first,
                        first_tran[0],
                        first_tran[1],
                        differentRatio(input_sent.second, first_tran[0]),
                    )
                )
            if second_tran[0]:
                trans_data.append(
                    InputSent(
                        second_tran[0],
                        input_sent.second,
                        second_tran[1],
                        differentRatio(input_sent.first, second_tran[0]),
                    )
                )

        if any(e.accurate > config.v2en.accept_percentage for e in trans_data):
            is_agree = True
            is_error = False
        if is_agree and not is_error:
            cmds += [[input_sent.first, input_sent.second]] + [
                e.SQLFormat()
                for e in trans_data
                if e.accurate > config.v2en.accept_percentage
            ]
        if is_error:
            fdump, sdump = input_sent.first, input_sent.second

        print_data += [
            [e.isFrom, e.first, e.second, e.accurate]
            for e in trans_data
            if e.accurate > config.v2en.accept_percentage
        ]
        if len(print_data) < config.v2en.allow.sentences:
            debuger.printInfo(
                tabulate(
                    tabular_data=print_data,
                    headers=["From", "Source", "Target", "Accuracy?"],
                    tablefmt="fancy_grid",
                    showindex="always",
                    maxcolwidths=[None, None, 45, 45, 7],
                    floatfmt=(".2f" * 5),
                ),
            )
        del trans_data, print_data
        collect()
        return fdump, sdump, is_agree

    @staticmethod
    @lru_cache(maxsize=1024)
    def convert(x: str) -> str:
        if not x:
            return ""
        # fix bad data
        if "apos" in x or "quot" in x or "amp" in x or "&#91;" in x or "--" in x:
            return ""

        x = x.replace("“", " “ ").replace("”", " ” ").replace("’", " ’ ")
        for punc in punctuation:
            x = x.replace(punc, f" {punc} ")
        try:
            return x.lower().replace("  ", " ").replace("  ", " ")
        except Exception as e:
            debuger.printError(Language.convert.__name__, e)
            return ""

    @staticmethod
    @lru_cache(maxsize=1024)
    def getWikitionaryHeaders(word: str) -> httpx.Response:
        return httpx.get(f"https://en.wiktionary.org/wiki/{word}")

    @staticmethod
    @lru_cache(maxsize=1024)
    def existOnWiki(word: str, lang: str) -> bool:
        display_name = lcLanguage.make(language=lang).display_name()

        response = Language.getWikitionaryHeaders(word=word)
        return (
            f'href="#{display_name}"' in response.headers.get("link", "")
            or f'id="{display_name}"' in response.text
        )

    @staticmethod
    def loadDictionary(sheet: str) -> list:
        try:
            return GSQLClass(sheet, "dictionary").getCol(1)
        except Exception as e:
            debuger.printError(Language.loadDictionary.__name__, e)
        return []

    @staticmethod
    def saveDictionary(dictionary):
        try:
            sheet = GSQLClass(config.v2en.sheet, "dictionary")
            sheet.clear()
            sheet.writeLRow([[e] for e in sorted(list(dict.fromkeys(dictionary)))])
            sheet.autoFit()
        except Exception as e:
            debuger.printError(Language.saveDictionary.__name__, e)
