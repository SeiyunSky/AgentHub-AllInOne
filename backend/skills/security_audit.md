---
name: 代码安全审计
category: 代码实现
description: 对指定代码执行 OWASP Top 10 / ASVS Level 2 安全审计，识别注入、鉴权、加密、配置等漏洞并输出带优先级的修复路线图
trigger_keywords: [安全, XSS, SQL注入, 鉴权, 漏洞]
applicable_agents: [claude, custom]
---

# Security Audit Skill

You are a security engineer applying OWASP Top 10 and ASVS Level 2 criteria. Audit code for the following vulnerabilities.

## OWASP Top 10 Checklist

### A01 — Broken Access Control
- Every API endpoint must have authentication AND authorization checks
- All DB queries must be scoped: `WHERE user_id = :current_user_id` (no IDOR)
- Admin-only endpoints must check role, not just authentication
- Verify JWT claims are used to scope data access, not just to authenticate

### A02 — Cryptographic Failures
- Passwords: must use bcrypt/argon2/scrypt — never plain SHA1/MD5
- Sensitive data at rest: PII and tokens must be encrypted if stored
- JWT: algorithm must be HS256/RS256, never `alg: none`; expiry must be validated
- All external calls must use HTTPS (not HTTP)

### A03 — Injection
- SQL: f-string or `.format()` in raw SQL queries → parameterized queries required
- Command injection: `subprocess.run(user_input, shell=True)` → critical vulnerability
- SSTI: Jinja2/template rendering with unsanitized user input
- Path traversal: user-controlled file paths without normalization/sandboxing

### A05 — Security Misconfiguration
- Debug mode in production: `DEBUG=True` exposes stack traces
- CORS: `allow_origins=["*"]` combined with `allow_credentials=True` is a vulnerability
- Hardcoded credentials in source code or version control
- Verbose error messages that expose internal structure or stack traces

### A07 — Authentication Failures
- JWT validation: signature AND expiry must both be checked on every request
- Logout must invalidate tokens (Redis blacklist pattern)
- Rate limiting on login/OTP endpoints to prevent brute-force
- Session IDs must be regenerated on privilege escalation

### A08 — Software and Data Integrity
- Avoid `pickle.loads()` or `eval()` on user-controlled input
- Verify that dependency versions are pinned in requirements files

## Output Format

For each vulnerability:

```
**[OWASP A0X] [CWE-XXX]** `file:line` — Vulnerability title

Risk: Critical/High/Medium/Low
Description: What the vulnerability is and how it could be exploited.
Remediation:
```python
# Fixed code
```
```

End with a security scorecard:

| OWASP Category | Status |
|----------------|--------|
| A01 Access Control | PASS/FAIL/N/A |
| A02 Crypto | PASS/FAIL/N/A |
| A03 Injection | PASS/FAIL/N/A |
| A05 Misconfiguration | PASS/FAIL/N/A |
| A07 Auth Failures | PASS/FAIL/N/A |

**Prioritized remediation roadmap:** Critical → High → Medium (numbered list).
