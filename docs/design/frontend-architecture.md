# 設計ドキュメント: Frontend Architecture (Next.js + pnpm)

## 概要

早稲田大学シラバス MCP サーバーのフロントエンドアーキテクチャ。
Next.js で構築したシラバス検索 UI を提供し、バックエンドの FastAPI に直接リクエストする。

## 目標

- **主要な目標**
  - シラバス検索・詳細閲覧ができる UI を提供する
  - FastAPI (`packages/api`) を直接呼び出してデータを取得する
  - pnpm で依存関係を管理する

- **非目標**
  - API Route によるバックエンド中継（FastAPI が直接 API を提供するため不要）
  - 認証・ユーザー管理（シラバスは公開情報のため不要）
  - バックエンドアーキテクチャの設計（[backend-architecture.md](./backend-architecture.md) で扱う）

## 背景

バックエンドは FastAPI (`apps/backend/packages/api`) で HTTP API を提供する設計が決まっている。
フロントエンドはそこに直接リクエストするだけでよく、Next.js の API Route による BFF 層は不要。

シラバス情報は公開情報のため、認証トークン隠蔽などの BFF 的な要件も発生しない。

## 設計

### ディレクトリ構造

```
waseda-syllabus-mcp/
├── apps/
│   ├── backend/          # uv workspace (既存)
│   └── frontend/         # Next.js アプリ
│       ├── package.json
│       ├── pnpm-lock.yaml
│       ├── next.config.ts
│       ├── tsconfig.json
│       └── src/
│           ├── app/              # App Router
│           │   ├── layout.tsx
│           │   ├── page.tsx           # トップ / 検索画面
│           │   └── courses/
│           │       └── [id]/
│           │           └── page.tsx   # コース詳細画面
│           ├── components/       # UI コンポーネント
│           │   ├── search/
│           │   │   ├── SearchForm.tsx
│           │   │   └── SearchResults.tsx
│           │   └── course/
│           │       └── CourseDetail.tsx
│           ├── lib/
│           │   └── api.ts        # FastAPI クライアント
│           └── types/
│               └── course.ts     # 型定義
└── docs/
```

### アーキテクチャ

データフロー:

```
ブラウザ
    ↓ RSC / Server Actions
Next.js (apps/frontend)
    ↓ HTTP (fetch)
FastAPI (apps/backend/packages/api)
    ↓
PostgreSQL
```

Next.js の Server Components から直接 FastAPI を呼び出す。
クライアントコンポーネントが必要な箇所（検索フォームの入力など）は最小限に留める。

### API クライアント

`src/lib/api.ts` に FastAPI の呼び出しをまとめる。

```typescript
const API_BASE = process.env.API_URL ?? 'http://localhost:8000';

export async function searchCourses(query: string) {
  const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error('Search failed');
  return res.json();
}

export async function getCourse(id: string) {
  const res = await fetch(`${API_BASE}/courses/${id}`);
  if (!res.ok) throw new Error('Course not found');
  return res.json();
}
```

### 依存関係

```json
{
  "dependencies": {
    "next": "^15",
    "react": "^19",
    "react-dom": "^19"
  },
  "devDependencies": {
    "typescript": "^5",
    "@types/react": "^19",
    "@types/node": "^22"
  }
}
```

UIライブラリは実装フェーズで決定する（shadcn/ui + Tailwind CSS が候補）。

### 環境変数

| 変数名 | 説明 | デフォルト |
|---|---|---|
| `API_URL` | FastAPI のベース URL | `http://localhost:8000` |

`.env.local` で管理し、本番は環境変数として注入する。

## 検討した代替案

| 案 | 採用しなかった理由 |
|---|---|
| API Route (BFF) | FastAPI が直接 API を提供するため不要。レイヤーを増やすだけ |
| npm / yarn | pnpm の方が高速でディスク効率が良い |
| SPA (Vite + React) | SSR による初期表示速度・SEO の恩恵を受けたい |
| Remix | Next.js の方がエコシステムが大きく情報が多い |

## 未解決の質問

- [ ] UIライブラリの選定（shadcn/ui + Tailwind CSS か、他か）
- [ ] FastAPI の CORS 設定（開発時は `localhost:3000` を許可する必要あり）
- [ ] 本番デプロイ先（Vercel、Cloudflare Pages など）

## テスト戦略

- **Unit テスト**: コンポーネント単体（Vitest + React Testing Library）
- **E2E テスト**: 検索フロー全体（Playwright）

## 参考資料

- [Next.js App Router 公式ドキュメント](https://nextjs.org/docs/app)
- [pnpm 公式ドキュメント](https://pnpm.io/)
- [backend-architecture.md](./backend-architecture.md) - FastAPI の API エンドポイント設計
