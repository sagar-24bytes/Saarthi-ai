# -*- mode: python ; coding: utf-8 -*-
# Saarthi.spec — PyInstaller specification for Saarthi AI Assistant
# Bundles:
#   - GUI: CustomTkinter assets, themes, and fonts
#   - Speech: Faster-Whisper "small" model snapshot, Silero VAD ONNX, CTranslate2 engine & DLLs
#   - Audio: PortAudio binaries from _sounddevice_data
#   - Graph/LLM: LangGraph, LangChain Core, Pydantic, Requests
#   - Saarthi backend: Planner, Tools, Memory, Voice

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.abspath(SPECPATH)
VENV = os.path.join(BASE_DIR, '.venv', 'Lib', 'site-packages')

WHISPER_SNAPSHOT = os.path.join(
    os.path.expanduser('~'), '.cache', 'huggingface', 'hub',
    'models--Systran--faster-whisper-small', 'snapshots',
    '536b0662742c02347bc0e980a01041f333bce120'
)

CT2_DIR     = os.path.join(VENV, 'ctranslate2')
FW_DIR      = os.path.join(VENV, 'faster_whisper')
SD_DATA_DIR = os.path.join(VENV, '_sounddevice_data')

# ── Collected Data Files ───────────────────────────────────────────────────
datas = []

# Faster-Whisper "small" model snapshot (extracted to sys._MEIPASS/whisper_model)
if os.path.exists(WHISPER_SNAPSHOT):
    datas.append((WHISPER_SNAPSHOT, 'whisper_model'))

# Package data files (CustomTkinter themes/fonts, Faster-Whisper VAD, OnnxRuntime, LangGraph)
datas += collect_data_files('customtkinter')
datas += collect_data_files('faster_whisper')
datas += collect_data_files('onnxruntime')
datas += collect_data_files('langchain_core')
datas += collect_data_files('langgraph')

# PortAudio DLLs for sounddevice
if os.path.exists(SD_DATA_DIR):
    datas.append((SD_DATA_DIR, '_sounddevice_data'))

# CTranslate2 Python specs / package data
if os.path.exists(CT2_DIR):
    datas.append((CT2_DIR, 'ctranslate2'))

# ── Collected Binaries ─────────────────────────────────────────────────────
binaries = []
binaries += collect_dynamic_libs('ctranslate2')
binaries += collect_dynamic_libs('onnxruntime')
binaries += collect_dynamic_libs('scipy')

# Ensure CTranslate2 core runtime DLLs are explicitly present
ct2_dlls = ['ctranslate2.dll', 'libiomp5md.dll', 'cudnn64_9.dll', '_ext.cp310-win_amd64.pyd']
for dll in ct2_dlls:
    dll_path = os.path.join(CT2_DIR, dll)
    if os.path.exists(dll_path):
        target_dir = 'ctranslate2' if dll.endswith('.pyd') else '.'
        binaries.append((dll_path, target_dir))

# ── Analysis ───────────────────────────────────────────────────────────────
a = Analysis(
    ['gui.py'],
    pathex=[BASE_DIR],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        # ── LangGraph & LangChain ──────────────────────────────────────────
        'langgraph',
        'langgraph.graph',
        'langgraph.graph.state',
        'langgraph.checkpoint.memory',
        'langgraph.types',
        'langchain_core',
        'langchain_core.messages',
        'langchain_core.messages.human',

        # ── CTranslate2 / Faster-Whisper ───────────────────────────────────
        'ctranslate2',
        'ctranslate2._ext',
        'faster_whisper',
        'faster_whisper.audio',
        'faster_whisper.feature_extractor',
        'faster_whisper.tokenizer',
        'faster_whisper.transcribe',
        'faster_whisper.vad',
        'faster_whisper.utils',
        'onnxruntime',
        'onnxruntime.capi',
        'onnxruntime.capi._pybind_state',

        # ── Audio / SoundDevice ────────────────────────────────────────────
        'sounddevice',
        '_sounddevice',
        '_sounddevice_data',
        '_cffi_backend',
        'soundfile',
        'scipy.io.wavfile',
        'scipy.signal',

        # ── GUI / CustomTkinter ────────────────────────────────────────────
        'tkinter',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'customtkinter',
        'PIL',
        'PIL.ImageTk',

        # ── Saarthi Internal Modules ───────────────────────────────────────
        'planner',
        'planner.graph',
        'planner.planner',
        'planner.intent',
        'planner.llm',
        'planner.state',
        'tools',
        'tools.actions',
        'tools.confirmation',
        'tools.executor',
        'tools.normalizer',
        'tools.registry',
        'tools.search',
        'tools.validator',
        'memory',
        'memory.context',
        'memory.path_resolver',
        'memory.persistent',
        'voice',
        'voice.input',

        # ── System / Utilities ─────────────────────────────────────────────
        'sqlite3',
        'uuid',
        'json',
        'requests',
        'pydantic',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
        'vosk',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Saarthi',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[
        'ctranslate2.dll',
        'libiomp5md.dll',
        'cudnn64_9.dll',
        'onnxruntime.dll',
        'onnxruntime_providers_shared.dll',
        'libportaudio64bit.dll',
        'libportaudio64bit-asio.dll',
    ],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
