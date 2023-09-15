from multiprocessing.context import TimeoutError
from contextlib import suppress, closing
from os import makedirs, get_terminal_size, system as ossys, path, stat
from logging import (
    Formatter,
    FileHandler,
    INFO,
    basicConfig,
    DEBUG,
    warn,
    fatal,
    info,
    getLogger,
    WARNING,
)
from v2enlib.config import config
from time import monotonic, sleep
from resource import getrusage, RUSAGE_SELF
from platform import system
from librosa import note_to_hz
from hashlib import sha256
from soundfile import write as sfwrite
from subprocess import Popen
from difflib import SequenceMatcher
from multiprocessing.pool import Pool as mpPool, ThreadPool as mpThreadPool
from multiprocessing import Process as mpProcess, get_context
from tqdm import tqdm

import numpy as np


class Debugging:
    def __init__(self) -> None:
        formatter = Formatter("%(asctime)s - %(name)s - %(levelname)s\n%(message)s")
        makedirs("logs", exist_ok=True)
        makedirs(".wav", exist_ok=True)

        file_handler = FileHandler(f"./logs/{config.v2en.target}.log")
        file_handler.setLevel(INFO)
        file_handler.setFormatter(formatter)

        basicConfig(level=DEBUG, handlers=[file_handler])
        getLogger("httpx").setLevel(WARNING)

    @staticmethod
    def functionTimeout(timeout, func, *args, **kwargs):
        with mpThreadPool(processes=1) as pool:
            result = pool.apply_async(func=func, args=args, kwds=kwargs)
            output = kwargs.get("default_value", None)
            with suppress(TimeoutError):
                output = result.get(timeout=timeout or None)
            return output

    @staticmethod
    def measureFunction(func):
        def wrapper(*args, **kwargs):
            start_time = monotonic()
            result = func(*args, **kwargs)
            end_time = monotonic()
            execution_time = end_time - start_time
            before = getrusage(RUSAGE_SELF).ru_maxrss
            resource_consumption = before / 1024 / 1024  # Memory usage in MB
            if not (
                execution_time < config.v2en.allow.time
                and resource_consumption < config.v2en.allow.resource
            ):
                warn(
                    f"{func.__name__}'s result:\n\tExecution time: {execution_time} seconds\n\tMemory consumption: {resource_consumption} MB"
                )
            return result

        return wrapper

    @staticmethod
    def printError(text, error, important=False):
        text = f"{'_'*50}\n\tExpectation while {text}\n\tError type: {type(error)}\n\t{error}\n{chr(8254)*50}"
        fatal(text)
        if important:
            print(text)

    @staticmethod
    def printInfo(text):
        info(text)


class Terminal:
    @staticmethod
    def terminalWidth():
        try:
            return get_terminal_size().columns
        except Exception:
            return 0

    @staticmethod
    def cleanScreen() -> None:
        ossys("cls" if system() == "Windows" else "clear")


class Sound:
    @staticmethod
    def playNotes(notes, durations, note_start_times):
        """
        Plays multiple notes simultaneously with varying durations and decreasing volume using a thread pool.
        """
        pool = mpThreadPool(len(notes))
        for i in range(len(notes)):
            pool.apply_async(
                Sound.playNote,
                (
                    notes[i],
                    durations[i],
                    1 - (i / len(notes)),
                    durations[i],
                    note_start_times[i],
                ),
            )
        pool.close()
        pool.join()

    @staticmethod
    def playNote(note, duration, volume, note_duration, start_time):
        """
        Plays a single note with the given duration and volume using the soundfile library.
        """
        sr = 44100  # sample rate
        freq = note_to_hz(note)
        samples = scipy.signal.sawtooth(  # type: ignore
            2 * np.pi * np.arange(sr * note_duration) * freq / sr, 0.5
        )
        decay = np.linspace(volume, 0, int(sr * note_duration))
        scaled = samples * decay
        scaled /= np.max(np.abs(scaled))

        # Compute hash of audio data
        hashname = sha256(scaled).hexdigest()

        # Create subdirectory for stored audio files
        makedirs(".wav", exist_ok=True)

        # Check if file with the same hash already exists
        filename = path.join(".wav", f"{hashname[:10]}.wav")
        if not path.exists(filename):
            # Write scaled audio data to file
            sfwrite(filename, scaled, sr)

        sleep(start_time)

        # Play audio file using appropriate command depending on platform
        if system() == "Windows":
            Popen(
                [
                    "powershell",
                    'New-Object Media.SoundPlayer "{filename}"'.format(
                        filename=filename
                    ),
                ]
            )
        elif system() == "Darwin":
            Popen(["afplay", filename])
        else:
            Popen(["play", "-q", filename])


# other utils
def differentRatio(x, y):
    return SequenceMatcher(None, x, y).ratio()


def emptyFile(path):
    return stat(path).st_size == 0


class NoDaemonProcess(mpProcess):
    @property
    def daemon(self):
        return False

    @daemon.setter
    def daemon(self, val):
        pass


class NoDaemonContext(type(get_context())):
    Process = NoDaemonProcess


class Pool(mpPool):
    def __init__(self, *args, **kwargs):
        kwargs["context"] = NoDaemonContext()
        super(Pool, self).__init__(*args, **kwargs)

    @classmethod
    def function(cls, func, iterable, force_pro: int = None) -> list:
        if (len(iterable)) == 0:
            return []
        elif not config.v2en.thread.allow:
            return [
                func(cmd)
                for cmd in tqdm(
                    iterable,
                    leave=False,
                    desc=func.__name__,
                    disable=not config.v2en.allow.tqdm,
                )
            ]
        with closing(
            cls(
                processes=force_pro
                or min(len(iterable), max(1, config.v2en.thread.limit)),
            )
        ) as p, tqdm(
            total=len(iterable),
            leave=False,
            desc=func.__name__,
            disable=not config.v2en.allow.tqdm,
        ) as pbar:
            results = []
            for res in p.imap(func, iterable):
                pbar.update(1)
                results.append(res)
            return results

    @classmethod
    def args(
        cls,
        funcs: list,
        subexecutor,
        poolName: str = "",
        **kwargs,
    ) -> list:
        if not config.v2en.thread.allow:
            return [
                subexecutor([func, kwargs])
                for func in tqdm(
                    funcs,
                    leave=False,
                    desc=poolName,
                    disable=not config.v2en.allow.tqdm,
                )
            ]
        with closing(
            cls(processes=min(len(funcs), max(1, config.v2en.thread.limit)))
        ) as ex, tqdm(
            total=len(funcs),
            leave=False,
            desc=poolName,
            disable=not config.v2en.allow.tqdm,
        ) as pbar:
            results = []
            kwargsc = [dict(kwargs) for _ in range(len(funcs))]
            for res in ex.imap(
                subexecutor, [[func, kwargsc[i]] for i, func in enumerate(funcs)]
            ):
                pbar.update(1)
                results.append(res)
            return results


class ThreadPool(mpThreadPool):
    @classmethod
    def function(cls, func, iterable, force_pro: int = None) -> list:
        if (len(iterable)) == 0:
            return []
        elif not config.v2en.thread.allow:
            return [
                func(cmd)
                for cmd in tqdm(
                    iterable,
                    leave=False,
                    desc=func.__name__,
                    disable=not config.v2en.allow.tqdm,
                )
            ]
        with closing(
            cls(
                processes=force_pro
                or min(len(iterable), max(1, config.v2en.thread.limit)),
            )
        ) as p, tqdm(
            total=len(iterable),
            leave=False,
            desc=func.__name__,
            disable=not config.v2en.allow.tqdm,
        ) as pbar:
            results = []
            for res in p.imap(func, iterable):
                pbar.update(1)
                results.append(res)
            return results

    @classmethod
    def args(
        cls,
        funcs: list,
        subexecutor,
        poolName: str = "",
        **kwargs,
    ) -> list:
        if not config.v2en.thread.allow:
            return [
                subexecutor([func, kwargs])
                for func in tqdm(
                    funcs,
                    leave=False,
                    desc=poolName,
                    disable=not config.v2en.allow.tqdm,
                )
            ]
        with closing(
            cls(processes=min(len(funcs), max(1, config.v2en.thread.limit)))
        ) as ex, tqdm(
            total=len(funcs),
            leave=False,
            desc=poolName,
            disable=not config.v2en.allow.tqdm,
        ) as pbar:
            results = []
            for res in ex.imap(subexecutor, [(func, kwargs.copy()) for func in funcs]):
                pbar.update(1)
                results.append(res)
            return results


debuger = Debugging()
