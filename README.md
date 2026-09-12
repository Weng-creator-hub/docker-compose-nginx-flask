# Docker Compose Nginx + Flask 多服务部署

基于 Docker Compose 实现的 Nginx + Gunicorn + Flask 多容器部署项目。

项目使用 Nginx 作为统一访问入口，通过 Docker 内部网络将请求转发至 Backend，并加入健康检查、启动依赖和容器重启策略。

## 技术栈

* Docker
* Docker Compose
* Nginx
* Python
* Flask
* Gunicorn
* Docker Bridge Network

## 请求链路

```mermaid
flowchart LR
    Client["客户端"] --> Host["宿主机 8080"]
    Host --> Nginx["Nginx 容器 80"]
    Nginx --> Backend["Backend 容器 8080"]
    Backend --> App["Gunicorn + Flask"]
```

外部用户只能通过 Nginx 访问应用，Backend 不直接向宿主机暴露端口。

## 项目结构

```text
backend-demo/
 app.py                 # Flask 应用及健康检查接口
 Dockerfile             # Backend 镜像构建文件
 docker-compose.yml     # 多容器编排配置
 nginx.conf             # Nginx 反向代理配置
 requirements.txt       # Python 依赖版本
 .dockerignore          # Docker 构建上下文排除规则
 .gitignore             # Git 忽略规则
 README.md
```

## 核心设计

### 1. Nginx 统一入口

宿主机默认使用 `8080` 端口接收请求，并映射到 Nginx 容器的 `80` 端口：

```yaml
ports:
  - "${WEB_PORT:-8080}:80"
```

可以通过环境变量修改宿主机端口，未设置时默认使用 `8080`。

Nginx 通过服务名访问 Backend：

```nginx
proxy_pass http://backend:8080;
```

这里不使用固定 IP，因为 Docker Compose 会通过内部 DNS 将服务名 `backend` 解析为对应容器地址。

### 2. 网络隔离

Nginx 和 Backend 加入自定义 Bridge 网络：

```yaml
networks:
  app_net:
    driver: bridge
```

Backend 没有配置宿主机端口映射，只能由同一 Docker 网络中的服务访问，减少不必要的端口暴露。

### 3. Backend 健康检查

Docker Engine 定期在 Backend 容器内部执行：

```python
import urllib.request
urllib.request.urlopen("http://127.0.0.1:8080/health")
```

健康检查配置：

```yaml
healthcheck:
  test:
    - CMD
    - python
    - -c
    - "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/health')"
  interval: 10s
  timeout: 3s
  retries: 3
  start_period: 5s
```

使用 Python 标准库完成检查，不需要额外在 Backend 镜像中安装 `curl`。

### 4. 启动依赖

Nginx 在启动阶段等待 Backend 进入健康状态：

```yaml
depends_on:
  backend:
    condition: service_healthy
```

这可以避免 Nginx 先启动，而 Backend 尚未准备完成。

需要注意：该配置主要控制启动顺序。Backend 运行过程中变为 `unhealthy` 时，Compose 不会自动停止 Nginx。

### 5. 重启策略

两个服务均配置：

```yaml
restart: unless-stopped
```

当容器主进程异常退出时，Docker 会根据该策略重新启动容器；如果用户主动停止容器，则不会持续重启。

健康检查失败本身只会将容器标记为 `unhealthy`，不会直接触发重启。重启策略主要由容器主进程的退出状态触发。

### 6. 依赖管理

Python 依赖及版本统一记录在 `requirements.txt` 中，避免不同时间构建时因为依赖版本变化导致运行结果不一致。

### 7. 镜像构建与最小权限

Dockerfile 先复制并安装 `requirements.txt`，再复制应用代码。修改 `app.py` 后重新构建时，可以复用未变化的依赖安装层，减少重复安装。

容器运行阶段使用 UID 为 `10001` 的普通用户 `appuser`，避免应用进程长期以 root 身份运行，降低容器被攻击后的权限风险。

Gunicorn 使用两个 worker 处理请求，并将访问日志和错误日志输出到标准输出，便于通过 `docker compose logs` 查看。

## 部署方法

### 1. 检查 Compose 配置

```bash
docker compose config
```

退出码为 `0` 表示 Compose 文件语法和结构检查通过。

### 2.构建并启动服务

```bash
docker compose up -d --build
```

### 3. 查看容器状态

```bash
docker compose ps
```

预期状态：

```text
backend   Up (healthy)
nginx     Up
```

### 4. 验证访问链路

验证主页：

```bash
curl -i http://localhost:8080/
```

验证健康检查接口：

```bash
curl -i http://localhost:8080/health
```

`/health` 返回 HTTP 200，说明以下链路正常：

```text
宿主机端口映射  Nginx  Backend  Gunicorn  Flask
```

### 5. 查看日志

```bash
docker compose logs --tail=50 nginx backend
```

持续查看日志：

```bash
docker compose logs -f nginx backend
```

### 6. 停止服务

```bash
docker compose down
```

## 自定义宿主机端口

例如使用宿主机 `8081` 端口：

```bash
WEB_PORT=8081 docker compose up -d
```

访问地址相应变为：

```text
http://localhost:8081
```

## 常用排查命令

查看 Backend 健康状态：

```bash
docker inspect "$(docker compose ps -q backend)" \
  --format '{{.State.Health.Status}}'
```

检查 Nginx 能否解析 Backend 服务名：

```bash
docker compose exec nginx getent hosts backend
```

查看端口映射：

```bash
docker compose port nginx 80
```

查看容器重启次数：

```bash
docker inspect "$(docker compose ps -q backend)" \
  --format '{{.RestartCount}}'
```

## 故障排查记录

### Nginx 出现 `host not found in upstream "backend"`

排查过程：

1. 使用 `docker compose ps` 检查 Backend 是否创建成功
2. 使用 `docker compose config` 检查网络配置结构
3. 检查 Nginx 和 Backend 是否加入同一个 `app_net`
4. 在 Nginx 容器中使用 `getent hosts backend` 验证 Docker DNS
5. 检查 `proxy_pass` 是否指向 `backend:8080`

最终确认问题来自 Compose 网络配置错误，修正后 Nginx 能够通过服务名访问 Backend。

### 访问 `/health` 返回 404

错误访问方式：

```bash
curl http://localhost/health
```

未指定端口时，请求会访问宿主机的 `80` 端口，而本项目映射的是宿主机 `8080` 端口。

正确方式：

```bash
curl http://localhost:8080/health
```

该问题说明排查容器服务时，需要区分宿主机端口与容器端口。

## 当前边界

* 当前项目运行在单台 Docker 主机上，不属于多节点容器集群
* 健康检查只能反映 Backend 接口状态，不能代替完整业务监控
* `restart` 策略不会因为容器变为 `unhealthy` 而直接触发
* 当前未接入数据库、集中日志和指标监控

## 后续计划

* 固定 Nginx 和 Python 基础镜像版本
* 增加资源限制和日志轮转配置
* 增加 `.env.example`
* 接入 Prometheus 和 Grafana
* 增加自动化部署及 CI/CD 流程

