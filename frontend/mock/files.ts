import type { MockMethod } from 'vite-plugin-mock'

const MOCK_FILES: Record<string, string> = {
  '/workspace/src/main.py': `import uvicorn
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
`,
  '/workspace/src/index.html': `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>My App</title>
</head>
<body>
  <h1>Hello from index.html</h1>
</body>
</html>
`,
  '/workspace/src/data_export.json': `{
  "quarter": "Q4",
  "revenue": 520000,
  "growth": 0.15,
  "top_products": [
    { "name": "Product A", "revenue": 180000 },
    { "name": "Product B", "revenue": 140000 },
    { "name": "Product C", "revenue": 200000 }
  ]
}
`,
}

export default [
  {
    url: '/api/v1/files/content',
    method: 'get',
    response: ({ query }: { query: { filePath?: string } }) => {
      const filePath = query.filePath ?? ''
      const content = MOCK_FILES[filePath] ?? `# Mock content for: ${filePath}\nprint("hello world")\n`
      return { code: 200, message: 'ok', data: { content } }
    },
  },
  {
    url: '/api/v1/files/content',
    method: 'put',
    response: ({ body }: { body: { filePath: string; content: string } }) => {
      if (body.filePath) {
        MOCK_FILES[body.filePath] = body.content
      }
      return { code: 200, message: 'ok', data: { success: true } }
    },
  },
] as MockMethod[]
