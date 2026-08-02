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

## モデルのサイズを選ぶ目安

- 小さいモデル: 起動と返答が速く、必要なメモリが少ない
- 大きいモデル: 返答の品質が上がることがあるが、起動と返答に時間がかかる

GPUのVRAMに収まらないモデルは、返答が遅くなったり、Ollamaが停止したりすることがあります。まず小さいモデルで動作を確認し、問題がなければ大きいモデルへ変更してください。
