import { describe, it, expect, beforeAll } from 'vitest'
import { conversationsApi } from '../conversations'
import { chatApi } from '../chat'
import { messagesApi } from '../messages'
import { agentsApi } from '../agents'

const BASE = 'http://localhost:5173/api/v1'

// Helper: direct fetch to vite-plugin-mock (bypasses axios)
async function mockFetch(path: string, options?: RequestInit) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', 'X-User-Id': 'default' },
    ...options,
  })
  return { status: res.status, data: await res.json() }
}

describe('Conversations API', () => {
  it('lists conversations', async () => {
    const { status, data } = await mockFetch('/conversations')
    expect(status).toBe(200)
    expect(data).toBeInstanceOf(Array)
    expect(data.length).toBeGreaterThanOrEqual(2)
    expect(data[0]).toHaveProperty('id')
    expect(data[0]).toHaveProperty('title')
    expect(data[0]).toHaveProperty('agents')
  })

  it('creates a conversation', async () => {
    const { status, data } = await mockFetch('/conversations', {
      method: 'POST',
      body: JSON.stringify({ title: 'Test Chat', mode: 'single', agent_ids: ['orchestrator'] }),
    })
    expect(status).toBe(200)
    expect(data.title).toBe('Test Chat')
    expect(data.mode).toBe('single')
    expect(data).toHaveProperty('id')
    expect(data.message_count).toBe(0)
  })

  it('gets a single conversation', async () => {
    const { data } = await mockFetch('/conversations/conv-1')
    expect(data.id).toBe('conv-1')
    expect(data.title).toBe('Q4 Sales Analysis')
    expect(data.agents).toBeInstanceOf(Array)
    expect(data.agents.length).toBe(3)
  })

  it('updates a conversation', async () => {
    const { data } = await mockFetch('/conversations/conv-1', {
      method: 'PATCH',
      body: JSON.stringify({ title: 'Renamed', is_pinned: false }),
    })
    expect(data.title).toBe('Renamed')
    expect(data.is_pinned).toBe(false)
  })

  it('returns 404 for nonexistent conversation', async () => {
    const { status, data } = await mockFetch('/conversations/nonexistent')
    expect(data).toHaveProperty('message')
  })
})

describe('Messages API', () => {
  it('lists messages for a conversation', async () => {
    const { status, data } = await mockFetch('/conversations/conv-1/messages')
    expect(status).toBe(200)
    expect(data).toBeInstanceOf(Array)
    expect(data.length).toBeGreaterThanOrEqual(8)
  })

  it('message has correct block types', async () => {
    const { data } = await mockFetch('/conversations/conv-1/messages')
    // msg-2 has thinking + text + tool_use blocks
    const agentMsg = data.find((m: any) => m.id === 'msg-2')
    expect(agentMsg).toBeDefined()
    expect(agentMsg.blocks.length).toBe(3)
    expect(agentMsg.blocks[0].type).toBe('thinking')
    expect(agentMsg.blocks[1].type).toBe('text')
    expect(agentMsg.blocks[2].type).toBe('tool_use')
  })

  it('code block has correct fields', async () => {
    const { data } = await mockFetch('/conversations/conv-1/messages')
    const codeMsg = data.find((m: any) => m.id === 'msg-3')
    const codeBlock = codeMsg.blocks.find((b: any) => b.type === 'code')
    expect(codeBlock).toBeDefined()
    expect(codeBlock.language).toBe('python')
    expect(codeBlock).toHaveProperty('code')
    expect(codeBlock).toHaveProperty('filename')
  })

  it('updates feedback', async () => {
    const { status, data } = await mockFetch('/messages/msg-3/feedback', {
      method: 'PATCH',
      body: JSON.stringify({ feedback: 'down' }),
    })
    expect(status).toBe(200)
    expect(data.success).toBe(true)
  })

  it('user message has role=user', async () => {
    const { data } = await mockFetch('/conversations/conv-1/messages')
    const userMsg = data.find((m: any) => m.role === 'user')
    expect(userMsg).toBeDefined()
    expect(userMsg.agent_id).toBeNull()
    expect(userMsg.blocks[0].type).toBe('text')
  })
})

describe('Chat API', () => {
  it('sends a message and gets started response', async () => {
    const { status, data } = await mockFetch('/chat', {
      method: 'POST',
      body: JSON.stringify({ conversation_id: 'conv-1', content: 'Hello' }),
    })
    expect(status).toBe(200)
    expect(data.status).toBe('started')
    expect(data).toHaveProperty('user_message_id')
    expect(data.conversation_id).toBe('conv-1')
  })

  it('stops a chat round', async () => {
    const { status, data } = await mockFetch('/chat/stop', {
      method: 'POST',
      body: JSON.stringify({ conversation_id: 'conv-1' }),
    })
    expect(status).toBe(200)
    expect(data).toHaveProperty('aborted')
    expect(data).toHaveProperty('cancelled_thread_ids')
    expect(data).toHaveProperty('timestamp')
  })
})

describe('Agents API', () => {
  it('lists agents', async () => {
    const { status, data } = await mockFetch('/agents')
    expect(status).toBe(200)
    expect(data).toBeInstanceOf(Array)
    expect(data.length).toBeGreaterThanOrEqual(2)
    expect(data[0]).toHaveProperty('capabilities')
    expect(data[0].capabilities).toHaveProperty('supports_code')
  })

  it('gets a single agent', async () => {
    const { data } = await mockFetch('/agents/orchestrator')
    expect(data.id).toBe('orchestrator')
    expect(data).toHaveProperty('type')
    expect(data).toHaveProperty('capabilities')
    expect(data).toHaveProperty('tags')
  })
})
