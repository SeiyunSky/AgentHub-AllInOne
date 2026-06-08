export default {
  // ─── Common ──────────────────────────────────────────────────────────────────
  common: {
    cancel: 'Cancel',
    confirm: 'Confirm',
    save: 'Save',
    delete: 'Delete',
    rename: 'Rename',
    loading: 'Loading...',
    noDescription: 'No description',
    active: 'Active',
    inactive: 'Inactive',
    all: 'All',
    copied: 'Copied!',
    copy: 'Copy',
    preview: 'Preview',
    edit: 'Edit',
    download: 'Download',
    refresh: 'Refresh',
    collapse: 'Collapse',
    expandAll: 'Expand all',
  },

  // ─── Nav ─────────────────────────────────────────────────────────────────────
  nav: {
    logout: 'Sign out',
    logoutConfirm: 'Are you sure you want to sign out?',
    logoutTitle: 'Sign out',
    logoutButton: 'Sign out',
    contributors: 'Work Summary',
    contributorsTitle: '🐧 Contributors',
    contributorsHint: 'Click a card for details',
    switchLang: 'Switch language',
  },

  // ─── Auth ─────────────────────────────────────────────────────────────────────
  auth: {
    loginTitle: 'Welcome back',
    loginSubtitle: 'Sign in to your account to continue',
    registerTitle: 'Create account',
    registerSubtitle: 'Join the Agent Orchestrator Platform',
    username: 'Username',
    password: 'Password',
    displayName: 'Display name (optional)',
    email: 'Email (optional)',
    confirmPassword: 'Confirm password',
    signIn: 'Sign In',
    createAccount: 'Create Account',
    newHere: 'New here?',
    createAccountLink: 'Create an account',
    alreadyHaveAccount: 'Already have an account?',
    signInLink: 'Sign in',
    loginFailed: 'Login failed, please try again',
    registerFailed: 'Registration failed, please try again',
    providersLabel: 'Supports leading AI providers',
    brandSubtitle: 'Agent Orchestrator Platform',
    featureMultiAgent: 'Multi-Agent',
    featureStreaming: 'Streaming',
    featureParallelExecution: 'Parallel Execution',
    featureDiffPreview: 'Diff & Preview',
    featureFreeToJoin: 'Free to Join',
    featureNoCreditCard: 'No Credit Card',
    featureInstantAccess: 'Instant Access',
    statProviders: 'AI Providers',
    statConcurrentAgents: 'Concurrent Agents',
    statRealTimeStream: 'Real-time Stream',
    stepAccountCreation: 'Create your account in seconds',
    stepAgentConfig: 'Configure AI agents with custom prompts',
    stepParallelOrchestration: 'Orchestrate parallel conversations',
    validation: {
      usernameRequired: 'Please enter username',
      usernameLength: 'Username must be 4-50 characters',
      usernameFormat: 'Only letters, digits, _ and - are allowed',
      passwordRequired: 'Please enter password',
      passwordLength: 'Password must be at least 8 characters',
      confirmPasswordRequired: 'Please confirm your password',
      passwordsMismatch: 'Passwords do not match',
      emailInvalid: 'Invalid email format',
      displayNameTooLong: 'Display name too long',
    },
    usernamePlaceholderRules: 'Username (4-50 chars, a-z 0-9 _ -)',
    passwordPlaceholderRules: 'Password (min 8 chars)',
  },

  // ─── Conversations ───────────────────────────────────────────────────────────
  conversation: {
    activeConversations: 'Active Conversations',
    newChat: 'New Chat',
    pinned: 'Pinned',
    recent: 'Recent',
    archived: 'Archived',
    rename: 'Rename Conversation',
    enterNewName: 'Enter new name',
    deleteConfirm: 'Delete this conversation? This action cannot be undone.',
    deleteTitle: 'Delete Conversation',
    deleteFailed: 'Delete failed, please try again',
    unnamedSession: 'Unnamed session',
  },

  // ─── Chat ─────────────────────────────────────────────────────────────────────
  chat: {
    selectOrCreate: 'Select or start a chat from the left',
    noSessionOpen: 'Please open or create a conversation first',
    uploadFailed: 'Upload failed, please try again',
    uploadInProgress: 'Upload in progress, please wait',
    archivedNotice: 'This conversation is archived and cannot receive messages',
    feedbackFailed: 'Failed to submit feedback, please retry',
    feedbackWithdrawn: 'Feedback withdrawn',
    feedbackThumbsUp: '👍 Feedback submitted',
    feedbackThumbsDown: '👎 Feedback submitted',
    messageRead: 'Read',
  },

  // ─── Conversation Settings ────────────────────────────────────────────────────
  conversationSettings: {
    title: 'Conversation Settings',
    members: 'Members (',
    addMember: 'Add member',
    noAgentsToAdd: 'No agents available to add',
    orchestratorLabel: 'System · Owner',
    tokenUsage: 'Token Usage',
    totalToken: 'Total Tokens',
    inputToken: 'Input',
    outputToken: 'Output',
    messages: 'messages',
    noTokenUsage: 'No token usage in this conversation yet',
    refreshUsage: 'Refresh usage',
    memberAdded: 'Added',
    addFailed: 'Failed to add, please retry',
    memberRemoved: 'Removed',
    removeFailed: 'Failed to remove, please retry',
    sessionSettingsTitle: 'Settings (Members / Token Usage)',
    settings: 'Settings',
  },

  // ─── New Chat Dialog ──────────────────────────────────────────────────────────
  newChat: {
    noPresetMembers: 'No preset members',
    taskModeDesc: 'Orchestrator manages tasks',
    broadcastModeDesc: 'Casual chat, each replies',
  },

  // ─── Chat Status ─────────────────────────────────────────────────────────────
  chatStatus: {
    oneAgentReplying: '1 agent replying',
    multiAgentParallel: ' agents running in parallel',
    multiAgentIdle: ' agents · idle',
  },

  // ─── Agent Bubble ─────────────────────────────────────────────────────────────
  agentBubble: {
    thinking: 'Thinking',
    typing: 'Typing',
    toolPrefix: 'Calling ',
    toolFallback: 'Calling tool',
    idle: 'Idle',
    reactionLike: 'Liked',
    reactionDislike: 'Disliked',
  },

  // ─── Collapsible ─────────────────────────────────────────────────────────────
  collapsible: {
    collapse: 'Collapse',
    expandAll: 'Expand all',
  },

  // ─── Approval Block ───────────────────────────────────────────────────────────
  approval: {
    approved: 'Approved',
    approvedAt: 'Approved at {time}',
    rejected: 'Rejected',
    rejectedAt: 'Rejected at {time}',
    waitingApproval: 'Waiting for approval...',
    rejectReasonPlaceholder: 'Reason for rejection (optional)',
    approveButton: 'Approve (Y)',
    rejectButton: 'Reject (N)',
    confirmReject: 'Confirm',
    keyboardHint: 'Press Y / N',
    hideContent: 'Hide content',
    showContent: 'Show content',
    hideDiff: 'Hide diff',
    showDiff: 'Show diff',
    hideDetails: 'Hide details',
    showDetails: 'Show details ({size})',
    lineCount: '{n} lines',
    labelOld: '- old',
    labelNew: '+ new',
  },

  // ─── Tool Use Block ───────────────────────────────────────────────────────────
  toolUse: {
    labelInput: 'Input:',
    labelOutput: 'Output:',
    executing: 'Executing...',
  },

  // ─── Thinking Block ───────────────────────────────────────────────────────────
  thinking: {
    label: 'Thinking',
  },

  // ─── Code Block ───────────────────────────────────────────────────────────────
  codeBlock: {
    preview: 'Preview',
    applying: 'Applying…',
    applied: 'Applied ✓',
    failed: 'Failed ✗',
    apply: 'Apply',
    copied: 'Copied!',
    copy: 'Copy',
    collapseLines: 'Collapse ({n} lines)',
    showAllLines: 'Show all {n} lines',
  },

  // ─── Deployment Block ─────────────────────────────────────────────────────────
  deploymentBlock: {
    labelLogs: 'Logs:',
    deploying: 'Deploying...',
    failed: 'Deployment failed',
  },

  // ─── Preview Card ─────────────────────────────────────────────────────────────
  previewCard: {
    fullPreview: 'Full Preview',
  },

  // ─── Deployments View ─────────────────────────────────────────────────────────
  deployments: {
    emptyTitle: 'No deployments yet',
    emptyDesc: 'Ask the main agent to call the deploy_app tool. Deployments will appear here.',
    running: 'Running',
    urlLabel: 'URL:',
    copyUrl: 'Copy URL',
    openInTab: 'Open in new tab',
    refresh: 'Refresh',
    historyLabel: 'Deployment history (',
    latestFailed: 'Latest deployment failed',
    unknownError: 'Unknown error',
    deployFailed: 'Deployment failed',
  },

  // ─── Workflow View ────────────────────────────────────────────────────────────
  workflow: {
    emptyTitle: 'Waiting for agent to run',
    emptyDesc: 'Send a message and the execution flow will appear here in real time',
    agentUnit: ' agents',
    done: 'Done',
    error: 'Failed',
    cancelled: 'Cancelled',
    currentRound: 'This round',
    pendingHint: 'Waiting for dependencies to complete',
    waitingApproval: 'Waiting for user approval',
    roundDone: 'Round complete',
    blockText: 'Text output',
    blockThinking: 'Thinking',
    blockCode: 'Code generation',
    blockImage: 'Image',
    blockApproval: 'Pending approval',
    blockDeployment: 'Deployment',
    blockArtifacts: 'Artifacts',
  },

  // ─── Agents Panel ─────────────────────────────────────────────────────────────
  agentsPanel: {
    title: 'Agents',
    emptyTitle: 'No agents yet',
    emptyDesc: 'Create your first AI agent to get started. Each agent can have unique skills and behaviors.',
    createAgent: 'Create Agent',
    noMatch: 'No agents match your search',
    filterAll: 'All',
    filterActive: 'Active',
    filterClaude: 'Claude',
    filterCodex: 'Codex',
    filterCustom: 'Custom',
    noDescription: 'No description',
    tooltipActive: 'Active',
    tooltipInactive: 'Inactive',
  },

  // ─── Skills Panel ─────────────────────────────────────────────────────────────
  skillsPanel: {
    title: 'Skills',
    emptyTitle: 'No skills yet',
    emptyDesc: 'Create your first skill to define reusable knowledge and behaviors for your agents.',
    createSkill: 'Create Skill',
    noMatch: 'No skills match your filter',
    filterAll: 'All',
    noDescription: 'No description',
    tooltipActive: 'Active',
    tooltipInactive: 'Inactive',
    uncategorized: 'Uncategorized',
  },

  // ─── Sandbox Files View ───────────────────────────────────────────────────────
  sandboxFiles: {
    toolbarLabel: 'Sandbox',
    toolbarFile: 'file',
    toolbarFiles: 'files',
    tooltipLoading: 'Loading',
    tooltipRefresh: 'Refresh',
    noConversation: 'No conversation selected',
    loadFailed: 'Failed to load files',
    emptyTitle: 'No files yet',
    emptyDesc: 'When the agent creates a file in this conversation, it will appear here.',
    tooltipPreview: 'Preview',
    tooltipEdit: 'Edit',
    tooltipDownload: 'Download',
  },

  // ─── Agent Contacts ───────────────────────────────────────────────────────────
  agentContacts: {
    activeAgents: 'Active Agents',
    newAgent: 'New Agent',
    noDescription: 'No description',
  },

  // ─── Agent Builder ────────────────────────────────────────────────────────────
  agentBuilder: {
    title: 'Build with AI',
    subtitle: 'Describe your agent and I\'ll generate it',
    inputPlaceholder: 'Describe the agent you want to build...',
    greetingInitial: 'Hi! Describe the agent you want to build and I\'ll generate a configuration for you. For example: "A customer support agent that handles refund requests professionally."',
    greetingSimple: 'Hi! Describe the agent you want to build and I\'ll generate a configuration for you.',
    draftConfirmation: 'I\'ve drafted an agent called "{name}". You can review it above and click "Use This Agent" to create it, or keep chatting to refine.',
    errorGeneration: 'Sorry, I had trouble generating the agent. Please try again.',
    errorBuildFailed: 'Build request failed',
    cancel: 'Cancel',
    useAgent: 'Use This Agent',
  },

  // ─── Agent Form ───────────────────────────────────────────────────────────────
  agentForm: {
    namePlaceholder: 'Agent Name',
    nameHelper: 'Give your agent a memorable name',
    descriptionLabel: 'Description',
    descriptionPlaceholder: 'Brief description of what this agent does...',
    platformLabel: 'Platform',
    skillsLabel: 'Skills',
    addMoreSkills: 'Add more skills',
    selectSkills: 'Select skills',
    capabilitiesGroup: 'Capabilities',
    skillsGroup: 'Skills',
    loadingSkills: 'Loading...',
    noSkillsAvailable: 'No skills available',
    systemPromptLabel: 'System Prompt',
    markdownSupported: 'Markdown supported',
    systemPromptPlaceholder: '### Goals\nDefine what the agent should accomplish...\n### Skills\nList the agent\'s core capabilities...\n### Workflow\nDescribe how the agent should work...\n### Constraints\nSet boundaries and limitations...',
    tagsLabel: 'Tags',
    addTagPlaceholder: 'Add tag...',
    addTagHelper: 'Press Enter to add a tag',
    visibilityLabel: 'Visibility',
    publicAgent: 'Public Agent',
    publicAgentDesc: 'Allow other users to discover and use this agent',
    statusLabel: 'Status',
    activeLabel: 'Active',
    disabledAgentDesc: 'Disabled agents cannot be used in conversations',
    skillCodeExecution: 'Code Execution',
    skillDiffReview: 'Diff Review',
    skillApprovalFlow: 'Approval Flow',
    skillImageProcessing: 'Image Processing',
  },

  // ─── Skill Form ───────────────────────────────────────────────────────────────
  skillForm: {
    namePlaceholder: 'skill-name',
    nameHelper: 'English identifier (lowercase, numbers, hyphens, underscores)',
    displayNameLabel: 'Display Name',
    displayNamePlaceholder: 'Display name (optional)',
    descriptionLabel: 'Description',
    descriptionPlaceholder: 'Brief description of what this skill does...',
    categoryLabel: 'Category',
    selectCategory: 'Select category',
    contentLabel: 'Content',
    markdownSupported: 'Markdown supported',
    contentPlaceholder: '### Overview\nDescribe the skill\'s purpose and scope...\n### Instructions\nStep-by-step guidance for the agent...\n### Examples\nProvide example inputs and outputs...\n### Constraints\nSet boundaries and limitations...',
    visibilityLabel: 'Visibility',
    publicSkill: 'Public Skill',
    publicSkillDesc: 'Allow other users to discover and use this skill',
    statusLabel: 'Status',
    activeLabel: 'Active',
    disabledSkillDesc: 'Disabled skills cannot be selected by agents',
    categoryCode: 'Code',
    categorySecurity: 'Security',
    categoryDomainKnowledge: 'Domain Knowledge',
    categoryGeneral: 'General',
  },

  // ─── SSE Errors ───────────────────────────────────────────────────────────────
  sse: {
    errorPrefix: '[Error] ',
  },

  // ─── Approval Overlay ─────────────────────────────────────────────────────────
  approvalOverlay: {
    title: 'Approval Required',
  },

  // ─── Message Actions ──────────────────────────────────────────────────────────
  messageActions: {
    like: 'Like',
    dislike: 'Dislike',
    reply: 'Reply',
    copy: 'Copy',
  },

  // ─── Time Ago ─────────────────────────────────────────────────────────────────
  timeAgo: {
    justNow: 'just now',
    minutesAgo: '{n}m ago',
    hoursAgo: '{n}h ago',
  },

  // ─── Nav Extra ────────────────────────────────────────────────────────────────
  navExtra: {
    search: 'Search',
    support: 'About',
    settings: 'Settings',
    collapse: 'Collapse',
    chatLabel: 'Chat',
    agentsLabel: 'Agents',
    skillsLabel: 'Skills',
    searchDialogTitle: 'Search',
    searchDialogConfirm: 'Search',
    searchDialogPlaceholder: 'Search conversations, agents, skills...',
  },

  // ─── Agent Form Panel ─────────────────────────────────────────────────────────
  agentFormPanel: {
    editTitle: 'Edit Agent',
    createTitle: 'Create Agent',
    readonlyTag: '(Read-only)',
    readonlyBuiltin: 'Built-in agents cannot be modified',
    readonlyOther: 'You do not have permission to modify this agent',
    delete: 'Delete',
    cancel: 'Cancel',
    saveChanges: 'Save Changes',
    createAgent: 'Create Agent',
    loadFailed: 'Failed to load agent',
    deleteConfirm: 'Delete agent "{name}"? This cannot be undone.',
    deleteTitle: 'Delete Agent',
    deleted: 'Agent deleted',
    deleteFailed: 'Failed to delete agent',
    nameRequired: 'Agent name is required',
    updated: 'Agent updated',
    created: 'Agent created',
    saveFailed: 'Failed to save agent',
  },

  // ─── Skill Form Panel ─────────────────────────────────────────────────────────
  skillFormPanel: {
    editTitle: 'Edit Skill',
    createTitle: 'Create Skill',
    readonlyTag: '(Read-only)',
    readonlyBuiltin: 'Built-in skills cannot be modified',
    readonlyOther: 'You do not have permission to modify this skill',
    delete: 'Delete',
    cancel: 'Cancel',
    saveChanges: 'Save Changes',
    createSkill: 'Create Skill',
    loadFailed: 'Failed to load skill',
    deleteConfirm: 'Delete skill "{name}"? This cannot be undone.',
    deleteTitle: 'Delete Skill',
    deleted: 'Skill deleted',
    deleteFailed: 'Failed to delete skill',
    nameRequired: 'Skill name is required',
    nameFormat: 'Skill name must be lowercase letters, numbers, hyphens, or underscores',
    contentRequired: 'Skill content is required',
    updated: 'Skill updated',
    created: 'Skill created',
    saveFailed: 'Failed to save skill',
  },

  // ─── Right Panel ──────────────────────────────────────────────────────────────
  rightPanel: {
    view: 'View',
    edit: 'Edit',
    closePreview: 'Close preview (back to last tab)',
    running: 'Running',
    idle: 'Idle',
    tabWorkflow: 'Workflow',
    tabFiles: 'Files',
    tabDeploy: 'Deploy',
    tabPreview: 'Preview',
    titleFiles: 'Files',
    titleDeployments: 'Deployments',
    titleWorkflow: 'Workflow',
  },

  // ─── Settings Dialog ──────────────────────────────────────────────────────────
  settings: {
    title: 'Settings',
    accentColor: 'Accent Color',
    language: 'Language',
    langChinese: 'Chinese',
    langEnglish: 'English',
  },

  // ─── New Chat Dialog Extra ────────────────────────────────────────────────────
  newChatExtra: {
    title: 'New Chat',
    subtitle: 'Set up your conversation',
    squadTemplates: 'Squad Templates',
    chatTitleLabel: 'Title',
    chatTitlePlaceholder: 'Enter chat title...',
    modeLabel: 'Mode',
    taskMode: 'Task',
    broadcastMode: 'Broadcast',
    inviteAgents: 'Invite Agents',
    addMoreAgents: 'Add more agents',
    selectAgents: 'Select agents',
    searchAgents: 'Search agents...',
    noAgentsAvailable: 'No agents available',
    creating: 'Creating...',
    createChat: 'Create Chat',
  },

  // ─── Chat Input Extra ─────────────────────────────────────────────────────────
  chatInputExtra: {
    replyingTo: 'Replying to {name}',
    filesAttached: '{n} file(s) attached',
    attachFiles: 'Attach files (uploads to conversation sandbox)',
    placeholder: 'Ask anything...',
  },

  // ─── Conversation Item ────────────────────────────────────────────────────────
  convItem: {
    noMessages: 'No messages yet',
    rename: 'Rename',
    unpin: 'Unpin',
    pin: 'Pin',
    unarchive: 'Unarchive',
    archive: 'Archive',
    delete: 'Delete',
  },

  // ─── App Layout ───────────────────────────────────────────────────────────────
  appLayout: {
    expandSidebar: 'Expand sidebar',
  },

  // ─── Chat Panel ───────────────────────────────────────────────────────────────
  chatPanel: {
    defaultTitle: 'Chat',
    readyStatus: 'Ready',
  },

  // ─── Conversation Settings Extra ──────────────────────────────────────────────
  convSettingsExtra: {
    removeMember: 'Remove {name} from conversation',
  },

  // ─── Code Block Extra ─────────────────────────────────────────────────────────
  codeBlockExtra: {
    defaultLabel: 'Code',
  },

  // ─── Image Block ──────────────────────────────────────────────────────────────
  imageBlock: {
    defaultLabel: 'Image',
    defaultAlt: 'Image',
  },

  // ─── Deployments Extra ────────────────────────────────────────────────────────
  deploymentsExtra: {
    copied: '✓ Copied',
    activeStatus: 'ACTIVE',
  },

  // ─── Skills List ──────────────────────────────────────────────────────────────
  skillsList: {
    libraryTitle: 'Skills Library',
    newSkill: 'New Skill',
    noDescription: 'No description',
  },

  // ─── Element Plus locale name ─────────────────────────────────────────────────
  lang: 'English',
}
