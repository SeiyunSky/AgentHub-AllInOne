import type { MockMethod } from 'vite-plugin-mock'
import type { IncomingMessage, ServerResponse } from 'http'

function sendSSE(res: ServerResponse, event: string, data: unknown) {
  res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
}

async function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms))
}

const conversations = [
  {
    id: 'conv-1',
    user_id: 'default',
    title: 'Q4 Sales Analysis',
    mode: 'group',
    is_pinned: true,
    is_archived: false,
    last_message_preview: 'Excellent work! The report is ready.',
    last_message_at: '2026-05-26T10:00:00Z',
    message_count: 14,
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
    blocks: [{ block_id: 'b1', type: 'text', content: 'Can you help me process the Q4 sales data?' }],
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
  {
    id: 'msg-2',
    conversation_id: 'conv-1',
    thread_id: 'thread-1',
    parent_id: null,
    user_id: null,
    agent_id: 'orchestrator',
    role: 'assistant',
    blocks: [
      { block_id: 'b2', type: 'thinking', content: 'The user wants to process Q4 sales data...', duration_ms: 2500 },
      { block_id: 'b3', type: 'text', content: "I'll analyze the sales data and coordinate with the team." },
      {
        block_id: 'b4',
        type: 'tool_use',
        tool_name: 'dispatch_agent',
        input: { agent: 'data-analyst', task: 'load_csv' },
        output: 'Agent dispatched successfully',
        status: 'completed',
      },
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
      {
        block_id: 'b6',
        type: 'code',
        language: 'python',
        code: 'import pandas as pd\n\ndef load_data():\n    df = pd.read_csv("sales_q4.csv")\n    return df.to_dict("records")',
        filename: 'sales_q4.csv',
      },
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
    response: ({ body }: { body: { conversation_id: string } }) => ({
      conversation_id: body.conversation_id,
      aborted: true,
      cancelled_thread_ids: [],
      timestamp: new Date().toISOString(),
    }),
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
]

// SSE stream mock — simulates a full agent response cycle
const sseMock: MockMethod = {
  url: '/api/v1/chat/stream/:conversationId',
  method: 'get',
  rawResponse: async (req: any, res: any) => {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      Connection: 'keep-alive',
    })

    const now = () => new Date().toISOString()
    const agentId = 'orchestrator'
    const threadId = 'thread-mock'
    const messageId = `msg-ssse-${Date.now()}`

    // 1. agent_start
    sendSSE(res, 'agent_start', {
      type: 'agent_start',
      agent_id: agentId,
      thread_id: threadId,
      message_id: messageId,
      agent_name: 'Orchestrator',
      timestamp: now(),
    })
    await delay(300)

    // 2. block_start — thinking
    sendSSE(res, 'block_start', {
      type: 'block_start',
      agent_id: agentId,
      thread_id: threadId,
      message_id: messageId,
      block: { block_id: 'sb-1', type: 'thinking', content: '' },
      timestamp: now(),
    })
    await delay(100)

    // 3. block_delta — thinking content (simulated typing)
    const thinkingChunks = ['Analyzing the request...\n', 'I should dispatch to the relevant agent.']
    for (const chunk of thinkingChunks) {
      sendSSE(res, 'block_delta', {
        type: 'block_delta',
        agent_id: agentId,
        thread_id: threadId,
        message_id: messageId,
        block_id: 'sb-1',
        delta: { content: chunk },
        timestamp: now(),
      })
      await delay(200)
    }

    // 4. block_stop — thinking done
    sendSSE(res, 'block_stop', {
      type: 'block_stop',
      agent_id: agentId,
      thread_id: threadId,
      message_id: messageId,
      block_id: 'sb-1',
      final_fields: { duration_ms: 1200 },
      timestamp: now(),
    })
    await delay(300)

    // 5. block_start — text
    sendSSE(res, 'block_start', {
      type: 'block_start',
      agent_id: agentId,
      thread_id: threadId,
      message_id: messageId,
      block: { block_id: 'sb-2', type: 'text', content: '' },
      timestamp: now(),
    })
    await delay(100)

    // 6. block_delta — text content
    const textChunks = ['Here is the analysis result:\n\n', 'The Q4 revenue grew by 15% compared to Q3.']
    for (const chunk of textChunks) {
      sendSSE(res, 'block_delta', {
        type: 'block_delta',
        agent_id: agentId,
        thread_id: threadId,
        message_id: messageId,
        block_id: 'sb-2',
        delta: { content: chunk },
        timestamp: now(),
      })
      await delay(300)
    }

    // 7. block_stop — text done
    sendSSE(res, 'block_stop', {
      type: 'block_stop',
      agent_id: agentId,
      thread_id: threadId,
      message_id: messageId,
      block_id: 'sb-2',
      timestamp: now(),
    })
    await delay(200)

    // 8. agent_done
    sendSSE(res, 'agent_done', {
      type: 'agent_done',
      agent_id: agentId,
      thread_id: threadId,
      message_id: messageId,
      timestamp: now(),
    })
    await delay(100)

    // 9. round_done
    sendSSE(res, 'round_done', {
      type: 'round_done',
      timestamp: now(),
    })
    await delay(100)

    // 10. queue_drained
    sendSSE(res, 'queue_drained', {
      type: 'queue_drained',
      timestamp: now(),
    })

    res.end()
  },
}

export default [...mockList, sseMock] as MockMethod[]
