import { http } from './http'

// 与 backend/schemas/auth.py 对齐
export interface UserPublic {
  id: string
  username: string
  email?: string | null
  display_name?: string | null
  last_login_at?: string | null
  created_at?: string | null
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: UserPublic
}

export interface LoginPayload {
  username: string
  password: string
}

export interface RegisterPayload {
  username: string
  password: string
  email?: string
  display_name?: string
}

export const authApi = {
  /** POST /api/v1/auth/login -> TokenResponse */
  login(payload: LoginPayload): Promise<TokenResponse> {
    return http.post('/auth/login', payload) as unknown as Promise<TokenResponse>
  },

  /** POST /api/v1/auth/logout -> 204 (envelope -> null) */
  logout(): Promise<void> {
    return http.post('/auth/logout') as unknown as Promise<void>
  },

  /** POST /api/v1/auth/refresh -> TokenResponse (refresh_token 沿用旧的) */
  refresh(refreshToken: string): Promise<TokenResponse> {
    return http.post('/auth/refresh', { refresh_token: refreshToken }) as unknown as Promise<TokenResponse>
  },

  /** GET /api/v1/auth/me -> UserPublic */
  me(): Promise<UserPublic> {
    return http.get('/auth/me') as unknown as Promise<UserPublic>
  },

  /** POST /api/v1/auth/register -> UserPublic (201) */
  register(payload: RegisterPayload): Promise<UserPublic> {
    return http.post('/auth/register', payload) as unknown as Promise<UserPublic>
  },

  /** GET /api/v1/auth/oauth/microsoft -> { url: string } */
  getMicrosoftOAuthUrl(): Promise<{ url: string }> {
    return http.get('/auth/oauth/microsoft') as unknown as Promise<{ url: string }>
  },
}

