export default {
  // ─── 通用 ───────────────────────────────────────────────────────────────────
  common: {
    cancel: '取消',
    confirm: '确定',
    save: '保存',
    delete: '删除',
    rename: '重命名',
    loading: '加载中...',
    noDescription: '暂无描述',
    active: '活跃',
    inactive: '已禁用',
    all: '全部',
    copied: '已复制!',
    copy: '复制',
    preview: '预览',
    edit: '编辑',
    download: '下载',
    refresh: '刷新',
    collapse: '收起',
    expandAll: '展开全部',
  },

  // ─── 导航栏 ──────────────────────────────────────────────────────────────────
  nav: {
    logout: '退出登录',
    logoutConfirm: '确定要退出登录吗?',
    logoutTitle: '退出登录',
    logoutButton: '退出',
    contributors: '工作内容',
    contributorsTitle: '🐧 Contributors',
    contributorsHint: '点击卡片查看详情',
    switchLang: '切换语言',
  },

  // ─── 登录/注册 ────────────────────────────────────────────────────────────────
  auth: {
    loginTitle: '欢迎回来',
    loginSubtitle: '登录您的账号以继续',
    registerTitle: '创建账号',
    registerSubtitle: '加入 Agent 编排平台',
    username: '用户名',
    password: '密码',
    displayName: '显示名称（可选）',
    email: '邮箱（可选）',
    confirmPassword: '确认密码',
    signIn: '登录',
    createAccount: '创建账号',
    newHere: '还没有账号？',
    createAccountLink: '立即注册',
    alreadyHaveAccount: '已有账号？',
    signInLink: '立即登录',
    loginFailed: '登录失败，请稍后重试',
    registerFailed: '注册失败，请稍后重试',
    providersLabel: '支持主流 AI 提供商',
    brandSubtitle: 'Agent 编排平台',
    featureMultiAgent: '多 Agent',
    featureStreaming: '流式输出',
    featureParallelExecution: '并行执行',
    featureDiffPreview: 'Diff 预览',
    featureFreeToJoin: '免费加入',
    featureNoCreditCard: '无需信用卡',
    featureInstantAccess: '立即使用',
    statProviders: 'AI 提供商',
    statConcurrentAgents: '并发 Agent 数',
    statRealTimeStream: '实时流',
    stepAccountCreation: '秒速创建账号',
    stepAgentConfig: '配置自定义 AI Agent',
    stepParallelOrchestration: '编排并行对话',
    // 表单校验
    validation: {
      usernameRequired: '请输入用户名',
      usernameLength: '用户名须为 4-50 个字符',
      usernameFormat: '只允许字母、数字、_ 和 -',
      passwordRequired: '请输入密码',
      passwordLength: '密码至少 8 个字符',
      confirmPasswordRequired: '请确认密码',
      passwordsMismatch: '两次密码不一致',
      emailInvalid: '邮箱格式不正确',
      displayNameTooLong: '显示名称过长',
    },
    usernamePlaceholderRules: '用户名（4-50 位，a-z 0-9 _ -）',
    passwordPlaceholderRules: '密码（至少 8 位）',
  },

  // ─── 会话列表 ─────────────────────────────────────────────────────────────────
  conversation: {
    activeConversations: '进行中的会话',
    newChat: '新建聊天',
    pinned: '已置顶',
    recent: '最近',
    archived: '已归档',
    rename: '重命名会话',
    enterNewName: '请输入新名称',
    deleteConfirm: '确认删除该会话？此操作不可恢复。',
    deleteTitle: '删除会话',
    deleteFailed: '删除失败，请重试',
    unnamedSession: '未命名会话',
  },

  // ─── 聊天 ─────────────────────────────────────────────────────────────────────
  chat: {
    selectOrCreate: '从左侧选择或新建聊天',
    noSessionOpen: '请先打开或创建一个会话',
    uploadFailed: '文件上传失败，请重试',
    uploadInProgress: '文件上传中，请稍候',
    archivedNotice: '该会话已归档，无法继续发送消息',
    feedbackFailed: '反馈提交失败，请重试',
    feedbackWithdrawn: '已撤销反馈',
    feedbackThumbsUp: '👍 反馈已提交',
    feedbackThumbsDown: '👎 反馈已提交',
    messageRead: '已读',
  },

  // ─── 会话设置抽屉 ─────────────────────────────────────────────────────────────
  conversationSettings: {
    title: '会话设置',
    members: '群成员 (',
    addMember: '添加成员',
    noAgentsToAdd: '没有可添加的 Agent',
    orchestratorLabel: '系统 · 群主',
    tokenUsage: 'Token 用量',
    totalToken: '总 Token 用量',
    inputToken: '输入',
    outputToken: '输出',
    messages: '条',
    noTokenUsage: '本会话还没有 token 消耗',
    refreshUsage: '刷新用量',
    memberAdded: '已添加',
    addFailed: '添加失败,请重试',
    memberRemoved: '已移除',
    removeFailed: '移除失败,请重试',
    sessionSettingsTitle: '会话设置(成员 / Token 用量)',
    settings: '群聊设置',
  },

  // ─── 新建聊天对话框 ────────────────────────────────────────────────────────────
  newChat: {
    noPresetMembers: '暂无预设成员',
    taskModeDesc: 'Orchestrator 统筹任务',
    broadcastModeDesc: '闲聊，各自回复',
  },

  // ─── 状态栏 ──────────────────────────────────────────────────────────────────
  chatStatus: {
    oneAgentReplying: '1 个 Agent 正在回复',
    multiAgentParallel: '个 Agent 并行中',
    multiAgentIdle: '个 Agent · 待命',
  },

  // ─── Agent 气泡 ───────────────────────────────────────────────────────────────
  agentBubble: {
    thinking: '思考中',
    typing: '回复中',
    toolPrefix: '调用 ',
    toolFallback: '调用工具',
    idle: '等待中',
    reactionLike: '已点赞',
    reactionDislike: '已点踩',
  },

  // ─── 折叠内容 ─────────────────────────────────────────────────────────────────
  collapsible: {
    collapse: '收起',
    expandAll: '展开全部',
  },

  // ─── 审批 Block ────────────────────────────────────────────────────────────────
  approval: {
    approved: '已批准',
    approvedAt: '已批准于 {time}',
    rejected: '已拒绝',
    rejectedAt: '已拒绝于 {time}',
    waitingApproval: '等待审批...',
    rejectReasonPlaceholder: '拒绝原因（可选）',
    approveButton: '批准 (Y)',
    rejectButton: '拒绝 (N)',
    confirmReject: '确认',
    keyboardHint: '按 Y / N',
    hideContent: '收起内容',
    showContent: '展开内容',
    hideDiff: '收起 Diff',
    showDiff: '展开 Diff',
    hideDetails: '收起详情',
    showDetails: '展开详情 ({size})',
    lineCount: '{n} 行',
    labelOld: '- 旧',
    labelNew: '+ 新',
  },

  // ─── 工具调用 Block ────────────────────────────────────────────────────────────
  toolUse: {
    labelInput: '输入：',
    labelOutput: '输出：',
    executing: '执行中...',
  },

  // ─── 思考 Block ────────────────────────────────────────────────────────────────
  thinking: {
    label: '思考中',
  },

  // ─── 代码 Block ────────────────────────────────────────────────────────────────
  codeBlock: {
    preview: '预览',
    applying: '应用中…',
    applied: '已应用 ✓',
    failed: '失败 ✗',
    apply: '应用',
    copied: '已复制!',
    copy: '复制',
    collapseLines: '收起（{n} 行）',
    showAllLines: '展开全部 {n} 行',
  },

  // ─── 部署 Block ────────────────────────────────────────────────────────────────
  deploymentBlock: {
    labelLogs: '日志：',
    deploying: '部署中...',
    failed: '部署失败',
  },

  // ─── 预览卡片 ─────────────────────────────────────────────────────────────────
  previewCard: {
    fullPreview: '全屏预览',
  },

  // ─── 部署视图 ─────────────────────────────────────────────────────────────────
  deployments: {
    emptyTitle: '还没有部署',
    emptyDesc: '让主 Agent 调 deploy_app 工具，部署应用后会出现在这里',
    running: '运行中',
    urlLabel: 'URL：',
    copyUrl: '复制 URL',
    openInTab: '新标签打开',
    refresh: '刷新',
    historyLabel: '部署历史 (',
    latestFailed: '最近部署失败',
    unknownError: '未知错误',
    deployFailed: '部署失败',
  },

  // ─── Workflow 视图 ────────────────────────────────────────────────────────────
  workflow: {
    emptyTitle: '等待 Agent 运行',
    emptyDesc: '发送消息后将在此处实时展示执行流程',
    agentUnit: '个 Agent',
    done: '完成',
    error: '失败',
    cancelled: '已取消',
    currentRound: '本轮',
    pendingHint: '等待依赖任务完成后启动',
    waitingApproval: '等待用户审批',
    roundDone: '本轮完成',
    blockText: '输出文本',
    blockThinking: '思考中',
    blockCode: '生成代码',
    blockImage: '图像',
    blockApproval: '等待审批',
    blockDeployment: '部署',
    blockArtifacts: '产出物',
  },

  // ─── Agent 面板 ───────────────────────────────────────────────────────────────
  agentsPanel: {
    title: 'Agents',
    emptyTitle: '还没有 Agent',
    emptyDesc: '创建你的第一个 AI Agent 开始使用，每个 Agent 可拥有独特的技能和行为。',
    createAgent: '创建 Agent',
    noMatch: '没有符合搜索条件的 Agent',
    filterAll: '全部',
    filterActive: '活跃',
    filterClaude: 'Claude',
    filterCodex: 'Codex',
    filterCustom: '自定义',
    noDescription: '暂无描述',
    tooltipActive: '活跃',
    tooltipInactive: '已禁用',
  },

  // ─── Skills 面板 ──────────────────────────────────────────────────────────────
  skillsPanel: {
    title: '技能',
    emptyTitle: '还没有技能',
    emptyDesc: '创建你的第一个技能，为 Agent 定义可复用的知识和行为。',
    createSkill: '创建技能',
    noMatch: '没有符合筛选条件的技能',
    filterAll: '全部',
    noDescription: '暂无描述',
    tooltipActive: '活跃',
    tooltipInactive: '已禁用',
    uncategorized: '未分类',
  },

  // ─── Sandbox 文件视图 ──────────────────────────────────────────────────────────
  sandboxFiles: {
    toolbarLabel: '沙盒',
    toolbarFile: '个文件',
    toolbarFiles: '个文件',
    tooltipLoading: '加载中',
    tooltipRefresh: '刷新',
    noConversation: '未选择会话',
    loadFailed: '文件加载失败',
    emptyTitle: '还没有文件',
    emptyDesc: '当 Agent 在本会话中创建文件后，会显示在这里。',
    tooltipPreview: '预览',
    tooltipEdit: '编辑',
    tooltipDownload: '下载',
  },

  // ─── Agent 联系人列表 ──────────────────────────────────────────────────────────
  agentContacts: {
    activeAgents: '活跃 Agents',
    newAgent: '新建 Agent',
    noDescription: '暂无描述',
  },

  // ─── Agent Builder 对话框 ─────────────────────────────────────────────────────
  agentBuilder: {
    title: '用 AI 构建 Agent',
    subtitle: '描述你的 Agent，AI 将自动生成配置',
    inputPlaceholder: '描述你想创建的 Agent...',
    greetingInitial: '你好！描述你想构建的 Agent，我将为你生成配置。例如："一个专业处理退款请求的客服 Agent。"',
    greetingSimple: '你好！描述你想构建的 Agent，我将为你生成配置。',
    draftConfirmation: '已为你草拟了名为"{name}"的 Agent。你可以在上方查看，点击"使用此 Agent"创建它，或继续对话以调整。',
    errorGeneration: '抱歉，生成 Agent 配置时出错，请重试。',
    errorBuildFailed: '构建请求失败',
    cancel: '取消',
    useAgent: '使用此 Agent',
  },

  // ─── Agent 表单 ───────────────────────────────────────────────────────────────
  agentForm: {
    namePlaceholder: 'Agent 名称',
    nameHelper: '给你的 Agent 取一个好记的名字',
    descriptionLabel: '描述',
    descriptionPlaceholder: '简要描述此 Agent 的职责...',
    platformLabel: '平台',
    skillsLabel: '技能',
    addMoreSkills: '添加更多技能',
    selectSkills: '选择技能',
    capabilitiesGroup: '能力',
    skillsGroup: '技能',
    loadingSkills: '加载中...',
    noSkillsAvailable: '暂无可用技能',
    systemPromptLabel: '系统提示词',
    markdownSupported: '支持 Markdown',
    systemPromptPlaceholder: '### 目标\n定义 Agent 应完成的任务...\n### 技能\n列出 Agent 的核心能力...\n### 工作流\n描述 Agent 的工作方式...\n### 约束\n设定边界和限制...',
    tagsLabel: '标签',
    addTagPlaceholder: '添加标签...',
    addTagHelper: '按 Enter 添加标签',
    visibilityLabel: '可见性',
    publicAgent: '公开 Agent',
    publicAgentDesc: '允许其他用户发现并使用此 Agent',
    statusLabel: '状态',
    activeLabel: '活跃',
    disabledAgentDesc: '已禁用的 Agent 无法用于对话',
    skillCodeExecution: '代码执行',
    skillDiffReview: 'Diff 审查',
    skillApprovalFlow: '审批流',
    skillImageProcessing: '图像处理',
  },

  // ─── Skill 表单 ───────────────────────────────────────────────────────────────
  skillForm: {
    namePlaceholder: 'skill-name',
    nameHelper: '英文标识符（小写字母、数字、连字符、下划线）',
    displayNameLabel: '显示名称',
    displayNamePlaceholder: '中文名称（可选）',
    descriptionLabel: '描述',
    descriptionPlaceholder: '简要描述此技能的作用...',
    categoryLabel: '分类',
    selectCategory: '选择分类',
    contentLabel: '内容',
    markdownSupported: '支持 Markdown',
    contentPlaceholder: '### 概述\n描述技能的目的和范围...\n### 说明\n为 Agent 提供分步指导...\n### 示例\n提供输入/输出示例...\n### 约束\n设定边界和限制...',
    visibilityLabel: '可见性',
    publicSkill: '公开技能',
    publicSkillDesc: '允许其他用户发现并使用此技能',
    statusLabel: '状态',
    activeLabel: '活跃',
    disabledSkillDesc: '已禁用的技能无法被 Agent 选择',
    categoryCode: '代码',
    categorySecurity: '安全',
    categoryDomainKnowledge: '领域知识',
    categoryGeneral: '通用',
  },

  // ─── SSE 错误 ─────────────────────────────────────────────────────────────────
  sse: {
    errorPrefix: '[错误] ',
  },

  // ─── 审批浮层（Overlay） ───────────────────────────────────────────────────────
  approvalOverlay: {
    title: '等待审批',
  },

  // ─── 消息操作 ─────────────────────────────────────────────────────────────────
  messageActions: {
    like: '点赞',
    dislike: '点踩',
    reply: '回复',
    copy: '复制',
  },

  // ─── 相对时间 ─────────────────────────────────────────────────────────────────
  timeAgo: {
    justNow: '刚刚',
    minutesAgo: '{n}分钟前',
    hoursAgo: '{n}小时前',
  },

  // ─── 导航栏（扩展） ───────────────────────────────────────────────────────────
  navExtra: {
    search: '搜索',
    support: '关于',
    settings: '设置',
    collapse: '收起',
    chatLabel: '聊天',
    agentsLabel: 'Agents',
    skillsLabel: '技能',
    searchDialogTitle: '搜索',
    searchDialogConfirm: '搜索',
    searchDialogPlaceholder: '搜索会话、Agent、技能...',
  },

  // ─── Agent 表单面板 ───────────────────────────────────────────────────────────
  agentFormPanel: {
    editTitle: '编辑 Agent',
    createTitle: '新建 Agent',
    readonlyTag: '（只读）',
    readonlyBuiltin: '内置 Agent 不可修改',
    readonlyOther: '无权修改他人创建的 Agent',
    delete: '删除',
    cancel: '取消',
    saveChanges: '保存修改',
    createAgent: '新建 Agent',
    loadFailed: '加载 Agent 失败',
    deleteConfirm: '确认删除 Agent "{name}"？此操作不可恢复。',
    deleteTitle: '删除 Agent',
    deleted: 'Agent 已删除',
    deleteFailed: '删除失败',
    nameRequired: 'Agent 名称不能为空',
    updated: 'Agent 已更新',
    created: 'Agent 已创建',
    saveFailed: '保存失败',
  },

  // ─── Skill 表单面板 ──────────────────────────────────────────────────────────
  skillFormPanel: {
    editTitle: '编辑技能',
    createTitle: '新建技能',
    readonlyTag: '（只读）',
    readonlyBuiltin: '内置 Skill 不可修改',
    readonlyOther: '无权修改他人创建的 Skill',
    delete: '删除',
    cancel: '取消',
    saveChanges: '保存修改',
    createSkill: '新建技能',
    loadFailed: '加载技能失败',
    deleteConfirm: '确认删除技能 "{name}"？此操作不可恢复。',
    deleteTitle: '删除技能',
    deleted: '技能已删除',
    deleteFailed: '删除失败',
    nameRequired: '技能名称不能为空',
    nameFormat: '技能名称只允许小写字母、数字、连字符或下划线',
    contentRequired: '技能内容不能为空',
    updated: '技能已更新',
    created: '技能已创建',
    saveFailed: '保存失败',
  },

  // ─── 右侧面板 ─────────────────────────────────────────────────────────────────
  rightPanel: {
    view: '预览',
    edit: '编辑',
    closePreview: '关闭预览（返回上一个标签）',
    running: '运行中',
    idle: '待命',
    tabWorkflow: 'Workflow',
    tabFiles: '文件',
    tabDeploy: '部署',
    tabPreview: '预览',
    titleFiles: '文件',
    titleDeployments: '部署',
    titleWorkflow: 'Workflow',
  },

  // ─── 设置对话框 ───────────────────────────────────────────────────────────────
  settings: {
    title: '设置',
    accentColor: '主题色',
    language: '语言',
    langChinese: '中文',
    langEnglish: 'English',
  },

  // ─── 新建聊天对话框（扩展） ──────────────────────────────────────────────────
  newChatExtra: {
    title: '新建聊天',
    subtitle: '配置你的会话',
    squadTemplates: '小队模板',
    chatTitleLabel: '标题',
    chatTitlePlaceholder: '输入聊天标题...',
    modeLabel: '模式',
    taskMode: '任务',
    broadcastMode: '广播',
    inviteAgents: '邀请 Agents',
    addMoreAgents: '添加更多 Agents',
    selectAgents: '选择 Agents',
    searchAgents: '搜索 Agents...',
    noAgentsAvailable: '暂无可用 Agent',
    creating: '创建中...',
    createChat: '创建聊天',
  },

  // ─── 聊天输入（扩展） ────────────────────────────────────────────────────────
  chatInputExtra: {
    replyingTo: '回复 {name}',
    filesAttached: '已附件 {n} 个文件',
    attachFiles: '附件（上传到会话沙箱）',
    placeholder: '输入消息...',
  },

  // ─── 会话列表项 ──────────────────────────────────────────────────────────────
  convItem: {
    noMessages: '暂无消息',
    rename: '重命名',
    unpin: '取消置顶',
    pin: '置顶',
    unarchive: '取消归档',
    archive: '归档',
    delete: '删除',
  },

  // ─── Element Plus 组件语言 ────────────────────────────────────────────────────
  lang: '简体中文',
}
