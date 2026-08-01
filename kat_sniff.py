#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KAT検証ツール: VRCPetが送るOSCを受信して文字盤テキストを復元表示する。

VRChatを閉じた状態で実行（UDP9000を使うため）。VRCPetがしゃべるたびに
復元テキストが表示される。VRCPetのログ(said)と同じ文字列になれば、
muchio_llm.py の文字テーブル・プロトコル理解が正しいことの証明になる。

  python kat_sniff.py
"""
import socket, sys

KANJI = "--kanji" in sys.argv
from muchio_llm import CHARSET, KCHARSET, osc_parse as parse
REV8 = {v: k for k, v in CHARSET.items()}
REV16 = {v: k for k, v in KCHARSET.items()}

def _to_byte(f):
    b = round(float(f) * 127.0)
    return b + 256 if b < 0 else b

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("127.0.0.1", 9000))
    except OSError:
        print("UDP9000をbindできません。VRChatを閉じてから実行してください。")
        sys.exit(1)
    print("受信待ち... (VRCPetがしゃべると盤面を表示。Ctrl+Cで終了)")
    board = [0] * 128   # 128字改造アバター対応(無改造はポインタ1-8しか来ないだけ)
    ptr = 0
    dirty = False
    sock.settimeout(1.0)
    while True:
        try:
            try:
                data, _ = sock.recvfrom(4096)
            except socket.timeout:
                if dirty:
                    if KANJI:
                        glyphs = [REV16.get(board[k] * 256 + board[k + 1], "?")
                                  for k in range(0, 128, 2)]
                        rows = ["".join(glyphs[r:r + 16]).rstrip() for r in range(0, 64, 16)]
                    else:
                        rows = ["".join(REV8.get(b, "?") for b in board[r:r + 32]).rstrip()
                                for r in range(0, 128, 32)]
                    while rows and not rows[-1]:
                        rows.pop()
                    print("盤面: [" + "|".join(rows) + "]")
                    dirty = False
                continue
            msgs = []
            parse(data, msgs)
            for addr, args in msgs:
                if "KAT_Pointer" in addr:
                    ptr = int(args[0])
                elif "KAT_CharSync" in addr:
                    i = int(addr.rsplit("Sync", 1)[1])
                    if 1 <= ptr <= 16:
                        board[(ptr - 1) * 8 + i] = _to_byte(args[0])
                        dirty = True
                elif "KAT_Visible" in addr:
                    print(f"KAT_Visible = {args[0]}")
        except KeyboardInterrupt:
            print("終了")
            return

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()
