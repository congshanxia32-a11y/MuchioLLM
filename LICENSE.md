# License

This repository is a companion tool and optional Unity Editor extension for the VRChat pet "Muchio".
It does not grant any rights to redistribute Muchio itself.

## Project Code

Unless a file says otherwise, the MuchioLLM Python code, web UI, batch launchers, tests, and project
documentation are released under the MIT License.

Copyright (c) 2026 MuchioLLM contributors

SPDX-License-Identifier: MIT

## Muchio Kanji Mod

`MuchioKanjiMod.unitypackage` is a patcher-style Unity package. It is intended to be distributed
without any original Muchio model, texture, prefab, VRCPet executable, or modified Muchio asset.
Users must import their own purchased copy of Muchio and apply the patch locally.

The package's own C# editor scripts, generated animation/controller assets, prefab wrapper, and
documentation are MIT-licensed unless noted below.

## Third-Party Material

KillFrenzy Avatar Text (KAT)

- Used by: the modified KAT-compatible shader and generated KAT animation assets in the Kanji Mod.
- Upstream: https://github.com/killfrenzy96/KillFrenzyAvatarText
- License: MIT
- Copyright: 2023 KillFrenzy / Evan Tran
- Required notice: the upstream copyright and MIT permission notice must be preserved in copies or
  substantial portions of KAT-derived material.

BIZ UDGothic glyph atlas

- Used by: `Assets/MuchioKanji/Textures/KAT_KanjiTiles.png` inside the Unity package.
- Upstream: https://github.com/googlefonts/morisawa-biz-ud-gothic
- License: SIL Open Font License 1.1
- Copyright: 2022 The BIZ UDGothic Project Authors
- Note: the package does not include `.ttf` or `.otf` font files. The PNG is a rasterized glyph atlas
  used as a bitmap font texture, so it should be kept documented as BIZ UDGothic/OFL-derived material
  rather than treated as a purely MIT-licensed original image.

Runtime dependencies

- Python packages installed from `requirements.txt`, optional GPU/speaker-identification packages,
  Ollama models, VRCX, VRCFury, VRChat SDK, Modular Avatar, Unity, and VRCPet are not part of this
  repository's license grant. They remain under their own licenses and terms.

## Muchio Terms Boundary

Muchio and VRCPet are copyrighted works by their original author/distributor. The checked BOOTH page
and local `利用規約.txt` allow personal VRChat use and modification, but prohibit redistribution,
resale, transfer, distribution/sale of modified data, and making the product data available for third
parties to download.

Do not distribute:

- `VRCPet.exe`
- the original Muchio unitypackage
- Muchio models, textures, prefabs, animations, or app files
- patched avatars, Unity projects, or packages that contain Muchio product data

You may distribute this companion tool and the standalone Kanji Mod patcher package only while keeping
that boundary intact.

## No Endorsement

This project is unofficial and is not endorsed by IWANUGA, BOOTH, VRChat, KillFrenzy, Morisawa, Google,
VRCFury, or any other third-party project named here.
