"""Non-destructive critical-path source-stage overlap for experimental VIDEO-001.
Preserves original 17 ASR + 16 OCR workers, original media and sampling.
Only starts independent follow-up tasks as soon as their own input is ready.
"""
from concurrent.futures import ThreadPoolExecutor

def overlap_sources(audio_task, scan_task, board_task, chat_task):
    """Run source-preparation dependencies in a DAG; propagate failures."""
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="video001-prep") as pool:
        audio = pool.submit(audio_task)
        scan = pool.submit(scan_task)
        def board_branch():
            manifest = audio.result()
            return manifest, board_task(manifest)
        def chat_branch():
            index = scan.result()
            return index, chat_task(index)
        board_future = pool.submit(board_branch)
        chat_future = pool.submit(chat_branch)
        manifest, board = board_future.result()
        index, chat = chat_future.result()
    return manifest, index, board, chat
