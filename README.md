## <About the project will be put later>
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

Step - 2: Start Mongo and Redis server
```
sudo systemctl start mongod
sudo systemctl status mongod
```
```
sudo systemctl start redis-server
sudo systemctl status redis-server
```

Step - 3: Build the FastAPI Dockerfile
1) Create .env file in /api and add:
```env
EH_COMPAT_CONN_STR=
EH_CONSUMER_GROUP=telemetry-app

# MongoDB
MONGO_URI=mongodb://host.docker.internal:27017/iot_demo
MONGO_DB=iot_demo

# Redis
REDIS_URL=redis://host.docker.internal:6379/0

# Alerting thresholds (example)
ALERT_TEMP_GT=80

#IoT Hub service connection string for getting access to IoT Hub services like c2d messages 
IOTHUB_SERVICE_CONN_STR=
```
2) Run this in azure cli to get the Event Hub Connection string(EH_COMPAT_CONN_STR):
```
az iot hub connection-string show \
  -n iothub-sudeep \
  --default-eventhub \
  --policy-name service \
  -o tsv
```

In Azure portal-> your-iot-hub -> in the left navigation panel (security settings -> shared access policies -> service -> primary connection string) for IOTHUB service connection string (IOTHUB_SERVICE_CONN_STR)

3) Run ```docker build -t e2e-pipeline:1 .```
4) After successful build run: ```docker run -p 8000:8000 --env-file .env --add-host=host.docker.internal:host-gateway e2e-pipeline:1``` to get live logs of every request and response codes

Endpoints to verify:
open ```http://localhost:8000```
check `/health` , `/devices` , `/telemetry/{device_id}` , `/debug/stats`
