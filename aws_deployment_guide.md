# MEGA — AWS Deployment Guide

## Architecture Overview

```
Users
  │
  ▼
CloudFront (CDN)
  ├── /api/* → ALB → ECS (Backend Node.js)
  └── /*     → S3  (React frontend build)
                      │
             ┌────────┼────────┐
             │        │        │
          MongoDB  ElastiCache  S3
          Atlas    (Redis)    (Videos)
             │
          EC2 / ECS
        (ML Service - Python)
```

---

## Service Map

| Service | What it is | AWS Target |
|---------|-----------|------------|
| Frontend | React/Vite | S3 + CloudFront |
| Backend | Node.js/Express | ECS Fargate or EC2 |
| ML Service | Python/FastAPI + CLIP/Whisper | EC2 (g4dn.xlarge) |
| Database | MongoDB | MongoDB Atlas (Free/M10) |
| Cache | Redis | ElastiCache (t3.micro) |
| Video storage | Local disk → S3 | Amazon S3 |

---

## Step 1 — Prerequisites

```bash
# Install AWS CLI
winget install Amazon.AWSCLI

# Configure credentials
aws configure
# Enter: Access Key ID, Secret Key, Region (ap-south-1 for India), Output: json
```

Create an IAM user with:
- `AmazonS3FullAccess`
- `AmazonEC2FullAccess`
- `AmazonECS_FullAccess`
- `CloudFrontFullAccess`
- `ElastiCacheFullAccess`

---

## Step 2 — MongoDB Atlas (Database)

> Recommended over AWS DocumentDB — free tier available.

1. Go to [mongodb.com/atlas](https://cloud.mongodb.com)
2. Create a free **M0 cluster** (512 MB) or **M10** for production
3. Add IP Whitelist: `0.0.0.0/0` (for EC2 access)
4. Create a DB user → copy the connection string:
   ```
   mongodb+srv://user:pass@cluster0.xxxxx.mongodb.net/mega
   ```
5. Update your backend ENV later: `MONGODB_URI=<above string>`

---

## Step 3 — S3 Bucket (Video Storage)

```bash
# Create bucket (replace with your bucket name)
aws s3 mb s3://mega-videos-sahil --region ap-south-1

# Block public access (videos served through backend only)
aws s3api put-public-access-block \
  --bucket mega-videos-sahil \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

Update backend to stream from S3 instead of local disk (change `VIDEO_STORAGE_PATH` to use AWS SDK — see Step 7).

---

## Step 4 — ElastiCache Redis (Cache)

```bash
# Create a Redis cluster (t3.micro = free-tier eligible)
aws elasticache create-cache-cluster \
  --cache-cluster-id mega-redis \
  --engine redis \
  --cache-node-type cache.t3.micro \
  --num-cache-nodes 1 \
  --region ap-south-1
```

> ⚠️ ElastiCache is VPC-only — your EC2/ECS must be in the **same VPC**.

Get the endpoint:
```bash
aws elasticache describe-cache-clusters \
  --cache-cluster-id mega-redis \
  --show-cache-node-info \
  --query 'CacheClusters[0].CacheNodes[0].Endpoint'
```

---

## Step 5 — ML Service on EC2 (GPU)

The ML service needs GPU for fast inference (CLIP, Whisper).

### 5a. Launch EC2 instance

```bash
# g4dn.xlarge = 1x NVIDIA T4 GPU, 16GB RAM (~$0.53/hr)
# For dev/demo: t3.large (CPU only, slower) = $0.08/hr
aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \  # Ubuntu 22.04 LTS (ap-south-1)
  --instance-type g4dn.xlarge \
  --key-name your-key-pair \
  --security-group-ids sg-xxxxxxxx \
  --subnet-id subnet-xxxxxxxx \
  --count 1 \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=mega-ml}]'
```

> **Security Group rules needed:**
> - Inbound: Port 8001 from backend SG only
> - Inbound: Port 22 from your IP (SSH)

### 5b. SSH and setup

```bash
ssh -i your-key.pem ubuntu@<EC2_PUBLIC_IP>

# Install dependencies
sudo apt update && sudo apt install -y python3-pip python3-venv git
sudo apt install -y ffmpeg libsm6 libxext6

# Clone project
git clone https://github.com/yourrepo/mega.git
cd mega/ml-service

# Setup Python env
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create systemd service for auto-restart
sudo tee /etc/systemd/system/mega-ml.service > /dev/null <<EOF
[Unit]
Description=MEGA ML Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/mega/ml-service
Environment=PATH=/home/ubuntu/mega/ml-service/venv/bin
ExecStart=/home/ubuntu/mega/ml-service/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8001 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable mega-ml
sudo systemctl start mega-ml

# Check status
sudo systemctl status mega-ml
```

---

## Step 6 — Backend on ECS Fargate

### 6a. Create Dockerfile (if not present)

```dockerfile
# backend/Dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev
COPY src/ ./src/
EXPOSE 3000
CMD ["node", "src/index.js"]
```

### 6b. Push to ECR

```bash
# Create ECR repository
aws ecr create-repository --repository-name mega-backend --region ap-south-1

# Get login token
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS \
  --password-stdin <ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com

# Build and push
cd backend
docker build -t mega-backend .
docker tag mega-backend:latest <ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/mega-backend:latest
docker push <ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/mega-backend:latest
```

### 6c. Create ECS Task Definition

Create `task-definition.json`:
```json
{
  "family": "mega-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/ecsTaskExecutionRole",
  "containerDefinitions": [{
    "name": "mega-backend",
    "image": "<ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/mega-backend:latest",
    "portMappings": [{ "containerPort": 3000 }],
    "environment": [
      { "name": "MONGODB_URI",     "value": "mongodb+srv://..." },
      { "name": "REDIS_HOST",      "value": "<elasticache-endpoint>" },
      { "name": "JWT_SECRET",      "value": "your-secret" },
      { "name": "ML_SERVICE_URL",  "value": "http://<ec2-private-ip>:8001" },
      { "name": "EMAIL_USER",      "value": "sahiltpatil03@gmail.com" },
      { "name": "EMAIL_PASS",      "value": "eoxo ndea xrwp rvge" },
      { "name": "CLIENT_URL",      "value": "https://your-cloudfront-domain.com" }
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/mega-backend",
        "awslogs-region": "ap-south-1",
        "awslogs-stream-prefix": "ecs"
      }
    }
  }]
}
```

```bash
aws ecs register-task-definition --cli-input-json file://task-definition.json
aws ecs create-cluster --cluster-name mega-cluster
aws ecs create-service \
  --cluster mega-cluster \
  --service-name mega-backend \
  --task-definition mega-backend \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

---

## Step 7 — Frontend on S3 + CloudFront

### 7a. Build frontend

```bash
cd frontend

# Update .env for production
echo "VITE_API_URL=https://your-cloudfront-domain.com" > .env.production

npm run build   # outputs to dist/
```

### 7b. Create S3 bucket for hosting

```bash
aws s3 mb s3://mega-frontend-sahil --region ap-south-1

# Upload build
aws s3 sync dist/ s3://mega-frontend-sahil --delete

# Enable static website hosting
aws s3 website s3://mega-frontend-sahil \
  --index-document index.html \
  --error-document index.html    # SPA fallback
```

### 7c. Create CloudFront distribution

```bash
aws cloudfront create-distribution \
  --origin-domain-name mega-frontend-sahil.s3-website.ap-south-1.amazonaws.com \
  --default-root-object index.html
```

> Configure **2 origins** in CloudFront:
> - `/*` → S3 bucket (frontend)
> - `/api/*` → ALB pointing to ECS backend

---

## Step 8 — Environment Variables Summary

### Backend `.env` (production)
```env
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/mega
REDIS_HOST=mega-redis.xxxxx.cache.amazonaws.com
REDIS_PORT=6379
JWT_SECRET=<strong-random-64-char>
ML_SERVICE_URL=http://<ec2-private-ip>:8001
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=sahiltpatil03@gmail.com
EMAIL_PASS=eoxo ndea xrwp rvge
CLIENT_URL=https://dxxxxx.cloudfront.net
VIDEO_STORAGE_PATH=s3://mega-videos-sahil   # or keep local on EC2
```

---

## Step 9 — Cost Estimate (Monthly)

| Service | Tier | Est. Cost/month |
|---------|------|----------------|
| EC2 g4dn.xlarge (ML) | On-demand | ~$380 |
| EC2 t3.large (ML, CPU only) | On-demand | ~$60 |
| ECS Fargate (Backend) | 0.5 vCPU, 1GB | ~$15 |
| S3 (videos + frontend) | 50 GB | ~$1.15 |
| CloudFront | 1 TB transfer | ~$8.50 |
| ElastiCache t3.micro | Redis | ~$12 |
| MongoDB Atlas M0 | Free tier | $0 |
| **Total (CPU ML)** | | **~$97/month** |
| **Total (GPU ML)** | | **~$417/month** |

> 💡 **Tip:** Stop EC2 when not in use. Use `aws ec2 stop-instances` and `start-instances` to save cost during development.

---

## Recommended Deployment Order

```
1. MongoDB Atlas     → get connection string
2. ElastiCache       → get Redis endpoint  
3. S3 buckets        → create videos + frontend buckets
4. EC2 ML Service    → deploy Python service
5. ECS Backend       → deploy Node.js with all env vars
6. S3 + CloudFront   → build and deploy frontend
7. Test end-to-end   → register, upload, search
```

> [!TIP]
> For a B.Tech demo/project, use **EC2 t3.medium** for the backend too (instead of ECS) — it's simpler and cheaper. Just SSH in, clone the repo, run `npm start` as a systemd service.

> [!WARNING]
> Never commit `.env` files with credentials to Git. Use **AWS Secrets Manager** or **Systems Manager Parameter Store** for production secrets.
