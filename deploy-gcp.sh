#!/bin/bash
# ═══════════════════════════════════════════════════════════
#  Travelo AI — GCP Cloud Run Deployment Script
#  Usage: ./deploy-gcp.sh [PROJECT_ID] [REGION]
# ═══════════════════════════════════════════════════════════
set -euo pipefail

PROJECT_ID="${1:-$(gcloud config get-value project)}"
REGION="${2:-asia-south1}"  # Mumbai — closest to India

echo "═══════════════════════════════════════════"
echo "  Deploying Travelo AI to GCP Cloud Run"
echo "  Project: $PROJECT_ID"
echo "  Region:  $REGION"
echo "═══════════════════════════════════════════"

# ── Step 1: Enable required APIs ──
echo "▸ Enabling GCP APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  storage.googleapis.com \
  --project="$PROJECT_ID"

# ── Step 2: Create Artifact Registry repo (if not exists) ──
echo "▸ Creating Artifact Registry..."
gcloud artifacts repositories create travelo-ai \
  --repository-format=docker \
  --location="$REGION" \
  --description="Travelo AI container images" \
  --project="$PROJECT_ID" 2>/dev/null || echo "  (already exists)"

REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/travelo-ai"
CHROMA_BUCKET="${PROJECT_ID}-travelo-chroma"

# ── Step 3: Create GCS bucket for ChromaDB persistence ──
echo "▸ Creating GCS bucket for ChromaDB..."
gsutil mb -l "$REGION" -p "$PROJECT_ID" "gs://${CHROMA_BUCKET}" 2>/dev/null || echo "  (already exists)"

# ── Step 4: Build & push backend ──
echo "▸ Building backend image..."
gcloud builds submit ./backend \
  --tag="${REGISTRY}/backend:latest" \
  --project="$PROJECT_ID" \
  --timeout=1200  # 20min for PyTorch install

# ── Step 5: Deploy backend to Cloud Run ──
echo "▸ Deploying backend to Cloud Run..."
SQL_CONN="${PROJECT_ID}:${REGION}:travelo-db"
gcloud run deploy travelo-backend \
  --image="${REGISTRY}/backend:latest" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --platform=managed \
  --allow-unauthenticated \
  --memory=2Gi \
  --cpu=2 \
  --min-instances=0 \
  --max-instances=1 \
  --timeout=300 \
  --add-cloudsql-instances="$SQL_CONN" \
  --add-volume=name=chroma-vol,type=cloud-storage,bucket=${CHROMA_BUCKET} \
  --add-volume-mount=volume=chroma-vol,mount-path=/mnt/chroma \
  --set-env-vars="CHROMA_PERSIST_DIR=/mnt/chroma,SUPABASE_URL=https://qbolfgnnifmnixpajjgn.supabase.co,SUPABASE_ANON_KEY=sb_publishable_vv7lVtRFnngS7Y31rL_Txg_U42zP6w_" \
  --set-secrets="DATABASE_URL=database-url:latest,GEMINI_API_KEY=gemini-api-key:latest,SERPAPI_KEY=serpapi-key:latest,OPENWEATHER_API_KEY=openweather-api-key:latest,SUPABASE_JWT_SECRET=supabase-jwt-secret:latest" \
  --port=8080

# Get the backend URL
BACKEND_URL=$(gcloud run services describe travelo-backend \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --format='value(status.url)')

echo "✓ Backend deployed at: $BACKEND_URL"

# ── Step 6: Build & push frontend (with backend URL baked in) ──
echo "▸ Configuring local Docker auth for registry..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

echo "▸ Building frontend image with VITE_API_URL=${BACKEND_URL}..."
docker build ./frontend \
  --build-arg VITE_API_URL="${BACKEND_URL}" \
  --build-arg VITE_SUPABASE_URL="https://qbolfgnnifmnixpajjgn.supabase.co" \
  --build-arg VITE_SUPABASE_ANON_KEY="sb_publishable_vv7lVtRFnngS7Y31rL_Txg_U42zP6w_" \
  -t "${REGISTRY}/frontend:latest"

echo "▸ Pushing frontend image to Artifact Registry..."
docker push "${REGISTRY}/frontend:latest"

# ── Step 6: Deploy frontend to Cloud Run ──
echo "▸ Deploying frontend to Cloud Run..."
gcloud run deploy travelo-frontend \
  --image="${REGISTRY}/frontend:latest" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --platform=managed \
  --allow-unauthenticated \
  --memory=256Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=3 \
  --port=8080

FRONTEND_URL=$(gcloud run services describe travelo-frontend \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --format='value(status.url)')

echo "✓ Frontend deployed at: $FRONTEND_URL"

# ── Step 7: Update backend CORS with actual frontend URL ──
echo "▸ Updating backend CORS..."
gcloud run services update travelo-backend \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --update-env-vars="ALLOWED_ORIGINS=${FRONTEND_URL}"

echo ""
echo "═══════════════════════════════════════════"
echo "  ✅ DEPLOYMENT COMPLETE!"
echo "═══════════════════════════════════════════"
echo ""
echo "  Frontend: $FRONTEND_URL"
echo "  Backend:  $BACKEND_URL"
echo ""
echo "  ⚠️  Don't forget to:"
echo "  1. Set up Cloud SQL and connect it (see deployment guide)"
echo "  2. Set API key env vars on the backend service"
echo "  3. Update Supabase redirect URLs to: $FRONTEND_URL"
echo ""
