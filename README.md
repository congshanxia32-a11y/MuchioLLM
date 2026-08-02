# ムチォLLMコンパニオン

VRCペット「ムチォ」(VRCPet.exe) と、ローカルで動くLLMを連携するツールです。あなたやフレンドの声を聞き取り、ムチォの文字盤に返事を表示します。会話データはこのPCに保存し、クラウドへ送信しません。

## まず必要なもの

- Windows 10/11
- [Python 3.10以上](https://www.python.org/downloads/)。インストール時に **Add python.exe to PATH** を有効にする
- [Ollama](https://ollama.com/download)。インストール後、起動しておく
- 購入済みのムチォ / VRCPet と、文字盤ギミックを設定したアバター
- 任意: [VRCXの配布ページ](https://github.com/vrcx-team/VRCX/releases)。フレンド・ワールド・日記機能に使います

LLMの処理速度はGPUとモデルサイズに左右されます。最初は小さいモデルで動作を確認してください。

## 導入手順

1. このフォルダを、日本語を含まないパスへ置く
2. [Ollamaのモデルを入れる](docs/ollama.md#モデルを入れる)
3. `setup.bat` をダブルクリックし、必要なライブラリをインストールする
4. `run.bat` をダブルクリックする
5. 開いた設定画面 `http://localhost:8787` で、ペットの名前・飼い主の名前・使用モデルを設定して保存する
6. VRChat内で **Options → OSC → Enabled** を有効にし、ペットへ話しかける

`setup.bat` と `run.bat` はメモ帳などで保存し直さないでください。文字コードが変わると起動できなくなることがあります。

## Ollamaのモデル管理

モデルの追加、確認、削除はコマンドで行えます。詳しい手順は [Ollamaの設定とモデル管理](docs/ollama.md) を参照してください。

```powershell
ollama pull qwen3:4b
ollama list
ollama rm qwen3:4b
```

モデルを削除しても、あとで同じ名前を `ollama pull` すれば再取得できます。削除前に `ollama list` で名前を確認してください。

## うまくいかないとき

- 文字盤に出ない: VRChatのOSCが有効か、アバターに文字盤ギミックが入っているか確認する
- 声を拾わない: 設定画面の「耳」カード、または `run.bat` の `MIC` / `SPK` を確認する
- 返事が遅い: 小さいモデルへ変更する
- 設定画面が開かない: 数秒待ち、ポート8787を他のアプリが使っていないか確認する

詳しい対処は [トラブルシューティング](docs/troubleshooting.md) を参照してください。

## 詳しい使い方

- [ふだんの使い方とデータ](docs/usage.md)
- [かんじモード](docs/kanji-mode.md): アバター改造が必要な上級者向け機能
- [Ollamaの設定とモデル管理](docs/ollama.md)
- [トラブルシューティング](docs/troubleshooting.md)
- [開発者向けメモ](DEVELOPING.md)

## 配布上の注意

この配布物に `VRCPet.exe`、ムチォ本体のモデル、テクスチャ、プレハブ、改変済みアバターデータは含まれません。購入者本人が自分のUnityプロジェクトへ導入し、パッチ適用後のアバターやプロジェクトを第三者へ配布しないでください。

本ツールは非公式です。詳しい条件は [LICENSE.md](LICENSE.md) を確認してください。

## 関連リンク

- [Ollamaモデルライブラリ](https://ollama.com/library)
- [VRCXの配布ページ](https://github.com/vrcx-team/VRCX/releases)
- [VRChat公式ドキュメント](https://docs.vrchat.com/)
- [VRChat OSC概要](https://docs.vrchat.com/docs/osc-overview)
