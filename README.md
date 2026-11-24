# FRB arXiv Daily

arXiv に毎日告知される新着論文のうち、FRB(fast radio burst)に関するものだけを拾い、サブ分野ごとにまとめて表示する自分用サイト。

- **取得**: arXiv の RSS(astro-ph 全体 + gr-qc + hep-ph + physics.plasm-ph)から `new` と `cross` だけを取得する。差し替え版(replace)は除外。
- **FRB判定**: タイトル・アブストに "fast radio burst" / "FRB" / "FRB 2024…" などが含まれるもの。
- **分類**: `config.json` のキーワード重み(タイトル一致は2倍)で11のサブ分野+その他に振り分ける。
  `ANTHROPIC_API_KEY` を設定すると、Claude が分類を見直し、英語と日本語の一行要約も付ける(任意)。表示言語に合わせて切り替わる。
- **更新**: GitHub Actions が平日の毎朝 10:17(台湾時間)に実行し、`docs/data/papers.json` を更新してコミットする。
- **表示**: GitHub Pages で `docs/` を公開する。サイトは英語が基本で、右上のボタンで日本語に切り替えられる(初回はブラウザの言語設定に合わせる)。★・既読・言語の状態はブラウザに保存される(端末ごと)。

## セットアップ

1. GitHub で新しいリポジトリ(例: `frb-arxiv-daily`)を作り、このフォルダの中身を push する。
2. **Settings → Pages**: Source を "Deploy from a branch"、Branch を `main` / `/docs` にする。
   → `https://shotaro-yamasaki.github.io/frb-arxiv-daily/` で見られる。
3. **Settings → Actions → General → Workflow permissions** を "Read and write permissions" にする。
4. 過去分を入れる: **Actions → Update FRB papers → Run workflow** で `backfill_days` に `60` などを入れて実行する。
5. (任意)日本語要約と高精度分類を使う場合: **Settings → Secrets and variables → Actions** で
   Secret `ANTHROPIC_API_KEY` を追加する。モデルを変えたいときは Variable `ANTHROPIC_MODEL` を設定する(既定は `claude-haiku-5-5`)。

## 調整

- サブ分野やキーワードは `config.json` の `subfields` を編集する(`name` が英語名、`name_ja` が日本語名)。色は `docs/index.html` の `COLORS` で変えられる。編集後は Run workflow で `reclassify` にチェックを入れると、保存済みの論文も分類し直される(LLMで分類したものは除く)。
- `watchlist` に入れた語(CHIME、BURSTT、20240114A など)を含む論文は、左端に色の帯が付き、該当語がハイライトされる。

## ローカルで試す

```bash
python scripts/fetch.py --rss-file tests/sample_rss.xml   # テスト用フィードで動作確認
python scripts/fetch.py                                   # 実際の arXiv から取得
cd docs && python -m http.server 8000                     # http://localhost:8000 で表示
```

外部ライブラリは不要(Python 3.9 以上の標準ライブラリのみ)。
