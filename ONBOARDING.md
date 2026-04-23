

# 第一次配置 (地端, DB使用地端的)

## 建立環境變數配置檔案 docker/.env
```
## Docker image tag
# default:latest [External Dev Don't Need to Fill Below Variable]
NGINX_IMAGE_tag=
NODE_IMAGE_TAG=21.6.0-alpine3.18
# GOLANG_IMAGE_TAG=1.21.3-alpine3.18
GOLANG_IMAGE_TAG=1.25.4-bookworm

## Frontend ENV Configs
VITE_API_URL=/api/dev
NODE_ENV=development
VITE_APP_TITLE=臺北城市儀表板
VITE_APP_VERSION=2.0.0
VITE_MAPBOXTOKEN=pk.eyJ1Ijoic3AxMjg5MzY3OCIsImEiOiJjbW54MzI1Zm0wMDh4MnJzNDU1M295azM3In0.YVtDteIiXIV7ob6eQIkyjw
VITE_MAPBOXTILE=

## Dashboard backend Server ENV Configs
GIN_MODE=debug # gin mode can be release(default)/debug/test
# GIN_DOMAIN should be set to 0.0.0.0 during dev
GIN_DOMAIN=0.0.0.0
GIN_PORT=8080
JWT_SECRET=secret
IDNO_SALT=salt
# [External Dev Don't Need to Fill Below Variable]
ISSO_URL=
# [External Dev Don't Need to Fill Below Variable]
TAIPEIPASS_URL=
# [External Dev Don't Need to Fill Below Variable]
ISSO_CLIENT_ID=
# [External Dev Don't Need to Fill Below Variable]
ISSO_CLIENT_SECRET=
# [External Dev Don't Need to Fill Below Variable]
ISSO_CLIENT_SCOPE=
DASHBOARD_DEFAULT_USERNAME=test
DASHBOARD_DEFAULT_Email=test1234@gmail.com
DASHBOARD_DEFAULT_PASSWORD=test1234

## DB Configs
# Dashboard data DB
DB_DASHBOARD_HOST=postgres-data
DB_DASHBOARD_USER=postgres
DB_DASHBOARD_PASSWORD=test1234
DB_DASHBOARD_DBNAME=dashboard
DB_DASHBOARD_PORT=5432
DASHBOARD_SAMPLE_FILE=dashboard-demo.sql
DB_DASHBOARD_SSLMODE=disable

# Dashboard Manager DB
DB_MANAGER_HOST=postgres-manager
DB_MANAGER_USER=postgres
DB_MANAGER_PASSWORD=test1234
DB_MANAGER_DBNAME=dashboardmanager
DB_MANAGER_PORT=5432
MANAGER_SAMPLE_FILE=dashboardmanager-demo.sql
DB_MANAGER_SSLMODE=disable

# Redis Configs
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# pgadmin
PGADMIN_DEFAULT_EMAIL=test1234@gmail.com
PGADMIN_DEFAULT_PASSWORD=test1234
PGADMIN_LISTEN_PORT=80

# Qdrant Configs
QDRANT_URL=http://qdrant:6333
QDRANT_API_KEY=your_api_key
QDRANT_COLLECTION=query_charts

#Model Path
LM_MODEL_PATH=/opt/lm_model/onnx-e5/

# TWCC AI Foundry Service
TWCC_API_URL=https://api-ams.twcc.ai/api
TWCC_API_KEY=38c5ee00-7ca5-4e26-8245-d3dafcee7e27
TWCC_MODEL=llama3.3-ffm-70b-16k-chat
TWCC_TIMEOUT=60
TWCC_MAX_RETRY=2
TWCC_MAX_CONCURRENT=10
```

## 啟動環境
```
cd docker

# 建立網路
docker network create --driver=bridge --subnet=192.168.128.0/24 --gateway=192.168.128.1  br_dashboard

# 啟動與 DB 及 Qdrant 相關的容器
docker-compose -f docker-compose-db.yaml up -d

# 初始化前端和後端環境
docker-compose -f docker-compose-init.yaml up -d

# 啟動前端和後端服務
docker-compose up -d

# 執行資料匯入工具。此工具會將 PostgreSQL 中的資料轉換為向量並寫入 Qdrant
docker compose --profile tools up vector-db-upgrade
```

## 前端訪問:
http://localhost:8080/dashboard?index=ltc_care_tpe&city=taipei

### 登入方式 (會有後台管理頁面):
請按著Shift鍵 + 台北儀表板LOGO圖示 => 會變成帳號密碼形式輸入
帳號：test1234@gmail.com
密碼：test1234


## 後端:

### DB說明
有兩個DB

```
## DB Configs
# Dashboard data DB
DB_DASHBOARD_HOST=postgres-data
DB_DASHBOARD_USER=postgres
DB_DASHBOARD_PASSWORD=test1234
DB_DASHBOARD_DBNAME=dashboard
DB_DASHBOARD_PORT=5432
DASHBOARD_SAMPLE_FILE=dashboard-demo.sql
DB_DASHBOARD_SSLMODE=disable

# Dashboard Manager DB
DB_MANAGER_HOST=postgres-manager
DB_MANAGER_USER=postgres
DB_MANAGER_PASSWORD=test1234
DB_MANAGER_DBNAME=dashboardmanager
DB_MANAGER_PORT=5432
MANAGER_SAMPLE_FILE=dashboardmanager-demo.sql
DB_MANAGER_SSLMODE=disable
```

## AI 模型調用

### docker/.env配置

#### LLM 模型調用配置
TWCC_API_KEY => 可以替換為自己去 那個雲註冊的KEY

```
# TWCC AI Foundry Service
TWCC_API_URL=https://api-ams.twcc.ai/api
TWCC_API_KEY=38c5ee00-7ca5-4e26-8245-d3dafcee7e27
TWCC_MODEL=llama3.3-ffm-70b-16k-chat
TWCC_TIMEOUT=60
TWCC_MAX_RETRY=2
TWCC_MAX_CONCURRENT=10
```

#### 向量資料庫配置
使用本地模型 LM_MODEL_PATH
```
# Qdrant Configs
QDRANT_URL=http://qdrant:6333
QDRANT_API_KEY=your_api_key
QDRANT_COLLECTION=query_charts

#Model Path
LM_MODEL_PATH=/opt/lm_model/onnx-e5/
```

### LLM服務文件說明
https://docs.twcloud.ai/docs/user-guides/twcc/afs/api-and-parameters/api-compatible-with-openai

### 範例LLM Request
```
curl --location 'https://api-ams.twcc.ai/api/models/chat/completions' \
--header 'Content-Type: application/json' \
--header 'Authorization: ••••••' \
--data '{
  "model": "llama3.3-ffm-70b-16k-chat",
   "messages": [{"role":"user","content":"hi"}]
}'
```



# 雲端DB配置
```
## DB Configs
# Dashboard data DB
DB_DASHBOARD_HOST=tp-test-db.postgres.database.azure.com
DB_DASHBOARD_USER=ad0kj12wdu
DB_DASHBOARD_PASSWORD="p9#j^!~wda5"
DB_DASHBOARD_DBNAME=postgres
DB_DASHBOARD_PORT=5432
DASHBOARD_SAMPLE_FILE=dashboard-demo.sql
DB_DASHBOARD_SSLMODE=require

# Dashboard Manager DB
DB_MANAGER_HOST=tp-test-db-2.postgres.database.azure.com
DB_MANAGER_USER=w9wd87im
DB_MANAGER_PASSWORD="k^%1uh*81a~"
DB_MANAGER_DBNAME=postgres
DB_MANAGER_PORT=5432
MANAGER_SAMPLE_FILE=dashboardmanager-demo.sql
DB_MANAGER_SSLMODE=require
