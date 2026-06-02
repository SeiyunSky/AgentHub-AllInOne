import type { MockMethod } from 'vite-plugin-mock'
import type { IncomingMessage, ServerResponse } from 'http'

// Shared abort state: stop endpoint sets it, SSE handler checks it
const abortedConversations = new Set<string>()

function sendSSE(res: ServerResponse, event: string, data: unknown) {
  res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
}

async function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms))
}

// Delay that checks for abort; returns true if conversation was aborted
async function delayWithAbortCheck(ms: number, convId: string, res: ServerResponse): Promise<boolean> {
  const start = Date.now()
  while (Date.now() - start < ms) {
    if (abortedConversations.has(convId)) {
      // Send stop sequence: agent_error → round_done → queue_drained
      const now = () => new Date().toISOString()
      const agentId = 'orchestrator'
      const threadId = 'thread-mock'

      sendSSE(res, 'agent_error', {
        type: 'agent_error',
        agent_id: agentId,
        thread_id: threadId,
        message_id: `msg-ssse-${Date.now()}`,
        error: 'cancelled',
        timestamp: now(),
      })
      await delay(50)

      sendSSE(res, 'round_done', {
        type: 'round_done',
        timestamp: now(),
      })
      await delay(50)

      sendSSE(res, 'queue_drained', {
        type: 'queue_drained',
        timestamp: now(),
      })

      abortedConversations.delete(convId)
      res.end()
      return true
    }
    await delay(20)
  }
  return false
}

function splitChunks(text: string, size: number): string[] {
  const chunks: string[] = []
  for (let i = 0; i < text.length; i += size) {
    chunks.push(text.slice(i, i + size))
  }
  return chunks
}

const conversations = [
  {
    id: 'conv-1',
    user_id: 'default',
    title: 'Q4 Sales Analysis',
    mode: 'group',
    is_pinned: true,
    is_archived: false,
    last_message_preview: '以上是完整的 Markdown 渲染效果演示。',
    last_message_at: '2026-05-26T09:31:00Z',
    message_count: 16,
    unread_count: 2,
    created_at: '2026-05-26T09:00:00Z',
    updated_at: '2026-05-26T10:00:00Z',
    agents: [
      { id: 'orchestrator', name: 'Orchestrator', type: 'claude', description: 'Primary orchestration agent' },
      { id: 'data-analyst', name: 'Data Analyst', type: 'codex', description: 'Data analysis and visualizations' },
      { id: 'report-generator', name: 'Report Generator', type: 'claude', description: 'Report generation' },
    ],
  },
  {
    id: 'conv-2',
    user_id: 'default',
    title: 'Code Review',
    mode: 'single',
    is_pinned: false,
    is_archived: false,
    last_message_preview: 'Found 3 issues in the PR.',
    last_message_at: '2026-05-25T16:30:00Z',
    message_count: 8,
    unread_count: 0,
    created_at: '2026-05-25T15:00:00Z',
    updated_at: '2026-05-25T16:30:00Z',
    agents: [
      { id: 'code-reviewer', name: 'Code Reviewer', type: 'claude', description: 'Code review and quality' },
    ],
  },
]

const messages = [
  {
    id: 'msg-1',
    conversation_id: 'conv-1',
    thread_id: null,
    parent_id: null,
    user_id: 'default',
    agent_id: null,
    role: 'user',
    blocks: [{ block_id: 'b1', type: 'text', content: 'Can you help me process the Q4 sales data and generate a report?' }],
    status: 'done',
    error_message: null,
    model: null,
    sender: null,
    tokens_input: null,
    tokens_output: null,
    latency_ms: null,
    feedback: null,
    selected_range: null,
    is_deleted: false,
    created_at: '2026-05-26T09:05:00Z',
  },
  // msg-2: thinking + text + tool_use (completed)
  {
    id: 'msg-2',
    conversation_id: 'conv-1',
    thread_id: 'thread-1',
    parent_id: null,
    user_id: null,
    agent_id: 'orchestrator',
    role: 'assistant',
    blocks: [
      { block_id: 'b2', type: 'thinking', content: 'The user wants to process Q4 sales data. I should dispatch to Data Analyst first, then coordinate report generation.', duration_ms: 2500 },
      { block_id: 'b3', type: 'text', content: "I'll analyze the sales data and coordinate with the team." },
      { block_id: 'b4', type: 'tool_use', tool_name: 'dispatch_agent', input: { agent: 'data-analyst', task: 'load_csv' }, output: 'Agent dispatched successfully', status: 'completed' },
    ],
    status: 'done',
    error_message: null,
    model: 'claude-sonnet-4-6',
    sender: 'Orchestrator',
    tokens_input: 150,
    tokens_output: 80,
    latency_ms: 3200,
    feedback: null,
    selected_range: null,
    is_deleted: false,
    created_at: '2026-05-26T09:06:00Z',
  },
  // msg-3: text + code (with diff)
  {
    id: 'msg-3',
    conversation_id: 'conv-1',
    thread_id: 'thread-2',
    parent_id: null,
    user_id: null,
    agent_id: 'data-analyst',
    role: 'assistant',
    blocks: [
      { block_id: 'b5', type: 'text', content: 'Found 3 CSV files. Processing records...' },
      { block_id: 'b6', type: 'tool_use', tool_name: 'read_file', input: { path: 'sales_q4.csv' }, output: 'Read 1,247 rows', status: 'completed' },
      { block_id: 'b7', type: 'code', language: 'python', code: 'import pandas as pd\n\ndef load_data():\n    df = pd.read_csv("sales_q4.csv")\n    return df.to_dict("records")', filename: 'process_sales.py', old_code: 'import pandas as pd\n\ndef load_data():\n    pass', additions: 3, deletions: 1 },
    ],
    status: 'done',
    error_message: null,
    model: 'codex',
    sender: 'Data Analyst',
    tokens_input: 200,
    tokens_output: 120,
    latency_ms: 4500,
    feedback: 'up',
    selected_range: null,
    is_deleted: false,
    created_at: '2026-05-26T09:10:00Z',
  },
  // msg-3b: clean code block (no diff)
  {
    id: 'msg-3b',
    conversation_id: 'conv-1',
    thread_id: 'thread-2',
    parent_id: null,
    user_id: null,
    agent_id: 'data-analyst',
    role: 'assistant',
    blocks: [
      { block_id: 'b5b', type: 'text', content: 'Here is the data cleaning script I wrote for the pipeline:' },
      { block_id: 'b5c', type: 'code', language: 'python', code: 'import pandas as pd\nimport numpy as np\nfrom pathlib import Path\n\n\ndef clean_sales_data(df: pd.DataFrame) -> pd.DataFrame:\n    """Remove duplicates, fill nulls, normalize columns."""\n    df = df.drop_duplicates(subset=["order_id"])\n    df["revenue"] = df["revenue"].fillna(0)\n    df["date"] = pd.to_datetime(df["date"], errors="coerce")\n    return df.sort_values("date").reset_index(drop=True)\n\n\ndef main():\n    raw = pd.read_csv("sales_q4.csv")\n    clean = clean_sales_data(raw)\n    clean.to_parquet("sales_q4_clean.parquet", index=False)\n    print(f"Cleaned {len(clean)} rows")\n\n\nif __name__ == "__main__":\n    main()', filename: 'clean_pipeline.py' },
    ],
    status: 'done',
    error_message: null,
    model: 'codex',
    sender: 'Data Analyst',
    tokens_input: 180,
    tokens_output: 95,
    latency_ms: 3200,
    feedback: null,
    selected_range: null,
    is_deleted: false,
    created_at: '2026-05-26T09:12:00Z',
  },
  // msg-4: user asks for visualization
  {
    id: 'msg-4',
    conversation_id: 'conv-1',
    thread_id: null,
    parent_id: null,
    user_id: 'default',
    agent_id: null,
    role: 'user',
    blocks: [{ block_id: 'b8', type: 'text', content: 'Can you generate a revenue chart and deploy a preview?' }],
    status: 'done',
    error_message: null,
    model: null,
    sender: null,
    tokens_input: null,
    tokens_output: null,
    latency_ms: null,
    feedback: null,
    selected_range: null,
    is_deleted: false,
    created_at: '2026-05-26T09:15:00Z',
  },
  // msg-5: image block
  {
    id: 'msg-5',
    conversation_id: 'conv-1',
    thread_id: 'thread-3',
    parent_id: null,
    user_id: null,
    agent_id: 'data-analyst',
    role: 'assistant',
    blocks: [
      { block_id: 'b9', type: 'text', content: 'Here is the Q4 revenue chart:' },
      { block_id: 'b10', type: 'image', src: 'https://quickchart.io/chart?c={type:"bar",data:{labels:["Q1","Q2","Q3","Q4"],datasets:[{label:"Revenue ($K)",data:[320,410,380,520]}]}}', alt: 'Q4 Revenue Bar Chart', caption: 'Quarterly Revenue Comparison' },
    ],
    status: 'done',
    error_message: null,
    model: 'codex',
    sender: 'Data Analyst',
    tokens_input: 180,
    tokens_output: 90,
    latency_ms: 2800,
    feedback: null,
    selected_range: null,
    is_deleted: false,
    created_at: '2026-05-26T09:18:00Z',
  },
  // msg-6: deployment block (completed)
  {
    id: 'msg-6',
    conversation_id: 'conv-1',
    thread_id: 'thread-4',
    parent_id: null,
    user_id: null,
    agent_id: 'orchestrator',
    role: 'assistant',
    blocks: [
      { block_id: 'b11', type: 'text', content: 'Deploying the dashboard to preview...' },
      { block_id: 'b12', type: 'deployment', title: 'Dashboard Preview', status: 'completed', url: 'https://preview.example.com/reports/q4-sales', logs: 'Build completed in 2.3s\nDeployed to https://preview.example.com/reports/q4-sales', progress: 100 },
    ],
    status: 'done',
    error_message: null,
    model: 'claude-sonnet-4-6',
    sender: 'Orchestrator',
    tokens_input: 120,
    tokens_output: 60,
    latency_ms: 2100,
    feedback: null,
    selected_range: null,
    is_deleted: false,
    created_at: '2026-05-26T09:22:00Z',
  },
  // msg-7: artifacts block
  {
    id: 'msg-7',
    conversation_id: 'conv-1',
    thread_id: 'thread-5',
    parent_id: null,
    user_id: null,
    agent_id: 'report-generator',
    role: 'assistant',
    blocks: [
      { block_id: 'b13', type: 'text', content: 'Report generated. Here are the output files:' },
      {
        block_id: 'b14',
        type: 'artifacts',
        title: 'Q4 Sales Report',
        items: [
          { name: 'sales_dashboard.html', type: 'html', preview: '<!DOCTYPE html>\n<html><head><title>Dashboard</title></head>\n<body><h1>Q4 Revenue: $520K (+15%)</h1></body></html>', filePath: '/workspace/src/index.html' },
          { name: 'report.pdf', type: 'pdf' },
          { name: 'data_export.json', type: 'json', filePath: '/workspace/src/data_export.json' },
        ],
      },
    ],
    status: 'done',
    error_message: null,
    model: 'claude-sonnet-4-6',
    sender: 'Report Generator',
    tokens_input: 300,
    tokens_output: 150,
    latency_ms: 5600,
    feedback: null,
    selected_range: null,
    is_deleted: false,
    created_at: '2026-05-26T09:25:00Z',
  },
  // msg-8: approval block (already approved in history)
  {
    id: 'msg-8',
    conversation_id: 'conv-1',
    thread_id: 'thread-6',
    parent_id: null,
    user_id: null,
    agent_id: 'orchestrator',
    role: 'assistant',
    blocks: [
      { block_id: 'b15', type: 'text', content: 'I need to run a database migration. Requesting approval.' },
      { block_id: 'b16', type: 'approval', action: 'run_command', detail: 'alembic upgrade head --sql | psql sales_db', status: 'approved', decided_at: '2026-05-26T09:28:00Z' },
      { block_id: 'b17', type: 'tool_use', tool_name: 'run_command', input: { command: 'alembic upgrade head' }, output: 'Migration applied: 3 tables updated', status: 'completed' },
    ],
    status: 'done',
    error_message: null,
    model: 'claude-sonnet-4-6',
    sender: 'Orchestrator',
    tokens_input: 100,
    tokens_output: 70,
    latency_ms: 1800,
    feedback: null,
    selected_range: null,
    is_deleted: false,
    created_at: '2026-05-26T09:27:00Z',
  },
  // msg-9: user asks for markdown demo
  {
    id: 'msg-9',
    conversation_id: 'conv-1',
    thread_id: null,
    parent_id: null,
    user_id: 'default',
    agent_id: null,
    role: 'user',
    blocks: [{ block_id: 'b18', type: 'text', content: '给我展示一份完整的 Markdown 渲染效果，包括标题、列表、表格、代码块和引用' }],
    status: 'done',
    error_message: null,
    model: null,
    sender: null,
    tokens_input: null,
    tokens_output: null,
    latency_ms: null,
    feedback: null,
    selected_range: null,
    is_deleted: false,
    created_at: '2026-05-26T09:30:00Z',
  },
  // msg-10: agent responds with rich markdown — heading, lists, table, blockquote, code blocks
  {
    id: 'msg-10',
    conversation_id: 'conv-1',
    thread_id: 'thread-7',
    parent_id: null,
    user_id: null,
    agent_id: 'orchestrator',
    role: 'assistant',
    blocks: [
      {
        block_id: 'b19',
        type: 'text',
        content: `## Markdown 渲染效果演示

以下是各种 Markdown 元素的渲染效果：

### 文本格式

支持 **粗体**、*斜体*、~~删除线~~ 和 \`行内代码\` 等基本格式。

### 有序列表

1. 第一项：安装依赖
2. 第二项：配置环境变量
3. 第三项：启动开发服务器

### 无序列表

- 支持多种编程语言高亮
  - Python
  - TypeScript / JavaScript
  - Go
  - Rust
- 自动检测语言并应用对应主题
- 行号显示 & 一键复制

### 引用

> **提示：** 代码块支持语法高亮，使用的是 \`shiki\` 引擎，基于 VSCode 的 TextMate 语法，支持 100+ 语言。

### 表格

| 语言 | 文件扩展名 | 类型系统 | 运行方式 |
|------|-----------|---------|---------|
| Python | \`.py\` | 动态类型 | 解释执行 |
| TypeScript | \`.ts\` | 静态类型 | 编译为 JS |
| Go | \`.go\` | 静态类型 | 编译执行 |
| Rust | \`.rs\` | 静态类型 | 编译执行 |

### Python 代码示例

\`\`\`python
import pandas as pd
from typing import Optional

def load_sales_data(path: str, sheet: Optional[str] = None) -> pd.DataFrame:
    """Load sales data from Excel or CSV file."""
    if path.endswith('.xlsx'):
        return pd.read_excel(path, sheet_name=sheet or 0)
    return pd.read_csv(path)

def summarize(df: pd.DataFrame) -> dict:
    """Return summary statistics."""
    return {
        "total_revenue": df["revenue"].sum(),
        "avg_order_value": df["revenue"].mean(),
        "top_product": df.groupby("product")["revenue"].sum().idxmax(),
    }
\`\`\`

### TypeScript 代码示例

\`\`\`typescript
interface ApiResponse<T> {
  data: T
  status: number
  message: string
}

async function fetchWithRetry<T>(
  url: string,
  retries: number = 3
): Promise<ApiResponse<T>> {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(url)
      if (!res.ok) throw new Error(\`HTTP \${res.status}\`)
      return await res.json()
    } catch (err) {
      if (i === retries - 1) throw err
      await new Promise((r) => setTimeout(r, 1000 * (i + 1)))
    }
  }
  throw new Error("Unreachable")
}
\`\`\`

### SQL 查询示例

\`\`\`sql
SELECT
  p.name AS product_name,
  SUM(oi.quantity) AS total_sold,
  SUM(oi.quantity * oi.unit_price) AS revenue
FROM order_items oi
JOIN products p ON p.id = oi.product_id
JOIN orders o ON o.id = oi.order_id
WHERE o.created_at >= '2026-01-01'
GROUP BY p.name
HAVING SUM(oi.quantity * oi.unit_price) > 10000
ORDER BY revenue DESC
LIMIT 10;
\`\`\`

### Shell 命令示例

\`\`\`bash
#!/bin/bash
set -euo pipefail

echo "Deploying to production..."
docker build -t myapp:latest .
docker push registry.example.com/myapp:latest

kubectl set image deployment/myapp \\
  myapp=registry.example.com/myapp:latest \\
  --namespace production

kubectl rollout status deployment/myapp -n production
echo "Deploy complete!"
\`\`\`

---

*以上是完整的 Markdown 渲染效果演示。*`,
      },
    ],
    status: 'done',
    error_message: null,
    model: 'claude-sonnet-4-6',
    sender: 'Orchestrator',
    tokens_input: 450,
    tokens_output: 680,
    latency_ms: 4200,
    feedback: null,
    selected_range: null,
    is_deleted: false,
    created_at: '2026-05-26T09:31:00Z',
  },
]

const mockList = [
  // Chat
  {
    url: '/api/v1/chat',
    method: 'post',
    response: ({ body }: { body: { conversation_id: string } }) => ({
      status: 'started',
      conversation_id: body.conversation_id,
      user_message_id: `msg-${Date.now()}`,
    }),
  },
  {
    url: '/api/v1/chat/stop',
    method: 'post',
    response: ({ body }: { body: { conversation_id: string } }) => {
      abortedConversations.add(body.conversation_id)
      return {
        conversation_id: body.conversation_id,
        aborted: true,
        cancelled_thread_ids: [],
        timestamp: new Date().toISOString(),
      }
    },
  },

  // Conversations
  {
    url: '/api/v1/conversations',
    method: 'post',
    response: ({ body }: { body: { title: string; mode: string; agent_ids: string[] } }) => ({
      id: `conv-${Date.now()}`,
      user_id: 'default',
      title: body.title,
      mode: body.mode,
      is_pinned: false,
      is_archived: false,
      last_message_preview: null,
      last_message_at: null,
      message_count: 0,
      unread_count: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      agents: body.agent_ids.map((id) => ({ id, name: id, type: 'claude' })),
    }),
  },
  {
    url: '/api/v1/conversations',
    method: 'get',
    response: () => conversations,
  },
  {
    url: '/api/v1/conversations/:id',
    method: 'get',
    response: ({ query }: { query: { id: string } }) => {
      const conv = conversations.find((c) => c.id === query.id)
      return conv || { statusCode: 404, status: 404, message: 'Not found' }
    },
  },
  {
    url: '/api/v1/conversations/:id',
    method: 'patch',
    response: ({ query, body }: { query: { id: string }; body: Record<string, unknown> }) => {
      const conv = conversations.find((c) => c.id === query.id)
      if (!conv) return { statusCode: 404, status: 404, message: 'Not found' }
      return { ...conv, ...body, updated_at: new Date().toISOString() }
    },
  },

  // Messages
  {
    url: '/api/v1/messages/:id',
    method: 'get',
    response: ({ query }: { query: { id: string } }) => {
      const msg = messages.find((m) => m.id === query.id)
      return msg || { statusCode: 404, status: 404, message: 'Message not found' }
    },
  },
  {
    url: '/api/v1/conversations/:id/messages',
    method: 'get',
    response: ({ query }: { query: { id: string } }) => {
      return messages.filter((m) => m.conversation_id === query.id)
    },
  },
  {
    url: '/api/v1/messages/:id/feedback',
    method: 'patch',
    response: () => ({ success: true }),
  },

  // Approval
  {
    url: '/api/v1/approvals/:messageId/:blockId/approve',
    method: 'post',
    response: () => ({ status: 'approved', decided_at: new Date().toISOString() }),
  },
  {
    url: '/api/v1/approvals/:messageId/:blockId/reject',
    method: 'post',
    response: ({ body }: { body: { reason?: string } }) => ({
      status: 'rejected',
      reject_reason: body.reason ?? null,
      decided_at: new Date().toISOString(),
    }),
  },

  // Agents
  {
    url: '/api/v1/agents',
    method: 'get',
    response: () => [
      {
        id: 'orchestrator',
        user_id: 'GUGA',
        name: 'Orchestrator',
        description: 'Primary orchestration agent',
        type: 'claude',
        capabilities: { supports_code: true, supports_diff: true, supports_approval: true, supports_image: false },
        tags: ['core', 'orchestration'],
        is_public: true,
        is_active: true,
        skill_ids: [],
        created_at: '2026-05-01T00:00:00Z',
        updated_at: '2026-05-01T00:00:00Z',
      },
      {
        id: 'agent-research-builtin',
        user_id: 'GUGA',
        name: '调研 Agent',
        description: '专业信息收集与结构化报告输出，适合市场调研、技术选型、资料汇总等任务',
        type: 'claude',
        capabilities: {},
        tags: [],
        is_public: true,
        is_active: true,
        skill_ids: [],
        created_at: '2026-05-01T00:00:00Z',
        updated_at: '2026-05-01T00:00:00Z',
      },
      {
        id: 'data-analyst',
        user_id: 'default',
        name: 'Data Analyst',
        description: 'Analyzes data and generates insights',
        type: 'codex',
        capabilities: { supports_code: true, supports_diff: false, supports_approval: false, supports_image: true },
        tags: ['data', 'analysis'],
        is_public: true,
        is_active: true,
        skill_ids: [],
        created_at: '2026-05-10T00:00:00Z',
        updated_at: '2026-05-10T00:00:00Z',
      },
    ],
  },
  {
    url: '/api/v1/agents',
    method: 'post',
    response: ({ body }: { body: { name: string; description?: string; type: string; capabilities?: Record<string, boolean>; tags?: string[]; skill_ids?: string[] } }) => ({
      id: `agent-${Date.now()}`,
      user_id: 'default',
      name: body.name,
      description: body.description ?? '',
      type: body.type,
      capabilities: body.capabilities ?? { supports_code: true, supports_diff: false, supports_approval: false, supports_image: false },
      tags: body.tags ?? [],
      is_public: true,
      is_active: true,
      skill_ids: body.skill_ids ?? [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }),
  },
  {
    url: '/api/v1/agents/:id',
    method: 'get',
    response: ({ query }: { query: { id: string } }) => {
      return {
        id: query.id,
        user_id: 'default',
        name: query.id,
        type: 'claude',
        capabilities: { supports_code: true, supports_diff: true, supports_approval: false, supports_image: false },
        tags: [],
        is_public: true,
        is_active: true,
        skill_ids: [],
        created_at: '2026-05-01T00:00:00Z',
        updated_at: '2026-05-01T00:00:00Z',
      }
    },
  },
  {
    url: '/api/v1/agents/:id',
    method: 'patch',
    response: ({ query, body }: { query: { id: string }; body: Record<string, unknown> }) => ({
      id: query.id,
      user_id: 'default',
      name: body.name ?? 'Updated Agent',
      description: body.description ?? 'Updated description',
      type: 'claude',
      capabilities: body.capabilities ?? { supports_code: true, supports_diff: true, supports_approval: false, supports_image: false },
      tags: body.tags ?? [],
      is_public: body.is_public ?? true,
      is_active: body.is_active ?? true,
      skill_ids: body.skill_ids ?? [],
      created_at: '2026-05-01T00:00:00Z',
      updated_at: new Date().toISOString(),
    }),
  },
  {
    url: '/api/v1/agents/build',
    method: 'post',
    response: ({ body }: { body: { description: string } }) => ({
      session_id: `build-${Date.now()}`,
      draft: {
        name: 'Custom Agent',
        description: body.description,
        type: 'claude',
        system_prompt: `You are a helpful assistant specialized in: ${body.description}`,
        capabilities: { supports_code: true, supports_diff: true, supports_approval: false, supports_image: false },
        tags: ['custom'],
        suggested_skill_names: ['web-search', 'code-analysis'],
      },
    }),
  },
  {
    url: '/api/v1/agents/build/confirm',
    method: 'post',
    response: ({ body }: { body: { session_id: string; edited_draft: Record<string, unknown> } }) => ({
      id: `agent-${Date.now()}`,
      user_id: 'default',
      name: body.edited_draft.name ?? 'New Agent',
      description: body.edited_draft.description ?? '',
      type: body.edited_draft.type ?? 'claude',
      system_prompt: body.edited_draft.system_prompt ?? '',
      capabilities: body.edited_draft.capabilities ?? { supports_code: true, supports_diff: false, supports_approval: false, supports_image: false },
      tags: body.edited_draft.tags ?? [],
      is_public: true,
      is_active: true,
      skill_ids: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }),
  },

  // Skills
  {
    url: '/api/v1/skills',
    method: 'get',
    response: () => [
      {
        id: 'web-search',
        user_id: 'system',
        name: 'Web Search',
        description: 'Search the web for up-to-date information',
        type: 'builtin',
        config: { max_results: 5 },
        is_public: true,
        created_at: '2026-05-01T00:00:00Z',
        updated_at: '2026-05-01T00:00:00Z',
      },
      {
        id: 'code-analysis',
        user_id: 'system',
        name: 'Code Analysis',
        description: 'Analyze code quality and suggest improvements',
        type: 'builtin',
        config: { languages: ['python', 'typescript', 'go'] },
        is_public: true,
        created_at: '2026-05-05T00:00:00Z',
        updated_at: '2026-05-05T00:00:00Z',
      },
      {
        id: 'deploy',
        user_id: 'system',
        name: 'Deploy',
        description: 'Deploy applications to various environments',
        type: 'builtin',
        config: { environments: ['staging', 'production'] },
        is_public: true,
        created_at: '2026-05-10T00:00:00Z',
        updated_at: '2026-05-10T00:00:00Z',
      },
    ],
  },
  {
    url: '/api/v1/skills',
    method: 'post',
    response: ({ body }: { body: { name: string; description?: string; type?: string; config?: Record<string, unknown> } }) => ({
      id: `skill-${Date.now()}`,
      user_id: 'default',
      name: body.name,
      description: body.description ?? '',
      type: body.type ?? 'custom',
      config: body.config ?? {},
      is_public: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }),
  },
  {
    url: '/api/v1/skills/:id',
    method: 'get',
    response: ({ query }: { query: { id: string } }) => ({
      id: query.id,
      user_id: 'system',
      name: query.id,
      description: `Skill: ${query.id}`,
      type: 'builtin',
      config: {},
      is_public: true,
      created_at: '2026-05-01T00:00:00Z',
      updated_at: '2026-05-01T00:00:00Z',
    }),
  },
  {
    url: '/api/v1/skills/:id',
    method: 'patch',
    response: ({ query, body }: { query: { id: string }; body: Record<string, unknown> }) => ({
      id: query.id,
      user_id: 'default',
      name: body.name ?? 'Updated Skill',
      description: body.description ?? 'Updated description',
      type: 'custom',
      config: body.config ?? {},
      is_public: body.is_public ?? false,
      created_at: '2026-05-01T00:00:00Z',
      updated_at: new Date().toISOString(),
    }),
  },
]

// SSE stream mock — simulates a full agent response cycle (supports abort)
const sseMock: MockMethod = {
  url: '/api/v1/chat/stream/:conversationId',
  method: 'get',
  rawResponse: async (req: any, res: any) => {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      Connection: 'keep-alive',
    })

    const convId = req.url?.split('/').pop()?.split('?')[0] ?? ''
    const now = () => new Date().toISOString()
    const agentId = 'orchestrator'
    const threadId = 'thread-mock'
    const messageId = `msg-ssse-${Date.now()}`

    // Helper: abort-aware delay. Returns true if aborted (response already ended).
    const tick = (ms: number) => delayWithAbortCheck(ms, convId, res)

    // 1. agent_start
    sendSSE(res, 'agent_start', {
      type: 'agent_start', agent_id: agentId, thread_id: threadId,
      message_id: messageId, agent_name: 'Orchestrator', timestamp: now(),
    })
    if (await tick(300)) return

    // 2. block_start — thinking
    sendSSE(res, 'block_start', {
      type: 'block_start', agent_id: agentId, thread_id: threadId,
      message_id: messageId, block: { block_id: 'sb-1', type: 'thinking', content: '' }, timestamp: now(),
    })
    if (await tick(100)) return

    // 3. block_delta — thinking content
    const thinkingText = 'Analyzing the request...\nI should dispatch to the relevant agent.'
    for (const chunk of splitChunks(thinkingText, 8)) {
      sendSSE(res, 'block_delta', {
        type: 'block_delta', agent_id: agentId, thread_id: threadId,
        message_id: messageId, block_id: 'sb-1', delta: { content: chunk }, timestamp: now(),
      })
      if (await tick(40)) return
    }

    // 4. block_stop — thinking done
    sendSSE(res, 'block_stop', {
      type: 'block_stop', agent_id: agentId, thread_id: threadId,
      message_id: messageId, block_id: 'sb-1', final_fields: { duration_ms: 1200 }, timestamp: now(),
    })
    if (await tick(300)) return

    // 5. block_start — text
    sendSSE(res, 'block_start', {
      type: 'block_start', agent_id: agentId, thread_id: threadId,
      message_id: messageId, block: { block_id: 'sb-2', type: 'text', content: '' }, timestamp: now(),
    })
    if (await tick(100)) return

    // 6. block_delta — text content
    const textContent = 'Here is the analysis result:\n\nThe Q4 revenue grew by 15% compared to Q3.'
    for (const chunk of splitChunks(textContent, 6)) {
      sendSSE(res, 'block_delta', {
        type: 'block_delta', agent_id: agentId, thread_id: threadId,
        message_id: messageId, block_id: 'sb-2', delta: { content: chunk }, timestamp: now(),
      })
      if (await tick(30)) return
    }

    // 7. block_stop — text done
    sendSSE(res, 'block_stop', {
      type: 'block_stop', agent_id: agentId, thread_id: threadId,
      message_id: messageId, block_id: 'sb-2', timestamp: now(),
    })
    if (await tick(200)) return

    // 8. block_start — approval (pending)
    // sendSSE(res, 'block_start', {
    //   type: 'block_start', agent_id: agentId, thread_id: threadId,
    //   message_id: messageId, block: { block_id: 'sb-3', type: 'approval', action: 'run_command', detail: 'npm install axios@1.6.0 --save', status: 'pending' }, timestamp: now(),
    // })
    // if (await tick(200)) return

    // 8b. block_start — approval (create_file)
    sendSSE(res, 'block_start', {
      type: 'block_start', agent_id: 'orchestrator', thread_id: threadId,
      message_id: messageId, block: {
        block_id: 'sb-3b', type: 'approval', action: 'create_file',
        detail: "{'path': 'hello.txt', 'content': '这是一个测试文件 🎉\\n由主 Agent 创建于会话中。\\n'}",
        status: 'pending', decided_at: null, reject_reason: null,
      }, timestamp: now(),
    })
    if (await tick(200)) return

    // 9. block_start — tool_use (running)
    sendSSE(res, 'block_start', {
      type: 'block_start', agent_id: agentId, thread_id: threadId,
      message_id: messageId, block: { block_id: 'sb-4', type: 'tool_use', tool_name: 'read_file', input: { path: 'config.json' }, status: 'running' }, timestamp: now(),
    })
    if (await tick(300)) return

    // 10. block_stop — tool_use (completed)
    sendSSE(res, 'block_stop', {
      type: 'block_stop', agent_id: agentId, thread_id: threadId,
      message_id: messageId, block_id: 'sb-4', final_fields: { output: '{"api_key": "xxx", "timeout": 30000}', status: 'completed' }, timestamp: now(),
    })
    if (await tick(200)) return

    // 11. block_start — code
    sendSSE(res, 'block_start', {
      type: 'block_start', agent_id: agentId, thread_id: threadId,
      message_id: messageId, block: { block_id: 'sb-5', type: 'code', language: 'typescript', code: '', filename: 'utils.ts' }, timestamp: now(),
    })
    if (await tick(100)) return

    // 12. block_delta — code content
    const codeContent = 'export function formatCurrency(value: number): string {\n  return `$${value.toFixed(2)}`\n}'
    for (const chunk of splitChunks(codeContent, 5)) {
      sendSSE(res, 'block_delta', {
        type: 'block_delta', agent_id: agentId, thread_id: threadId,
        message_id: messageId, block_id: 'sb-5', delta: { code: chunk }, timestamp: now(),
      })
      if (await tick(25)) return
    }

    // 13. block_stop — code done
    sendSSE(res, 'block_stop', {
      type: 'block_stop', agent_id: agentId, thread_id: threadId,
      message_id: messageId, block_id: 'sb-5', timestamp: now(),
    })
    if (await tick(200)) return

    // 14. block_start — image
    sendSSE(res, 'block_start', {
      type: 'block_start', agent_id: agentId, thread_id: threadId,
      message_id: messageId, block: { block_id: 'sb-6', type: 'image', src: 'https://via.placeholder.com/400x200/3b82f6/ffffff?text=Revenue+Chart', alt: 'Revenue Chart' }, timestamp: now(),
    })
    if (await tick(100)) return

    // 15. block_start — deployment (deploying)
    sendSSE(res, 'block_start', {
      type: 'block_start', agent_id: agentId, thread_id: threadId,
      message_id: messageId, block: { block_id: 'sb-7', type: 'deployment', title: 'Preview Deploy', status: 'deploying', progress: 0 }, timestamp: now(),
    })
    if (await tick(100)) return

    // 16. block_delta — deployment progress
    for (const p of [25, 50, 75, 95]) {
      sendSSE(res, 'block_delta', {
        type: 'block_delta', agent_id: agentId, thread_id: threadId,
        message_id: messageId, block_id: 'sb-7', delta: { progress: p }, timestamp: now(),
      })
      if (await tick(150)) return
    }

    // 17. block_stop — deployment completed
    sendSSE(res, 'block_stop', {
      type: 'block_stop', agent_id: agentId, thread_id: threadId,
      message_id: messageId, block_id: 'sb-7', final_fields: { status: 'completed', url: 'https://preview.example.com/q4-sales', progress: 100 }, timestamp: now(),
    })
    if (await tick(200)) return

    // 18. block_start — artifacts
    sendSSE(res, 'block_start', {
      type: 'block_start', agent_id: agentId, thread_id: threadId,
      message_id: messageId, block: { block_id: 'sb-8', type: 'artifacts', title: 'Generated Files', items: [
        { name: 'dashboard.html', type: 'html', preview: '<h1>Q4 Revenue: $520K</h1>', filePath: '/workspace/src/index.html' },
        { name: 'report.pdf', type: 'pdf' },
        { name: 'main.py', type: 'python', preview: 'import uvicorn\n\napp = None', filePath: '/workspace/src/main.py' },
      ] }, timestamp: now(),
    })

    // 19. agent_done
    sendSSE(res, 'agent_done', {
      type: 'agent_done', agent_id: agentId, thread_id: threadId,
      message_id: messageId, timestamp: now(),
    })
    await delay(100)

    // 20. round_done
    sendSSE(res, 'round_done', {
      type: 'round_done', timestamp: now(),
    })
    await delay(100)

    // 21. queue_drained
    sendSSE(res, 'queue_drained', {
      type: 'queue_drained', timestamp: now(),
    })

    res.end()
  },
}

export default [...mockList, sseMock] as MockMethod[]
