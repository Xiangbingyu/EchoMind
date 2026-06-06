# 用户登录与 Security 模块详细方案

## 目标

为一期后端补齐第一个可直接落地的业务板块：用户登录与请求鉴权。

本方案聚焦两件事：

- 构建 `user` 模块中的登录业务闭环
- 构建独立 `security` 模块，对后续请求中 Cookie 携带的 token 做统一解析、校验与身份注入

该方案严格遵循当前一期已确认边界：

- 技术栈沿用 `FastAPI + PostgreSQL + Redis + JWT + Cookie`
- 一期只做 `用户名 + 密码` 登录
- 首个登录账号通过 seed 脚本初始化
- 同域部署，认证信息通过 `HttpOnly Cookie` 传递
- 一期只做短期 `access token`，不做 `refresh token`
- 允许同一账号多端同时登录
- 最小 CSRF 防护采用 `Origin/Referer` 校验
- 每次请求都要校验用户状态，`disabled/locked` 用户不可继续访问

## 设计范围

本方案覆盖：

- `/api/v1/auth/login`
- `/api/v1/auth/logout`
- `/api/v1/auth/me`
- 受保护接口的登录态校验
- Cookie 中 access token 的签发、解析、失效判断
- `security` 模块的统一鉴权依赖与请求过滤能力
- 登录相关 Redis key 设计
- 登录相关错误码与异常约定

本方案暂不覆盖：

- 用户注册
- refresh token
- 第三方登录
- RBAC/角色权限系统
- 跨站 Cookie 方案
- 设备管理页、登录记录页

## 总体思路

一期采用“`user` 负责登录业务，`security` 负责请求鉴权”的职责切分。

具体来说：

- `user` 模块负责账号查询、密码校验、JWT 签发、登录登出业务编排
- `security` 模块负责从请求 Cookie 中提取 token、校验 JWT、查询 Redis token 状态、校验用户状态、把当前用户注入请求上下文
- 业务模块不直接解析 JWT，也不直接操作 Cookie 中的 token
- 业务接口统一通过 `security` 暴露的依赖获取当前登录用户

这样做的目的：

- 保持 `user` 模块专注身份与登录态业务
- 保持 `security` 模块专注请求入口处的认证过滤
- 后续新增更多需要登录保护的模块时，可以直接复用 `security` 能力
- 后续若需要扩展 refresh token、角色权限、API key，也有明确扩展点

## 模块边界

### `user` 模块职责

`user` 模块负责身份真源与登录业务闭环。

建议职责：

- 根据 `username` 查询用户
- 校验密码哈希
- 校验用户是否允许登录
- 生成 JWT access token
- 为每次登录生成唯一 `jti`
- 登录成功后写入 Redis token 状态
- 登录成功后更新 `users.last_login_at`
- 登出时将当前 token 对应 `jti` 标记失效
- 对外暴露 `AuthService` 作为登录业务入口

`user` 模块不负责：

- 每个请求中的 token 提取与解析
- `Origin/Referer` 校验
- 将当前用户注入 FastAPI 请求依赖

这些职责统一放到 `security` 模块。

### `security` 模块职责

`security` 模块是独立认证入口模块，负责“请求进来之后，如何识别当前用户”。

建议职责：

- 从 Cookie 中读取 access token
- 校验 JWT 签名、过期时间、必要 claims
- 从 token 中解析 `sub(user_id)` 与 `jti`
- 查询 Redis 中 `auth:token:{jti}` 的状态
- 校验 token 是否仍然有效
- 查询用户并校验 `status`
- 在受保护接口中提供 `current_user` / `current_user_id` 依赖
- 对写接口执行 `Origin/Referer` 校验
- 统一抛出未登录、token 无效、用户被禁用等认证异常

`security` 模块不负责：

- 用户名密码登录逻辑
- 密码哈希生成
- 登录成功后的审计持久化业务编排

## 推荐目录结构

这两个模块一期不适合拆太细。

如果一开始就把 `jwt_service.py`、`password_service.py`、`token_resolver.py`、`exceptions.py` 这类文件全部拆开，虽然看起来分层完整，但对于一期登录场景来说会明显增加跳转成本，职责也容易被切碎。

更适合一期的做法是：

- `user` 模块只保留登录业务闭环相关文件
- `security` 模块只保留请求认证入口相关文件
- 能放在同一个文件内收口的逻辑，先不要过早拆成很多“service / resolver / manager”文件

建议目录调整为：

```text
backend/
  app/
    modules/
      user/
        api.py
        service.py
        repository.py
        schemas.py
        domain.py

      security/
        deps.py
        service.py
        csrf.py
        schemas.py
```

说明：

- `user/api.py` 暴露 `/api/v1/auth/*`
- `user/service.py` 负责登录、登出、获取 `me`，并内聚处理密码校验、token 签发、Redis 登录态写入等登录业务逻辑
- `user/repository.py` 负责 `users` 表查询与 `last_login_at` 更新
- `user/schemas.py` 负责登录请求、登录响应、`me` 响应等接口模型
- `user/domain.py` 负责 `User` 相关最小领域对象与状态语义
- `security/deps.py` 负责向其他模块暴露 `require_current_user`、`require_current_user_id` 之类的依赖
- `security/service.py` 统一负责 Cookie 取 token、JWT 校验、Redis token 状态校验、用户状态校验、认证上下文组装
- `security/csrf.py` 负责同域条件下的 `Origin/Referer` 校验
- `security/schemas.py` 负责 `AccessTokenClaims`、`AuthenticatedUser` 这类认证上下文对象

这样调整后的核心思路是：

- 登录业务相关逻辑尽量收口在 `user/service.py`
- 请求级鉴权相关逻辑尽量收口在 `security/service.py`
- 一期先不单独拆 `jwt_service.py`、`password_service.py`、`token_resolver.py`、`exceptions.py`

只有在以下情况出现时，再考虑继续细拆：

- 认证方式出现第二种实现
- 密码策略明显变复杂
- token 类型不再只有 access token
- `security/service.py` 已经膨胀到明显难以维护

### 为什么这样更合适

相较于上一版结构，这一版更适合一期的原因是：

- 文件数更少，认知负担更低
- `user` 和 `security` 的边界仍然清晰，没有混在一起
- 重要实现点集中，开发时不需要在过多文件之间来回跳转
- 后续如果复杂度上升，再从 `service.py` 里向外拆能力，迁移成本也低

### 文件内职责建议

为了避免“文件少了但文件内容失控”，建议把每个文件的边界写死：

`user/service.py` 负责：

- `login`
- `logout`
- `get_me`
- 用户状态登录前校验
- 密码校验
- access token 签发
- Redis token 写入与删除

`security/service.py` 负责：

- 从请求 Cookie 中提取 token
- 校验 JWT claims
- 查询 Redis token 状态
- 查询用户并校验状态
- 构造 `AuthenticatedUser`

这样既减少文件数量，也不会让职责再次混乱。

## 核心对象

### User

沿用已有领域对象：

- `id`
- `username`
- `password_hash`
- `status`
- `last_login_at`

一期建议用户状态只使用以下值：

- `active`
- `disabled`
- `locked`

规则：

- `active`：允许登录、允许访问受保护接口
- `disabled`：拒绝登录，也拒绝已登录 token 继续访问
- `locked`：拒绝登录，也拒绝已登录 token 继续访问

### AccessTokenClaims

一期 access token 建议最少包含以下 claims：

- `sub`：用户 ID，字符串形式
- `jti`：token 唯一标识
- `exp`：过期时间

建议补充以下 claims，便于后续排查和扩展：

- `iat`：签发时间
- `type`：固定为 `access`

示例：

```json
{
  "sub": "1001",
  "jti": "01JXYZ...",
  "type": "access",
  "iat": 1770000000,
  "exp": 1770007200
}
```

### AuthenticatedUser

`security` 模块内部建议定义轻量认证上下文对象：

- `user_id`
- `username`
- `status`
- `jti`

用途：

- 作为请求认证后的标准结果
- 避免每个业务模块直接依赖完整 ORM 对象

## 认证数据流

### 1. 登录流程

`POST /api/v1/auth/login` 的建议处理流程：

1. `user/api.py` 接收 `username`、`password`
2. `AuthService.login()` 根据 `username` 查询用户
3. 如果用户不存在，返回登录失败
4. 如果用户状态不是 `active`，返回登录失败
5. `user/service.py` 内部完成密码哈希校验
6. 生成新的 `jti`
7. `user/service.py` 内部生成 access token
8. 将 `auth:token:{jti}` 写入 Redis，并设置 TTL 为 token 剩余有效期
9. 更新 `users.last_login_at`
10. 写登录成功审计日志
11. 通过 `Set-Cookie` 将 access token 写入 HttpOnly Cookie
12. 返回最小登录成功响应

登录失败流程：

- 用户不存在、密码错误、用户状态异常，都返回统一的登录失败语义
- 不向前端暴露“用户名不存在”还是“密码错误”的细粒度差异
- 登录失败也建议记审计日志，但不泄露过多内部细节

### 2. 请求鉴权流程

受保护接口的建议处理流程：

1. 路由通过 `security.deps.require_current_user` 声明登录依赖
2. `security` 从请求 Cookie 中读取 access token
3. 如果 Cookie 缺失，抛出未登录异常
4. 校验 JWT 签名、`exp`、`sub`、`jti`、`type`
5. 根据 `jti` 查询 Redis 中 `auth:token:{jti}`
6. 如果 Redis 中不存在该 key，则视为 token 已失效或已登出
7. 如果 Redis 中状态不是有效态，则拒绝访问
8. 根据 `sub` 查询用户
9. 如果用户不存在或状态不是 `active`，拒绝访问
10. 构造 `AuthenticatedUser` 返回给业务接口

### 3. 登出流程

`POST /api/v1/auth/logout` 的建议处理流程：

1. 先通过 `require_current_user` 确保当前请求已经登录
2. 从当前认证上下文中拿到 `jti`
3. 删除或失效 Redis 中的 `auth:token:{jti}`
4. 写登出审计日志
5. 返回响应时清理 access token Cookie

说明：

- 一期允许多端登录，所以登出只让“当前 token”失效
- 不做“注销全部设备”接口

### 4. `me` 流程

`GET /api/v1/auth/me` 的建议处理流程：

1. 通过 `require_current_user` 完成鉴权
2. 返回当前最小身份信息
3. 不聚合 profile 信息

返回字段建议：

- `user_id`
- `username`
- `status`

## Cookie 设计

一期采用同域 HttpOnly Cookie。

建议 Cookie 名称：

- `em_access_token`

建议属性：

- `HttpOnly = true`
- `Secure = true`：生产环境开启；本地开发可按环境配置决定
- `SameSite = Lax`
- `Path = /`
- `Max-Age` 与 JWT `exp` 保持一致

说明：

- 一期是同域部署，`SameSite=Lax` 足以作为基础保护
- 由于 token 放在 HttpOnly Cookie，中前端 JS 不需要也不应该读取 token
- 前端只负责带上 Cookie 发请求

## JWT 设计

### 签发策略

一期建议仅签发 access token。

建议有效期：

- `1~2 小时`

建议默认收口为：

- `2 小时`

原因：

- 一期不做 refresh token，过短会导致体验太差
- 过长又会拉大 token 泄露后的风险窗口
- 2 小时是一个偏稳妥的一期折中值

### 载荷字段

最小字段：

- `sub`
- `jti`
- `exp`

建议字段：

- `iat`
- `type=access`

### 校验规则

`security` 模块在校验 token 时至少检查：

- 签名合法
- `exp` 未过期
- `sub` 存在且可解析为用户 ID
- `jti` 存在
- `type` 为 `access`

任何一项失败，都应统一视为未登录或无效 token。

## Redis 设计

### Key 设计

沿用一期总方案：

- `auth:token:{jti}`

### Value 设计

一期建议 value 保持轻量，采用 JSON 或 hash 均可。

推荐最小字段：

- `user_id`
- `status`
- `expires_at`

示例：

```json
{
  "user_id": 1001,
  "status": "active",
  "expires_at": "2026-05-17T12:00:00Z"
}
```

### 状态约定

一期建议只使用最小状态集合：

- `active`
- `revoked`

实际实现建议：

- 登录成功时写入 `active`
- 登出时直接删除 key，或短暂改为 `revoked`

更推荐的一期实现：

- 直接删除 key

原因：

- 一期不需要复杂黑名单历史
- key 是否存在即可表达 token 是否仍有效
- Redis 占用和判断逻辑都更简单

因此，一期的实际判断规则可以收口为：

- JWT 合法且 Redis key 存在：认为 token 有效
- JWT 合法但 Redis key 不存在：认为 token 已登出、已过期或已失效

### TTL 设计

Redis key 的 TTL 应与 token 剩余有效期一致。

规则：

- token 签发时，`TTL = exp - now`
- token 到期后，Redis key 自动过期

这样可以避免数据库保存登录态，也不需要额外清理任务。

## CSRF 与请求来源校验

一期使用 Cookie 认证，因此写接口必须补最小 CSRF 防护。

当前已确认只做：

- `Origin/Referer` 校验

### 校验范围

建议对所有会修改状态的接口执行校验：

- `POST`
- `PUT`
- `PATCH`
- `DELETE`

建议至少覆盖：

- `/api/v1/auth/login`
- `/api/v1/auth/logout`
- `/api/v1/chat/*`
- `/api/v1/sessions/*` 的写接口
- `/api/v1/models/switch`
- `/api/v1/profile/refresh`

### 校验规则

同域部署下一期建议规则：

1. 如果请求方法是只读方法，例如 `GET`、`HEAD`、`OPTIONS`，默认不做该校验
2. 如果请求方法是写方法，则优先读取 `Origin`
3. `Origin` 存在时，必须与后端允许域完全匹配
4. `Origin` 缺失时，可回退校验 `Referer`
5. `Referer` 存在时，也必须属于同域可信地址
6. 两者都缺失时，拒绝请求

说明：

- 一期不做独立 CSRF token
- 但要明确把 `Origin/Referer` 校验做成 `security` 模块内统一能力，避免业务接口各自散落实现

## 接口设计

### 1. `POST /api/v1/auth/login`

用途：

- 用户使用账号密码登录
- 登录成功后由后端写入 access token Cookie

请求体建议：

```json
{
  "username": "alice",
  "password": "plain-text-password"
}
```

成功响应建议：

```json
{
  "user_id": 1001,
  "username": "alice",
  "status": "active"
}
```

响应行为：

- 设置 `Set-Cookie: em_access_token=...; HttpOnly; Path=/; SameSite=Lax`

失败语义：

- 账号或密码错误
- 用户已禁用或已锁定
- 请求来源不合法

### 2. `POST /api/v1/auth/logout`

用途：

- 使当前 token 失效并清理 Cookie

请求体：

- 无

成功响应建议：

```json
{
  "success": true
}
```

响应行为：

- 清理 `em_access_token` Cookie

### 3. `GET /api/v1/auth/me`

用途：

- 返回当前登录用户的最小身份信息

成功响应建议：

```json
{
  "user_id": 1001,
  "username": "alice",
  "status": "active"
}
```

说明：

- 不返回 profile 聚合信息
- 前端如果要展示昵称，后续应调用 profile 模块接口

## `security` 模块公开能力设计

为了让其他模块少关心认证细节，`security` 模块建议只暴露有限的公开入口。

### FastAPI 依赖

建议提供：

- `require_current_user()`
- `require_current_user_id()`
- `enforce_same_origin_for_write()`

含义：

- `require_current_user()`：返回认证后的 `AuthenticatedUser`
- `require_current_user_id()`：只返回当前用户 ID，给只需要用户标识的接口用
- `enforce_same_origin_for_write()`：用于写接口做来源校验

### Service 方法边界

建议 `security/service.py` 对内提供：

- `authenticate_request(request) -> AuthenticatedUser`
- `validate_token(token) -> AccessTokenClaims`
- `assert_token_active(jti, user_id) -> None`
- `assert_user_active(user) -> None`
- `assert_same_origin(request) -> None`

这样其余业务模块只依赖稳定方法边界，不需要自己拼认证细节。

## `user` 模块服务边界设计

建议 `AuthService` 暴露如下方法：

- `login(username, password) -> LoginResult`
- `logout(current_user) -> None`
- `get_me(current_user) -> MeResult`

内部协作关系建议：

- `AuthService` 调用 `UserRepository` 查询用户
- `AuthService` 在模块内完成密码校验
- `AuthService` 在模块内完成 token 签发
- `AuthService` 调用 Redis token store 写入或删除 token 状态

说明：

- `me` 接口虽然很简单，仍建议通过 `AuthService` 暴露，保持模块公开入口统一

## 数据访问边界

### 数据库

登录模块一期只依赖 `users` 表。

核心读写：

- 按 `username` 查用户
- 按 `id` 查用户
- 更新 `last_login_at`

不新增数据库 token 表。

### Redis

登录态只写 Redis，不写数据库主表。

核心操作：

- `set auth:token:{jti}`
- `get auth:token:{jti}`
- `delete auth:token:{jti}`

## 错误码设计

一期建议把“认证失败”和“业务失败”分开。

### HTTP 状态码建议

- `400 Bad Request`：请求参数错误
- `401 Unauthorized`：未登录、token 无效、token 过期、cookie 缺失
- `403 Forbidden`：来源校验失败、用户被禁用、用户被锁定

### 业务错误码建议

建议最少定义以下错误码：

- `AUTH_INVALID_CREDENTIALS`：用户名或密码错误
- `AUTH_UNAUTHENTICATED`：未登录
- `AUTH_TOKEN_INVALID`：token 非法或 claims 不完整
- `AUTH_TOKEN_EXPIRED`：token 已过期
- `AUTH_TOKEN_REVOKED`：token 已失效或已登出
- `AUTH_USER_DISABLED`：用户已禁用
- `AUTH_USER_LOCKED`：用户已锁定
- `AUTH_ORIGIN_NOT_ALLOWED`：请求来源不被允许

建议原则：

- 登录接口对前端展示时，可把 `AUTH_INVALID_CREDENTIALS`、`AUTH_USER_DISABLED`、`AUTH_USER_LOCKED` 收口成统一文案
- 但后端内部日志和审计记录里仍保留真实原因，便于排障

## 审计建议

结合一期最小审计要求，登录模块至少记录：

- 登录成功
- 登录失败
- 登出

建议 `audit_logs.action`：

- `auth.login.succeeded`
- `auth.login.failed`
- `auth.logout.succeeded`

建议 `metadata_json` 至少记录：

- `username`
- `reason`（失败时）
- `jti`（成功或登出时）

由于你当前未要求一期纳入设备/IP/UA 记录，本方案先不强制落字段，但 `metadata_json` 预留扩展空间。

## 与其他模块的协作方式

### chat / session / models / profile

这些模块不直接解析 JWT。

统一做法：

1. 路由层声明 `current_user = Depends(require_current_user)`
2. 业务层只使用 `current_user.user_id`
3. 如需最小身份信息，可使用 `current_user.username`、`current_user.status`

这样可以保证：

- 认证逻辑只维护一处
- 用户状态禁用后，所有受保护模块都会同步失效

## 配置项建议

建议在 `app/config.py` 中补充以下配置：

- `JWT_SECRET_KEY`
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_SECONDS`
- `AUTH_COOKIE_NAME`
- `AUTH_COOKIE_SECURE`
- `AUTH_COOKIE_SAMESITE`
- `AUTH_COOKIE_DOMAIN`（同域一期可选）
- `ALLOWED_ORIGINS`

一期建议默认值：

- `ACCESS_TOKEN_EXPIRE_SECONDS = 7200`
- `AUTH_COOKIE_NAME = em_access_token`
- `AUTH_COOKIE_SAMESITE = lax`

## 落地约束

### 1. 登录失败响应要避免枚举用户

要求：

- 不暴露“用户名不存在”与“密码错误”的差异
- 对外统一返回登录失败语义

### 2. 用户状态必须做二次校验

要求：

- 登录时校验一次
- 每次受保护请求再校验一次

原因：

- 防止用户在 token 有效期内被禁用后，旧 token 继续访问

### 3. token 状态必须依赖 Redis

要求：

- 不只校验 JWT 自身合法性
- 还要校验 Redis 中该 `jti` 是否仍然存在

原因：

- 这样才能支持登出即时失效

### 4. 认证逻辑不得散落在业务模块里

要求：

- 其他模块只能通过 `security` 依赖获取当前用户
- 不允许在 `chat`、`session`、`models` 等模块内部重复写 token 解析逻辑

## 典型时序

### 登录成功

1. 前端提交 `username/password`
2. `Auth API` 调用 `AuthService.login`
3. 查询 `users`
4. 校验用户状态
5. 校验密码
6. 生成 `jti`
7. 签发 JWT
8. 写入 Redis `auth:token:{jti}`
9. 更新 `users.last_login_at`
10. 返回响应并设置 Cookie

### 访问受保护接口

1. 前端带 Cookie 请求业务接口
2. `security` 从 Cookie 读取 token
3. 校验 JWT
4. 查询 Redis `auth:token:{jti}`
5. 查询 `users`
6. 校验 `users.status == active`
7. 注入 `AuthenticatedUser`
8. 业务模块继续执行

### 登出

1. 前端调用 `/api/v1/auth/logout`
2. `security` 完成当前请求认证
3. `AuthService.logout` 删除 Redis `auth:token:{jti}`
4. 返回响应并清理 Cookie

## 推荐实现顺序

为了尽快落地，建议按下面顺序开发：

1. 完成密码哈希方案与 seed 账号初始化约束
2. 完成 `UserRepository` 的按用户名/按 ID 查询
3. 完成 access token 的签发与解析能力
4. 完成 Redis token store
5. 完成 `AuthService.login/logout/me`
6. 完成 `security` 模块的 token 解析与当前用户依赖
7. 完成 `Origin/Referer` 校验能力
8. 将 `/api/v1/auth/*` 接口接入
9. 将 `chat`、`session`、`models` 等后续接口统一接入 `security`

## 本方案的最终收口

一期用户登录板块的最终方案建议收口为：

- 使用 `user` 模块承载登录业务闭环
- 单独建立 `security` 模块承载请求级认证过滤
- 使用 `HttpOnly Cookie + JWT access token + Redis token 状态` 形成最小认证闭环
- 一期不做 refresh token，只做 `1~2 小时` 短期 access token
- 允许同一账号多端登录，以 `jti` 维度管理每个 token
- 对写请求统一执行 `Origin/Referer` 校验
- 每次受保护请求都重新校验用户状态，确保被禁用用户立即失效
- 其他业务模块统一通过 `security` 依赖拿当前用户，不自行解析 token

这套设计满足你当前的一期目标：

- 足够小，可以直接开工
- 登录业务和请求鉴权边界清晰
- 与现有一期架构文档、数据库草案保持一致
- 后续扩展 refresh token、角色权限或更多认证方式时，不需要推翻现有模块边界
