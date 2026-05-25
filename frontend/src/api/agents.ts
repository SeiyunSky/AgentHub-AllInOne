import type { Agent, AgentDraft } from '@/types/agent'

const mockAgents: Agent[] = [
  {
    id: '1',
    name: 'Orchestrator',
    description: 'Primary orchestration agent that coordinates tasks across all agents.',
    type: 'claude',
    systemPrompt: 'You are the primary orchestrator...',
    capabilities: { supportsCode: true, supportsDiff: true, supportsApproval: true, supportsImage: false },
    tags: ['core', 'orchestration'],
    isPublic: true,
    isActive: true,
    createdAt: new Date(),
    updatedAt: new Date(),
  },
  {
    id: '2',
    name: 'Data Analyst',
    description: 'Analyzes data and generates insights and visualizations.',
    type: 'codex',
    systemPrompt: 'You are a data analysis expert...',
    capabilities: { supportsCode: true, supportsDiff: false, supportsApproval: false, supportsImage: true },
    tags: ['data', 'analysis'],
    isPublic: true,
    isActive: true,
    createdAt: new Date(),
    updatedAt: new Date(),
  },
  {
    id: '3',
    name: 'Lead Developer',
    description: 'Handles code review, architecture decisions, and technical guidance.',
    type: 'claude',
    systemPrompt: 'You are a senior developer...',
    capabilities: { supportsCode: true, supportsDiff: true, supportsApproval: true, supportsImage: false },
    tags: ['development', 'code-review'],
    isPublic: false,
    isActive: true,
    createdAt: new Date(),
    updatedAt: new Date(),
  },
  {
    id: '4',
    name: 'QA Engineer',
    description: 'Writes and runs tests, identifies bugs and quality issues.',
    type: 'opencode',
    systemPrompt: 'You are a QA engineer...',
    capabilities: { supportsCode: true, supportsDiff: false, supportsApproval: false, supportsImage: false },
    tags: ['testing', 'quality'],
    isPublic: true,
    isActive: false,
    createdAt: new Date(),
    updatedAt: new Date(),
  },
]

export const agentsApi = {
  async list(): Promise<Agent[]> {
    return mockAgents
  },

  async get(id: string): Promise<Agent | undefined> {
    return mockAgents.find(a => a.id === id)
  },

  async create(_data: AgentDraft): Promise<Agent> {
    return {
      id: String(Date.now()),
      ..._data,
      isActive: true,
      createdAt: new Date(),
      updatedAt: new Date(),
    }
  },

  async update(id: string, data: Partial<Agent>): Promise<Agent> {
    const agent = mockAgents.find(a => a.id === id)
    if (!agent) throw new Error('Agent not found')
    return { ...agent, ...data, updatedAt: new Date() }
  },
}
