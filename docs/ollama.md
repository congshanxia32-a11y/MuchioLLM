# Ollamaの設定とモデル管理

このページでは、MuchioLLMが使うOllamaの導入、モデルの追加、モデルの切り替え、削除を説明します。

## Ollamaをインストールする

1. [Ollamaのダウンロードページ](https://ollama.com/download) を開く
2. Windows版をインストールする
3. Ollamaを起動する
4. PowerShellで次のコマンドを実行し、バージョンが表示されることを確認する

```powershell
ollama --version
```

MuchioLLMは、起動中のOllamaへ `http://localhost:11434` で接続します。

## モデルを入れる

Ollamaでは、モデルをダウンロードする操作を `pull` と呼びます。

1. [Ollamaモデルライブラリ](https://ollama.com/library) からモデルを選ぶ
2. モデルページに表示された名前を確認する
3. PowerShellで `ollama pull モデル名` を実行する

例として、Qwen3の4Bモデルを追加します。

```powershell
ollama pull qwen3:4b
```

ダウンロード済みのモデルは次のコマンドで確認できます。

```powershell
ollama list
```

`setup.bat` の途中でも、`config.json` に設定されたモデルをダウンロードできます。サイズが大きいモデルは時間とディスク容量が必要なので、最初は小さいモデルを選んでください。

## MuchioLLMでモデルを選ぶ

1. `run.bat` を起動する
2. `http://localhost:8787` を開く
3. 「あたま(LLM)」カードを開く
4. Ollamaに入っているモデルを選ぶ
5. 保存する

一覧にモデルが出ないときは、Ollamaが起動していることと、`ollama list` にモデルが表示されることを確認してください。

## モデルを削除する

モデル名を確認してから `rm` を実行します。モデル本体、設定、メタデータがPCから削除されます。

```powershell
ollama list
ollama rm qwen3:4b
ollama list
```

複数のモデルをまとめて削除することもできます。

```powershell
ollama rm qwen3:4b llama3.2:3b
```

削除したモデルを使いたくなったら、同じ名前で再度 `ollama pull` を実行してください。削除前に残したいモデル名を確認してください。

## PCのスペックに合うモデルを選ぶ

VRAMはGPUのメモリ、RAMはPC全体のメモリです。次の表は、MuchioLLM・VRChat・音声認識を同時に動かす場合の安全寄りの目安です。

| PCの目安 | まず試すモデル | 向いている使い方 |
|---|---|---|
| GPUなし / RAM 8 GB以上 | `qwen3:0.6b`、`qwen3.5:0.8b` | 動作確認、短い返事 |
| VRAM 4 GB / RAM 16 GB以上 | `qwen3:4b`、`qwen3.5:4b`、`gemma3:4b` | 普段使いの入門 |
| VRAM 8 GB / RAM 16 GB以上 | `qwen3:8b`、`qwen3.5:9b` | 返事の自然さと速度のバランス |
| VRAM 12 GB以上 / RAM 32 GB以上 | `qwen3:14b`、`gemma3:12b` | 品質を優先した普段使い |
| VRAM 24 GB以上 / RAM 32 GB以上 | `qwen3:30b`、`qwen3.5:35b` | 品質を優先。起動は遅め |

モデルページに表示されるサイズは、ダウンロードするファイルの大きさです。実行時は会話の長さ、コンテキストサイズ、Ollama以外のアプリでもメモリを使います。表示サイズと同じ容量のVRAMだけでは足りないことがあるため、表では余裕を持たせています。

### モデルごとのサイズ

Ollamaのモデルページに表示される代表的なサイズは次のとおりです。タグや量子化方式が変わるとサイズも変わるので、ダウンロード前に各ページを確認してください。

| モデル | Ollama上のサイズ | 日本語会話での目安 |
|---|---:|---|
| [`qwen3:0.6b`](https://ollama.com/library/qwen3) | 523 MB | 最小構成。返答の品質は控えめ |
| [`qwen3:4b`](https://ollama.com/library/qwen3) | 2.5 GB | 4 GB級GPUの第一候補 |
| [`qwen3:8b`](https://ollama.com/library/qwen3) | 5.2 GB | 8 GB級GPUの第一候補 |
| [`qwen3:14b`](https://ollama.com/library/qwen3) | 9.3 GB | 12 GB以上で品質重視 |
| [`qwen3:30b`](https://ollama.com/library/qwen3) | 19 GB | 24 GB以上で品質重視 |
| [`qwen3.5:4b`](https://ollama.com/library/qwen3.5) | 3.4 GB | 4 GB級GPUの候補。画像入力にも対応 |
| [`qwen3.5:9b`](https://ollama.com/library/qwen3.5) | 6.6 GB | 8 GB級GPUの候補。画像入力にも対応 |
| [`qwen3.5:35b`](https://ollama.com/library/qwen3.5) | 24 GB | 24 GB以上で品質重視。画像入力にも対応 |
| [`gemma3:4b`](https://ollama.com/library/gemma3) | 3.3 GB | 4 GB級GPUの候補。画像入力にも対応 |
| [`gemma3:12b`](https://ollama.com/library/gemma3) | 8.1 GB | 12 GB以上で品質重視。画像入力にも対応 |

### 選び方の手順

1. まずPCのGPUのVRAM容量とRAM容量を確認する
2. 表の自分の行からモデルを1つ選ぶ
3. `ollama pull モデル名` で入れる
4. MuchioLLMの設定画面でモデルを選ぶ
5. 返事が遅い、Ollamaが停止する、VRChatが重い場合は1段階小さいモデルへ変更する

OllamaがモデルをGPUに載せきれない場合は、RAMへ分割して動かすことがあります。その場合も動作はしますが、返答が大幅に遅くなることがあります。音声認識にGPUを使う場合は、LLM用に使えるVRAMがさらに減るため、表より小さいモデルを選んでください。

Qwen3は日本語を含む多言語の会話に向いています。画像入力も使いたい場合は、[`qwen3.5`](https://ollama.com/library/qwen3.5) または [`gemma3`](https://ollama.com/library/gemma3) を選んでください。
