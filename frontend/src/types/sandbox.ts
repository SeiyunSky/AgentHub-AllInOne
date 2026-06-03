// 会话沙箱文件(runtime/memory/{user_id}/{conversation_id}/ 下递归列出)
// path 是相对沙箱根的 POSIX 风格路径,即 create_file 工具返回的 path 字段
export interface SandboxFileNode {
  name: string
  path: string
  size: number
  mtime: number   // unix seconds (float)
  isDir: boolean
}
