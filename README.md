Step - 1: Start the Data Simulation
1) Head to /device-sim in terminal
2) add this in the .env file:
```env
IOTHUB_HOST=
DEVICE_ID=
DEVICE_KEY=
```
3) Run:
   ```docker build -t device-sim .```
   ```docker run --env-file .env device-sim```
   Then you can observe telemetry data generating (also can verify in Azure Portal)

Step - 2: Start Mongo and Redis server in docker
```
docker run -d --name mongo \
  -p 27017:27017 \
  -v mongo_data:/data/db \
  --restart unless-stopped \
  mongo:4.4
```
```

docker run -d --name redis \
  -p 6379:6379 \
  --restart unless-stopped \
  redis:7
```

Step - 3: Compose the FastAPI + Mongo + Redis Dockerfile
1) Create .env file in /api and add:
```env
EH_COMPAT_CONN_STR=
EH_CONSUMER_GROUP=telemetry-app

# MongoDB
MONGO_URI=mongodb://mongo:27017
MONGO_DB=iot_demo

# Redis
REDIS_URL=redis://redis:6379/0

# Alerting thresholds (example)
ALERT_TEMP_GT=80
```
2) Run this in azure cli to get the Connection string:
```
az iot hub connection-string show \
  -n iothub-sudeep \
  --default-eventhub \
  --policy-name service \
  -o tsv
```
3) Run ```docker compose -f docker-compose.dev.yml up -d```
4) After successful build run: ```docker compose -f docker-compose.dev.yml logs -f api``` to get live logs of every request and response codes

Endpoints to verify:
open ```http://localhost:8000```
check /health , /devices , /telemetry/{device_id} , /debug/stats
