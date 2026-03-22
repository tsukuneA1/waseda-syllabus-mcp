# Frontend CLAUDE.md

Next.js (App Router) + pnpm。FastAPI (`apps/backend/packages/api`) に直接リクエストする。BFF 層なし。

## コマンド

```bash
# 依存関係インストール
pnpm install

# 開発サーバー起動
pnpm dev

# ビルド
pnpm build
```

## 環境変数

`.env.local` を作成:
```
API_URL=http://localhost:8000
```

## ディレクトリ構成

```
src/
├── app/              # App Router
│   ├── page.tsx      # 検索画面
│   └── courses/[id]/ # コース詳細
├── components/
│   ├── search/       # SearchForm, SearchResults
│   └── course/       # CourseDetail
├── lib/api.ts        # FastAPI クライアント
└── types/course.ts   # 型定義
```

## 注意事項

- API Route による BFF 不要。`lib/api.ts` から FastAPI に直接 fetch
- 設計詳細: `docs/design/frontend-architecture.md`
