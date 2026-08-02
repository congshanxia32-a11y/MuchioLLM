# トラブルシューティング

症状に近い項目を確認してください。設定画面の上部に警告が出ている場合は、最初にその内容を確認します。

## 文字盤に何も出ない

1. VRChat内のラジアルメニューで **Options → OSC → Enabled** をONにする
2. 直らない場合は、同じ画面の **Reset Config** を実行する
3. アバターに文字盤ギミックが入っているか確認する
4. `run.bat` を起動し直す

VRChatのOSCについては [VRChat公式のOSC概要](https://docs.vrchat.com/docs/osc-overview) を参照してください。

## 声を拾わない

- 設定画面の「耳」カードで音量ゲートを下げる
- `run.bat` の `MIC` と `SPK` に正しいデバイス名を指定する
- `python vrc_listener.py --list` でデバイス名を確認する
- VRChatやVirtual Desktopの音声出力先を確認する

## 返事が遅い

- Ollamaのモデルを小さいものへ変更する
- 設定画面の「かんがえてからはなす」をOFFにする
- VRAMに収まるモデルを選ぶ

## 設定画面が開かない

- 起動直後に数秒待つ
- `run.bat` を一度閉じて、もう一度起動する
- 他のアプリがポート8787を使っていないか確認する
- 先に `setup.bat` を完了させる

## `setup.bat` でOllamaが見つからない

Ollamaをインストールして起動してから、`setup.bat` をもう一度実行してください。PowerShellで次のコマンドが通ることも確認できます。

```powershell
ollama list
```

## なかま・日記が増えない

[VRCX](https://github.com/vrcx-team/VRCX) を起動してから `run.bat` を実行してください。基本的な会話機能にはVRCXは必要ありません。
